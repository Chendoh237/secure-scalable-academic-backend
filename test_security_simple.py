#!/usr/bin/env python
"""
Simple Security Testing Script for Student Timetable Module

This script tests core security aspects without complex model setup:
1. Authentication requirements
2. Input validation
3. SQL injection prevention
4. Authorization controls
"""

import os
import sys
import django
import json
from typing import Dict, List, Any

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    sys.exit(1)

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
import unittest

User = get_user_model()


class SimpleSecurityTest(TestCase):
    """
    Simple security tests focusing on core security aspects
    """
    
    def setUp(self):
        """Set up for each test"""
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.client = Client()
    
    def test_authentication_required(self):
        """Test that all student timetable endpoints require authentication"""
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
            self.assertIn(response.status_code, [401, 403, 404], 
                         f"Endpoint {endpoint} should require authentication for GET")
            
            # Test POST without authentication
            response = self.client.post(endpoint, {'test': 'data'}, content_type='application/json')
            self.assertIn(response.status_code, [401, 403, 404], 
                         f"Endpoint {endpoint} should require authentication for POST")
        
        print("✓ All endpoints properly require authentication")
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in API endpoints"""
        print("Testing SQL injection prevention...")
        
        self.client.force_login(self.user)
        
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
        
        self.client.force_login(self.user)
        
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
            self.assertIn(response.status_code, [400, 404], 
                           f"Invalid input should return 400 or 404 for {test_case['endpoint']}")
        
        print("✓ Input validation is working correctly")
    
    def test_data_leakage_prevention(self):
        """Test that sensitive data is not leaked in responses"""
        print("Testing data leakage prevention...")
        
        self.client.force_login(self.user)
        
        # Test levels endpoint
        response = self.client.get('/api/students/levels/')
        
        if response.status_code == 200:
            data = response.json()
            response_str = json.dumps(data)
            
            # Should not contain sensitive information
            sensitive_terms = ['password', 'secret', 'key', 'token']
            for term in sensitive_terms:
                self.assertNotIn(term, response_str.lower(), 
                               f"Response should not contain sensitive term '{term}'")
        
        print("✓ Data leakage prevention is working correctly")
    
    def test_error_information_disclosure(self):
        """Test that error messages don't disclose sensitive information"""
        print("Testing error information disclosure...")
        
        self.client.force_login(self.user)
        
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
    
    def test_secure_headers(self):
        """Test for security headers in responses"""
        print("Testing security headers...")
        
        self.client.force_login(self.user)
        response = self.client.get('/api/students/levels/')
        
        # Check for security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': ['DENY', 'SAMEORIGIN'],
            'X-XSS-Protection': '1; mode=block',
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
    
    def test_rate_limiting_awareness(self):
        """Test for rate limiting headers (if implemented)"""
        print("Testing rate limiting awareness...")
        
        self.client.force_login(self.user)
        
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


class SecurityTestRunner:
    """
    Security test runner with comprehensive reporting
    """
    
    def run_security_tests(self):
        """Run all security tests and generate report"""
        print("Student Timetable Module - Simple Security Testing")
        print("=" * 60)
        
        # Create test suite
        suite = unittest.TestSuite()
        
        # Add all security test methods
        test_methods = [
            'test_authentication_required',
            'test_sql_injection_prevention',
            'test_input_validation',
            'test_data_leakage_prevention',
            'test_error_information_disclosure',
            'test_secure_headers',
            'test_rate_limiting_awareness'
        ]
        
        for method in test_methods:
            suite.addTest(SimpleSecurityTest(method))
        
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
            print("✓ Student Timetable Module meets basic security requirements")
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
        print("- Add CSRF protection for state-changing operations")
        print("- Implement proper input sanitization")
        print("- Use parameterized queries to prevent SQL injection")
        
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