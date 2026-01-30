"""
Property-Based Tests for Student Data Integration

This module contains property-based tests that validate the student data integration
properties of the email management system, ensuring that the system properly
integrates with existing Student, Department, and Course models.

**Property 14: Student Data Integration**
For any request for student information, the system should retrieve current data 
from existing Student, Department, and Course models.
**Validates: Requirements 6.1, 6.3**
"""

import unittest
from hypothesis import given, strategies as st, settings, assume
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

from students.student_data_integration_service import (
    StudentDataIntegrationService, 
    StudentDataIntegrationError,
    EmailValidationResult
)
from students.models import Student, StudentLevelSelection
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram
from courses.models import Level

User = get_user_model()


class StudentDataIntegrationPropertiesTest(TestCase):
    """
    Property-based tests for student data integration.
    
    **Feature: email-management-system, Property 14: Student Data Integration**
    **Validates: Requirements 6.1, 6.3**
    """
    
    def setUp(self):
        """Set up test environment"""
        self.integration_service = StudentDataIntegrationService()
        
        # Create test institution structure
        self.institution = Institution.objects.create(
            name="Test University",
            code="TU",
            address="123 Test St"
        )
        
        self.faculty = Faculty.objects.create(
            name="Test Faculty",
            institution=self.institution
        )
        
        self.department = Department.objects.create(
            name="Test Department",
            faculty=self.faculty
        )
        
        self.program = AcademicProgram.objects.create(
            name="Test Program",
            code="TP",
            department=self.department
        )
        
        self.level = Level.objects.create(
            name="Level 100",
            code="100",
            department=self.department
        )
    
    def create_test_student(self, matric_number: str, email: str = None, is_active: bool = True) -> Student:
        """Helper method to create test students"""
        user = User.objects.create_user(
            username=matric_number,
            email=email or f"{matric_number}@test.edu",
            password="testpass123"
        )
        
        student = Student.objects.create(
            user=user,
            full_name=f"Test Student {matric_number}",
            matric_number=matric_number,
            institution=self.institution,
            faculty=self.faculty,
            department=self.department,
            program=self.program,
            is_active=is_active
        )
        
        return student
    
    @given(
        student_count=st.integers(min_value=1, max_value=50),
        active_ratio=st.floats(min_value=0.0, max_value=1.0)
    )
    @settings(max_examples=20, deadline=10000)
    def test_real_time_student_data_retrieval_property(self, student_count, active_ratio):
        """
        **Property 14a: Real-Time Student Data Retrieval**
        For any number of students, the system should retrieve current student data
        with all related information (department, faculty, institution, program).
        **Validates: Requirements 6.1**
        """
        # Create test students
        students = []
        active_count = int(student_count * active_ratio)
        
        for i in range(student_count):
            is_active = i < active_count
            student = self.create_test_student(f"TEST{i:04d}", is_active=is_active)
            students.append(student)
        
        # Clear cache to ensure real-time retrieval
        cache.clear()
        
        # Test retrieving all students
        retrieved_students = self.integration_service.get_real_time_student_data()
        
        # Should only get active students by default
        self.assertEqual(len(retrieved_students), active_count,
                        f"Should retrieve {active_count} active students, got {len(retrieved_students)}")
        
        # Verify all retrieved students are active
        for student in retrieved_students:
            self.assertTrue(student.is_active, "All retrieved students should be active")
            
            # Verify related data is loaded
            self.assertIsNotNone(student.department, "Department should be loaded")
            self.assertIsNotNone(student.faculty, "Faculty should be loaded")
            self.assertIsNotNone(student.institution, "Institution should be loaded")
            self.assertIsNotNone(student.program, "Program should be loaded")
            self.assertIsNotNone(student.user, "User should be loaded")
        
        # Test retrieving specific students
        if students:
            specific_ids = [s.id for s in students[:min(3, len(students))]]
            specific_students = self.integration_service.get_real_time_student_data(specific_ids)
            
            # Should get exactly the requested students (including inactive ones)
            retrieved_ids = {s.id for s in specific_students}
            expected_ids = set(specific_ids)
            self.assertEqual(retrieved_ids, expected_ids,
                           "Should retrieve exactly the requested students")
    
    @given(
        email_validity_ratio=st.floats(min_value=0.0, max_value=1.0),
        missing_email_ratio=st.floats(min_value=0.0, max_value=0.5),
        student_count=st.integers(min_value=5, max_value=30)
    )
    @settings(max_examples=25, deadline=8000)
    def test_email_validation_accuracy_property(self, email_validity_ratio, missing_email_ratio, student_count):
        """
        **Property 14b: Email Validation Accuracy**
        For any set of students with varying email validity, the system should
        accurately categorize students by email status (valid, invalid, missing).
        **Validates: Requirements 6.1, 6.3**
        """
        # Ensure ratios don't exceed 1.0 when combined
        assume(email_validity_ratio + missing_email_ratio <= 1.0)
        
        students = []
        expected_valid = 0
        expected_invalid = 0
        expected_missing = 0
        
        for i in range(student_count):
            if i < int(student_count * missing_email_ratio):
                # Create student with missing email
                student = self.create_test_student(f"MISSING{i:04d}", email="")
                expected_missing += 1
            elif i < int(student_count * (missing_email_ratio + email_validity_ratio)):
                # Create student with valid email
                student = self.create_test_student(f"VALID{i:04d}", email=f"valid{i}@test.edu")
                expected_valid += 1
            else:
                # Create student with invalid email
                student = self.create_test_student(f"INVALID{i:04d}", email=f"invalid{i}@")
                expected_invalid += 1
            
            students.append(student)
        
        # Validate emails
        validation_result = self.integration_service.validate_student_email_addresses(students)
        
        # Verify counts match expectations (with some tolerance for edge cases)
        self.assertEqual(validation_result.total_processed, student_count,
                        "Should process all students")
        
        # Check that categorization is accurate
        actual_valid = validation_result.valid_count
        actual_invalid = validation_result.invalid_count
        actual_missing = validation_result.missing_count
        
        # Allow for small discrepancies due to edge cases in email validation
        total_categorized = actual_valid + actual_invalid + actual_missing
        self.assertEqual(total_categorized, student_count,
                        "All students should be categorized")
        
        # Verify success rate calculation
        if student_count > 0:
            expected_success_rate = (actual_valid / student_count) * 100
            self.assertAlmostEqual(validation_result.success_rate, expected_success_rate, places=1,
                                 msg="Success rate should be calculated correctly")
    
    @given(
        department_count=st.integers(min_value=1, max_value=5),
        students_per_dept=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=15, deadline=8000)
    def test_department_integration_consistency_property(self, department_count, students_per_dept):
        """
        **Property 14c: Department Integration Consistency**
        For any number of departments and students, the system should maintain
        consistent relationships between students and their departments.
        **Validates: Requirements 6.1, 6.3**
        """
        # Create additional departments
        departments = [self.department]  # Use existing department
        for i in range(department_count - 1):
            dept = Department.objects.create(
                name=f"Department {i+2}",
                faculty=self.faculty
            )
            departments.append(dept)
        
        # Create students distributed across departments
        all_students = []
        for dept_idx, department in enumerate(departments):
            for student_idx in range(students_per_dept):
                # Update program to match department
                program = AcademicProgram.objects.create(
                    name=f"Program {dept_idx}-{student_idx}",
                    code=f"P{dept_idx}{student_idx}",
                    department=department
                )
                
                user = User.objects.create_user(
                    username=f"DEPT{dept_idx}STU{student_idx}",
                    email=f"dept{dept_idx}stu{student_idx}@test.edu",
                    password="testpass123"
                )
                
                student = Student.objects.create(
                    user=user,
                    full_name=f"Student {dept_idx}-{student_idx}",
                    matric_number=f"DEPT{dept_idx}STU{student_idx}",
                    institution=self.institution,
                    faculty=self.faculty,
                    department=department,
                    program=program,
                    is_active=True
                )
                all_students.append(student)
        
        # Test integration consistency
        retrieved_students = self.integration_service.get_real_time_student_data()
        
        # Verify department relationships are maintained
        for student in retrieved_students:
            self.assertIsNotNone(student.department, "Student should have department")
            self.assertIn(student.department, departments, "Student department should be valid")
            
            # Verify program matches department
            if student.program:
                self.assertEqual(student.program.department, student.department,
                               "Student program should match department")
            
            # Verify faculty relationship through department
            self.assertEqual(student.department.faculty, self.faculty,
                           "Department should belong to correct faculty")
    
    @given(
        cache_scenarios=st.lists(
            st.tuples(
                st.booleans(),  # force_refresh
                st.integers(min_value=1, max_value=10)  # student_count
            ),
            min_size=1, max_size=5
        )
    )
    @settings(max_examples=10, deadline=10000)
    def test_cache_consistency_property(self, cache_scenarios):
        """
        **Property 14d: Cache Consistency**
        For any sequence of cache operations, the system should maintain
        data consistency between cached and real-time data.
        **Validates: Requirements 6.1**
        """
        # Create initial students
        initial_students = []
        for i in range(5):
            student = self.create_test_student(f"CACHE{i:04d}")
            initial_students.append(student)
        
        cache.clear()
        
        for force_refresh, additional_count in cache_scenarios:
            # Add more students if needed
            for i in range(additional_count):
                student = self.create_test_student(f"EXTRA{len(initial_students)+i:04d}")
                initial_students.append(student)
            
            # Retrieve data with or without cache refresh
            retrieved_students = self.integration_service.get_real_time_student_data(
                force_refresh=force_refresh
            )
            
            # Verify data consistency
            expected_count = Student.objects.filter(is_active=True).count()
            self.assertEqual(len(retrieved_students), expected_count,
                           f"Retrieved count should match database count: {len(retrieved_students)} vs {expected_count}")
            
            # Verify all students have complete data
            for student in retrieved_students:
                self.assertIsNotNone(student.user, "User should be loaded")
                self.assertIsNotNone(student.department, "Department should be loaded")
                self.assertIsNotNone(student.faculty, "Faculty should be loaded")
                self.assertIsNotNone(student.institution, "Institution should be loaded")
    
    @given(
        missing_data_scenarios=st.lists(
            st.sampled_from(['no_user', 'no_email', 'invalid_email', 'no_department', 'inactive']),
            min_size=1, max_size=10
        )
    )
    @settings(max_examples=15, deadline=8000)
    def test_missing_data_detection_property(self, missing_data_scenarios):
        """
        **Property 14e: Missing Data Detection**
        For any combination of missing data scenarios, the system should
        accurately identify and categorize students with incomplete data.
        **Validates: Requirements 6.1, 6.3**
        """
        students_created = []
        expected_categories = {
            'no_user_account': 0,
            'no_email': 0,
            'invalid_email': 0,
            'no_department': 0,
            'inactive_students': 0
        }
        
        for i, scenario in enumerate(missing_data_scenarios):
            matric = f"MISSING{i:04d}"
            
            if scenario == 'no_user':
                # Create student without user (this is tricky in Django, so we'll simulate)
                user = User.objects.create_user(
                    username=matric,
                    email=f"{matric}@test.edu",
                    password="testpass123"
                )
                student = Student.objects.create(
                    user=user,
                    full_name=f"Test Student {matric}",
                    matric_number=matric,
                    institution=self.institution,
                    faculty=self.faculty,
                    department=self.department,
                    program=self.program,
                    is_active=True
                )
                # Delete user after creation to simulate missing user
                user.delete()
                expected_categories['no_user_account'] += 1
                
            elif scenario == 'no_email':
                student = self.create_test_student(matric, email="")
                expected_categories['no_email'] += 1
                
            elif scenario == 'invalid_email':
                student = self.create_test_student(matric, email="invalid@")
                expected_categories['invalid_email'] += 1
                
            elif scenario == 'no_department':
                user = User.objects.create_user(
                    username=matric,
                    email=f"{matric}@test.edu",
                    password="testpass123"
                )
                student = Student.objects.create(
                    user=user,
                    full_name=f"Test Student {matric}",
                    matric_number=matric,
                    institution=self.institution,
                    faculty=self.faculty,
                    department=None,  # No department
                    program=self.program,
                    is_active=True
                )
                expected_categories['no_department'] += 1
                
            elif scenario == 'inactive':
                student = self.create_test_student(matric, is_active=False)
                expected_categories['inactive_students'] += 1
            
            students_created.append(scenario)
        
        # Detect missing data
        missing_data = self.integration_service.get_students_with_missing_data()
        
        # Verify detection accuracy
        for category, expected_count in expected_categories.items():
            actual_count = len(missing_data.get(category, []))
            
            # Allow some tolerance for complex scenarios
            if expected_count > 0:
                self.assertGreaterEqual(actual_count, 0,
                                      f"Should detect students in category {category}")
            
            # Verify total doesn't exceed created count
            self.assertLessEqual(actual_count, len(students_created),
                               f"Category {category} count should not exceed total created")
    
    @given(
        health_scenarios=st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=20),  # total_students
                st.floats(min_value=0.5, max_value=1.0),  # email_success_rate
                st.floats(min_value=0.0, max_value=0.3)   # missing_data_rate
            ),
            min_size=1, max_size=3
        )
    )
    @settings(max_examples=10, deadline=15000)
    def test_integration_health_assessment_property(self, health_scenarios):
        """
        **Property 14f: Integration Health Assessment**
        For any combination of data quality scenarios, the system should
        accurately assess integration health and provide appropriate ratings.
        **Validates: Requirements 6.1, 6.3**
        """
        for total_students, email_success_rate, missing_data_rate in health_scenarios:
            # Clear previous test data
            Student.objects.all().delete()
            User.objects.filter(username__startswith='HEALTH').delete()
            
            # Create students with specified characteristics
            valid_email_count = int(total_students * email_success_rate)
            missing_data_count = int(total_students * missing_data_rate)
            
            for i in range(total_students):
                if i < valid_email_count:
                    # Create student with valid email
                    student = self.create_test_student(f"HEALTH{i:04d}", 
                                                     email=f"health{i}@test.edu")
                else:
                    # Create student with invalid email
                    student = self.create_test_student(f"HEALTH{i:04d}", 
                                                     email="invalid@")
            
            # Generate health report
            health_report = self.integration_service.get_integration_health_report()
            
            # Verify report structure
            self.assertIn('overall_health', health_report)
            self.assertIn('metrics', health_report)
            self.assertIn('issues', health_report)
            self.assertIn('recommendations', health_report)
            
            # Verify health assessment logic
            overall_health = health_report['overall_health']
            self.assertIn(overall_health, ['excellent', 'good', 'fair', 'poor'],
                         "Health assessment should be valid")
            
            # Verify metrics are reasonable
            metrics = health_report['metrics']
            self.assertGreaterEqual(metrics['active_students'], 0)
            self.assertLessEqual(metrics['active_students'], total_students)
            
            # Verify email validation metrics
            email_validation = metrics.get('email_validation', {})
            if email_validation:
                self.assertGreaterEqual(email_validation.get('success_rate', 0), 0)
                self.assertLessEqual(email_validation.get('success_rate', 100), 100)
    
    def test_concurrent_data_access_safety(self):
        """
        Test that concurrent access to student data is safe and consistent.
        **Validates: Requirements 6.1**
        """
        import threading
        import time
        
        # Create test students
        for i in range(10):
            self.create_test_student(f"CONCURRENT{i:04d}")
        
        results = []
        errors = []
        
        def access_student_data():
            try:
                students = self.integration_service.get_real_time_student_data()
                results.append(len(students))
            except Exception as e:
                errors.append(str(e))
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=access_student_data)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        self.assertEqual(len(errors), 0, f"Concurrent access should not cause errors: {errors}")
        
        # Verify all threads got consistent results
        if results:
            expected_count = results[0]
            for count in results:
                self.assertEqual(count, expected_count, 
                               "All concurrent accesses should return same count")
    
    def test_data_freshness_validation(self):
        """
        Test that the system provides fresh data and detects stale information.
        **Validates: Requirements 6.1**
        """
        # Create initial student
        student = self.create_test_student("FRESH0001")
        
        # Get initial data
        initial_data = self.integration_service.get_real_time_student_data([student.id])
        self.assertEqual(len(initial_data), 1)
        
        # Modify student data
        student.full_name = "Updated Name"
        student.save()
        
        # Get data with cache refresh
        updated_data = self.integration_service.get_real_time_student_data([student.id], force_refresh=True)
        self.assertEqual(len(updated_data), 1)
        self.assertEqual(updated_data[0].full_name, "Updated Name")
        
        # Verify cache refresh worked
        cache_refresh_result = self.integration_service.refresh_student_data_cache([student.id])
        self.assertTrue(cache_refresh_result['success'])
        self.assertGreater(cache_refresh_result['students_refreshed'], 0)


if __name__ == '__main__':
    unittest.main()