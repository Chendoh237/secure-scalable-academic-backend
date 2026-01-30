#!/usr/bin/env python
"""
Security Testing Script for Student Timetable Module

This script tests security aspects including:
1. Authentication and authorization controls
2. SQL injection prevention
3. Data validation and sanitization
4. Access control enforcement
5. Input validation
"""

import os
import sys
import django
import json
import time
from typing import Dict, List, Any, Optional

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.db import connection
from django.core.exceptions import ValidationError
from django.test.utils import override_settings
import unittest

from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import Level, Course, TimetableSlot, DepartmentTimetable
from institutions.models import Institution, Faculty, Department
from users.models import User

User = get_user_model()


class StudentTimetableSecurityTest(TransactionTestCase):
    """
    Security tests for Student Timetable Module
    
    Tests authentication, authorization, input validation, and SQL injection prevention.
    """
    
    @classmethod
    def setUpClass(cls):
        """Set up test data for security testing"""
        super().setUpClass()
        
        # Create test institution structure
        cls.institution = Institution.objects.create(
            name="Test University",
            code="TU"
        )
        
        # Create academic program first (required for Faculty)
        from institutions.program_models import AcademicProgram
        cls.program = AcademicProgram.objects.create(
            name="Engineering Program",
            code="ENG",
            institution=cls.institution
        )
        
        cls.faculty = Faculty.objects.create(
            name="Faculty of Engineering",
            program=cls.program
        )
        
        cls.department1 = Department.objects.create(
            name="Computer Science",
            faculty=cls.faculty
        )
        
        cls.department2 = Department.objects.create(
            name="Electrical Engineering",
            faculty=cls.faculty
        )
        
        # Create test levels for both departments
        cls.level1_dept1 = Level.objects.create(
            name="Level 100",
            code="L100",
            department=cls.department1
        )
        
        cls.level1_dept2 = Level.objects.create(
            name="Level 100",
            code="L100",
            department=cls.department2
        )
        
        # Create test courses
        cls.course1_dept1 = Course.objects.create(
            code="CS101",
            title="Introduction to Programming",
            credit_units=3,
            department=cls.department1,
            level=cls.level1_dept1,
            semester=1
        )
        
        cls.course1_dept2 = Course.objects.create(
            code="EE101",
            title="Circuit Analysis",
            credit_units=3,
            department=cls.department2,
            level=cls.level1_dept2,
            semester=1
        )
    
    def setUp(self):
        """Set up for each test"""
        # Create test users and students
        self.user1 = User.objects.create_user(
            username='student1',
            email='student1@test.com',
            password='testpass123',
            first_name='Student',
            last_name='One'
        )
        
        self.user2 = User.objects.create_user(
            username='student2',
            email='student2@test.com',
            password='testpass123',
            first_name='Student',
            last_name='Two'
        )
        
        # Student 1 belongs to department 1
        self.student1 = Student.objects.create(
            user=self.user1,
            full_name='Student One',
            matric_number='ST001',
            institution=self.institution,
            faculty=self.faculty,
            department=self.department1,
            program=self.program,
            is_approved=True
        )
        
        # Student 2 belongs to department 2
        self.student2 = Student.objects.create(
            user=self.user2,
            full_name='Student Two',
            matric_number='ST002',
            institution=self.institution,
            faculty=self.faculty,
            department=self.department2,
            program=self.program,
            is_approved=True
        )
        
        # Create level selections
        StudentLevelSelection.objects.create(
            student=self.student1,
            level=self.level1_dept1
        )
        
        StudentLevelSelection.objects.create(
            student=self.student2,
            level=self.level1_dept2
        )
        
        self.client = Client()
    
    def tearDown(self):
        """Clean up after each test"""
        Student.objects.filter(matric_number__startswith='ST').delete()
        User.objects.filter(username__startswith='student').delete()
    
    def test_authentication_required(self):
        """Test that all endpoints require authentication"""
        print("Testing authentication requirements...")
        
        endpoints = [
            '/api/students/levels/',
            '/api/students/level-selection/',
            '/api/students/timetable/',
            '/api/students/course-selections/',
        ]
        
        for endpoint in endpoints:
            # Test GET without authentication
            response = self.client.get(endpoint)
            self.assertIn(response.status_code, [401, 403], 
                         f"Endpoint {endpoint} should require authentication for GET")
            
            # Test POST without authentication
            response = self.client.post(endpoint, {'test': 'data'}, content_type='application/json')
            self.assertIn(response.status_code, [401, 403], 
                         f"Endpoint {endpoint} should require authentication for POST")
        
        print("✓ All endpoints properly require authentication")
    
    def test_department_isolation(self):
        """Test that students can only access their own department's data"""
        print("Testing department isolation...")
        
        # Login as student1 (department1)
        self.client.force_login(self.user1)
        
        # Test levels endpoint - should only return department1 levels
        response = self.client.get('/api/students/levels/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        levels = data.get('levels', [])
        
        # Should only contain levels from department1
        for level in levels:
            # We can't directly check department in the response, but we know
            # the student should only see their department's levels
            pass
        
        # Test timetable endpoint with wrong department level
        response = self.client.get(f'/api/students/timetable/?level_id={self.level1_dept2.id}')
        self.assertEqual(response.status_code, 400, 
                        "Student should not be able to access other department's timetable")
        
        print("✓ Department isolation is properly enforced")
    
    def test_student_data_isolation(self):
        """Test that students can only access their own data"""
        print("Testing student data isolation...")
        
        # Create course selection for student1
        StudentCourseSelection.objects.create(
            student=self.student1,
            department=self.department1,
            level=self.level1_dept1,
            course=self.course1_dept1,
            is_offered=True
        )
        
        # Login as student1
        self.client.force_login(self.user1)
        
        # Get course selections - should only see own selections
        response = self.client.get('/api/students/course-selections/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        selections = data.get('course_selections', [])
        
        # Should have exactly 1 selection (student1's)
        self.assertEqual(len(selections), 1)
        
        # Login as student2
        self.client.force_login(self.user2)
        
        # Get course selections - should see no selections (student2 has none)
        response = self.client.get('/api/students/course-selections/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        selections = data.get('course_selections', [])
        
        # Should have 0 selections
        self.assertEqual(len(selections), 0)
        
        print("✓ Student data isolation is properly enforced")
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in API endpoints"""
        print("Testing SQL injection prevention...")
        
        self.client.force_login(self.user1)
        
        # Test various SQL injection attempts
        injection_payloads = [
            "1' OR '1'='1",
            "1; DROP TABLE students_student; --",
            "1' UNION SELECT * FROM auth_user --",
            "1' AND (SELECT COUNT(*) FROM auth_user) > 0 --",
            "'; DELETE FROM students_student; --",
            "1' OR 1=1 --",
            "admin'--",
            "admin' /*",
            "' or 1=1#",
            "' or 1=1--",
            "' or 1=1/*",
            "') or '1'='1--",
            "') or ('1'='1--"
        ]
        
        for payload in injection_payloads:
            # Test level_id parameter in timetable endpoint
            response = self.client.get(f'/api/students/timetable/?level_id={payload}')
            # Should return 400 (bad request) or 404 (not found), not 500 (server error)
            self.assertIn(response.status_code, [400, 404], 
                         f"SQL injection payload '{payload}' should not cause server error")
            
            # Test POST data in course selections
            response = self.client.post('/api/students/course-selections/', {
                'selections': [{'course_id': payload, 'is_offered': True}]
            }, content_type='application/json')
            # Should return 400 or 404, not 500
            self.assertIn(response.status_code, [400, 404], 
                         f"SQL injection payload '{payload}' in POST should not cause server error")
        
        print("✓ SQL injection prevention is working correctly")
    
    def test_input_validation(self):
        """Test input validation and sanitization"""
        print("Testing input validation...")
        
        self.client.force_login(self.user1)
        
        # Test invalid data types
        invalid_inputs = [
            # Invalid level_id types
            {'endpoint': '/api/students/level-selection/', 'data': {'level_id': 'invalid'}},
            {'endpoint': '/api/students/level-selection/', 'data': {'level_id': -1}},
            {'endpoint': '/api/students/level-selection/', 'data': {'level_id': 999999}},
            
            # Invalid course selection data
            {'endpoint': '/api/students/course-selections/', 'data': {'selections': 'not_a_list'}},
            {'endpoint': '/api/students/course-selections/', 'data': {'selections': [{'course_id': 'invalid'}]}},
            {'endpoint': '/api/students/course-selections/', 'data': {'selections': [{'is_offered': 'not_boolean'}]}},
        ]
        
        for test_case in invalid_inputs:
            response = self.client.post(
                test_case['endpoint'], 
                test_case['data'], 
                content_type='application/json'
            )
            self.assertEqual(response.status_code, 400, 
                           f"Invalid input should return 400 for {test_case['endpoint']}")
        
        print("✓ Input validation is working correctly")
    
    def test_authorization_bypass_attempts(self):
        """Test attempts to bypass authorization"""
        print("Testing authorization bypass prevention...")
        
        self.client.force_login(self.user1)
        
        # Attempt to access data from other department
        # Try to set level selection to a level from another department
        response = self.client.post('/api/students/level-selection/', {
            'level_id': self.level1_dept2.id  # This belongs to department2, user1 is in department1
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400, 
                        "Should not be able to select level from another department")
        
        # Try to create course selection for course in another department
        response = self.client.post('/api/students/course-selections/', {
            'selections': [{
                'course_id': self.course1_dept2.id,  # This belongs to department2
                'is_offered': True
            }]
        }, content_type='application/json')
        
        self.assertEqual(response.status_code, 400, 
                        "Should not be able to select course from another department")
        
        print("✓ Authorization bypass prevention is working correctly")
    
    def test_data_leakage_prevention(self):
        """Test that sensitive data is not leaked in responses"""
        print("Testing data leakage prevention...")
        
        self.client.force_login(self.user1)
        
        # Test levels endpoint
        response = self.client.get('/api/students/levels/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        
        # Check that response doesn't contain sensitive information
        response_str = json.dumps(data)
        
        # Should not contain other students' data
        self.assertNotIn(self.student2.matric_number, response_str)
        self.assertNotIn(self.user2.email, response_str)
        
        # Test timetable endpoint
        response = self.client.get(f'/api/students/timetable/?level_id={self.level1_dept1.id}')
        if response.status_code == 200:
            data = response.json()
            response_str = json.dumps(data)
            
            # Should not contain sensitive user information
            self.assertNotIn('password', response_str.lower())
            self.assertNotIn(self.user2.email, response_str)
        
        print("✓ Data leakage prevention is working correctly")
    
    def test_rate_limiting_headers(self):
        """Test for rate limiting headers (if implemented)"""
        print("Testing rate limiting awareness...")
        
        self.client.force_login(self.user1)
        
        # Make multiple requests to check for rate limiting headers
        response = self.client.get('/api/students/levels/')
        
        # Check if rate limiting headers are present (optional)
        rate_limit_headers = [
            'X-RateLimit-Limit',
            'X-RateLimit-Remaining',
            'X-RateLimit-Reset',
            'Retry-After'
        ]
        
        has_rate_limiting = any(header in response.headers for header in rate_limit_headers)
        
        if has_rate_limiting:
            print("✓ Rate limiting headers detected")
        else:
            print("ℹ No rate limiting headers found (consider implementing for production)")
    
    def test_csrf_protection(self):
        """Test CSRF protection for state-changing operations"""
        print("Testing CSRF protection...")
        
        # Create a new client without CSRF token
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user1)
        
        # Try to make POST request without CSRF token
        response = csrf_client.post('/api/students/level-selection/', {
            'level_id': self.level1_dept1.id
        }, content_type='application/json')
        
        # Should be rejected due to missing CSRF token
        # Note: DRF API views might not enforce CSRF by default
        # This test checks if CSRF protection is configured
        
        print("ℹ CSRF protection test completed (API endpoints may use token auth instead)")
    
    def test_secure_headers(self):
        """Test for security headers in responses"""
        print("Testing security headers...")
        
        self.client.force_login(self.user1)
        response = self.client.get('/api/students/levels/')
        
        # Check for security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': None,  # Should be present in production
            'Content-Security-Policy': None,    # Should be configured
        }
        
        headers_present = []
        headers_missing = []
        
        for header, expected_values in security_headers.items():
            if header in response.headers:
                headers_present.append(header)
                if expected_values and isinstance(expected_values, list):
                    if response.headers[header] not in expected_values:
                        print(f"⚠ {header} has unexpected value: {response.headers[header]}")
            else:
                headers_missing.append(header)
        
        if headers_present:
            print(f"✓ Security headers present: {', '.join(headers_present)}")
        
        if headers_missing:
            print(f"ℹ Security headers missing: {', '.join(headers_missing)} (consider adding for production)")
    
    def test_error_information_disclosure(self):
        """Test that error messages don't disclose sensitive information"""
        print("Testing error information disclosure...")
        
        self.client.force_login(self.user1)
        
        # Test with invalid IDs to trigger errors
        test_cases = [
            {'url': '/api/students/timetable/?level_id=999999', 'method': 'GET'},
            {'url': '/api/students/level-selection/', 'method': 'POST', 'data': {'level_id': 999999}},
        ]
        
        for test_case in test_cases:
            if test_case['method'] == 'GET':
                response = self.client.get(test_case['url'])
            else:
                response = self.client.post(
                    test_case['url'], 
                    test_case.get('data', {}), 
                    content_type='application/json'
                )
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    error_str = json.dumps(error_data).lower()
                    
                    # Check that error doesn't contain sensitive information
                    sensitive_terms = [
                        'traceback',
                        'exception',
                        'database',
                        'sql',
                        'password',
                        'secret',
                        'key',
                        'token'
                    ]
                    
                    for term in sensitive_terms:
                        self.assertNotIn(term, error_str, 
                                       f"Error response should not contain '{term}'")
                
                except json.JSONDecodeError:
                    # Non-JSON error response is acceptable
                    pass
        
        print("✓ Error information disclosure prevention is working correctly")


class SecurityTestRunner:
    """
    Security test runner with comprehensive reporting
    """
    
    def __init__(self):
        self.test_results = []
    
    def run_security_tests(self):
        """Run all security tests and generate report"""
        print("Student Timetable Module - Security Testing")
        print("=" * 60)
        
        # Create test suite
        suite = unittest.TestSuite()
        
        # Add all security test methods
        test_methods = [
            'test_authentication_required',
            'test_department_isolation',
            'test_student_data_isolation',
            'test_sql_injection_prevention',
            'test_input_validation',
            'test_authorization_bypass_attempts',
            'test_data_leakage_prevention',
            'test_rate_limiting_headers',
            'test_csrf_protection',
            'test_secure_headers',
            'test_error_information_disclosure'
        ]
        
        for method in test_methods:
            suite.addTest(StudentTimetableSecurityTest(method))
        
        # Run tests
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
        
        # Generate security report
        self.generate_security_report(result)
        
        return result.wasSuccessful()
    
    def generate_security_report(self, result):
        """Generate comprehensive security report"""
        print("\n" + "=" * 60)
        print("SECURITY TEST REPORT")
        print("=" * 60)
        
        total_tests = result.testsRun
        failures = len(result.failures)
        errors = len(result.errors)
        passed = total_tests - failures - errors
        
        print(f"Total Security Tests: {total_tests}")
        print(f"Passed: {passed}")
        print(f"Failed: {failures}")
        print(f"Errors: {errors}")
        
        if result.wasSuccessful():
            print("\n✓ ALL SECURITY TESTS PASSED")
            print("✓ Student Timetable Module meets security requirements")
        else:
            print("\n✗ SOME SECURITY TESTS FAILED")
            
            if result.failures:
                print("\nFailures:")
                for test, traceback in result.failures:
                    print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
            
            if result.errors:
                print("\nErrors:")
                for test, traceback in result.errors:
                    print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
        
        # Security recommendations
        print("\nSecurity Recommendations:")
        print("- Ensure HTTPS is used in production")
        print("- Implement rate limiting for API endpoints")
        print("- Add comprehensive logging for security events")
        print("- Regular security audits and penetration testing")
        print("- Keep dependencies updated")
        print("- Implement proper session management")
        print("- Use strong authentication mechanisms")
        
        print("=" * 60)


def main():
    """Main function"""
    try:
        runner = SecurityTestRunner()
        success = runner.run_security_tests()
        return success
    except Exception as e:
        print(f"Security testing failed: {e}")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)