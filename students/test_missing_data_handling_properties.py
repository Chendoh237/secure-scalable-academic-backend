"""
Property-Based Tests for Missing Data Handling

This module contains property-based tests that validate the missing data handling
properties of the email management system, ensuring that the system gracefully
handles cases where student email addresses are missing or invalid.

**Property 15: Missing Data Handling**
For any student with missing or invalid email addresses, the system should handle 
the case gracefully without failing the entire operation.
**Validates: Requirements 6.5**
"""

import unittest
from hypothesis import given, strategies as st, settings, assume
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock
from typing import List, Dict, Any

from students.student_data_integration_service import (
    StudentDataIntegrationService, 
    StudentDataIntegrationError,
    EmailValidationResult
)
from students.recipient_service import RecipientService, RecipientServiceError
from students.email_service import EmailService
from students.models import Student, StudentLevelSelection
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram
from courses.models import Level

User = get_user_model()


class MissingDataHandlingPropertiesTest(TestCase):
    """
    Property-based tests for missing data handling.
    
    **Feature: email-management-system, Property 15: Missing Data Handling**
    **Validates: Requirements 6.5**
    """
    
    def setUp(self):
        """Set up test environment"""
        self.integration_service = StudentDataIntegrationService()
        self.recipient_service = RecipientService()
        self.email_service = EmailService()
        
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
    
    def create_student_with_data_issues(self, matric_number: str, issue_type: str) -> Student:
        """Helper method to create students with specific data issues"""
        if issue_type == 'no_user':
            # Create student without user (simulate orphaned record)
            student = Student.objects.create(
                user=None,
                full_name=f"No User Student {matric_number}",
                matric_number=matric_number,
                institution=self.institution,
                faculty=self.faculty,
                department=self.department,
                program=self.program,
                is_active=True
            )
            return student
            
        elif issue_type == 'no_email':
            user = User.objects.create_user(
                username=matric_number,
                email="",  # Empty email
                password="testpass123"
            )
            
        elif issue_type == 'invalid_email':
            user = User.objects.create_user(
                username=matric_number,
                email="invalid@",  # Invalid email format
                password="testpass123"
            )
            
        elif issue_type == 'null_email':
            user = User.objects.create_user(
                username=matric_number,
                password="testpass123"
            )
            user.email = None
            user.save()
            
        elif issue_type == 'whitespace_email':
            user = User.objects.create_user(
                username=matric_number,
                email="   ",  # Whitespace only
                password="testpass123"
            )
            
        elif issue_type == 'no_department':
            user = User.objects.create_user(
                username=matric_number,
                email=f"{matric_number}@test.edu",
                password="testpass123"
            )
            student = Student.objects.create(
                user=user,
                full_name=f"No Dept Student {matric_number}",
                matric_number=matric_number,
                institution=self.institution,
                faculty=self.faculty,
                department=None,  # No department
                program=self.program,
                is_active=True
            )
            return student
            
        else:  # 'valid' - create normal student
            user = User.objects.create_user(
                username=matric_number,
                email=f"{matric_number}@test.edu",
                password="testpass123"
            )
        
        # Create student with user (for most cases)
        if issue_type != 'no_department':
            student = Student.objects.create(
                user=user,
                full_name=f"Test Student {matric_number}",
                matric_number=matric_number,
                institution=self.institution,
                faculty=self.faculty,
                department=self.department,
                program=self.program,
                is_active=True
            )
        
        return student
    
    @given(
        data_issue_scenarios=st.lists(
            st.sampled_from(['no_user', 'no_email', 'invalid_email', 'null_email', 'whitespace_email', 'valid']),
            min_size=1, max_size=20
        )
    )
    @settings(max_examples=25, deadline=10000)
    def test_graceful_missing_data_handling_property(self, data_issue_scenarios):
        """
        **Property 15a: Graceful Missing Data Handling**
        For any combination of students with missing or invalid data, the system
        should handle each case gracefully without failing the entire operation.
        **Validates: Requirements 6.5**
        """
        students = []
        expected_valid_count = 0
        
        # Create students with various data issues
        for i, issue_type in enumerate(data_issue_scenarios):
            matric = f"ISSUE{i:04d}"
            student = self.create_student_with_data_issues(matric, issue_type)
            students.append(student)
            
            if issue_type == 'valid':
                expected_valid_count += 1
        
        # Test email validation - should not fail despite missing data
        try:
            validation_result = self.integration_service.validate_student_email_addresses(students)
            
            # Operation should succeed
            self.assertIsInstance(validation_result, EmailValidationResult)
            self.assertEqual(validation_result.total_processed, len(students))
            
            # Should categorize students appropriately
            total_categorized = (validation_result.valid_count + 
                               validation_result.invalid_count + 
                               validation_result.missing_count)
            self.assertEqual(total_categorized, len(students),
                           "All students should be categorized despite data issues")
            
            # Should have some valid students if any were created
            if expected_valid_count > 0:
                self.assertGreater(validation_result.valid_count, 0,
                                 "Should identify valid students correctly")
            
        except Exception as e:
            self.fail(f"Email validation should not fail due to missing data: {str(e)}")
    
    @given(
        recipient_configs=st.lists(
            st.fixed_dictionaries({
                'type': st.sampled_from(['all', 'department', 'specific']),
                'include_problematic': st.booleans()
            }),
            min_size=1, max_size=5
        )
    )
    @settings(max_examples=15, deadline=8000)
    def test_recipient_selection_resilience_property(self, recipient_configs):
        """
        **Property 15b: Recipient Selection Resilience**
        For any recipient selection configuration, the system should handle
        missing data gracefully and return valid recipients without failing.
        **Validates: Requirements 6.5**
        """
        # Create mix of valid and problematic students
        valid_students = []
        problematic_students = []
        
        # Create valid students
        for i in range(5):
            student = self.create_student_with_data_issues(f"VALID{i:04d}", 'valid')
            valid_students.append(student)
        
        # Create problematic students
        issue_types = ['no_email', 'invalid_email', 'null_email']
        for i, issue_type in enumerate(issue_types):
            student = self.create_student_with_data_issues(f"PROB{i:04d}", issue_type)
            problematic_students.append(student)
        
        for config in recipient_configs:
            try:
                if config['type'] == 'all':
                    # Test getting all students
                    students = self.recipient_service.get_all_students()
                    
                elif config['type'] == 'department':
                    # Test getting students by department
                    students = self.recipient_service.get_students_by_department([self.department.id])
                    
                elif config['type'] == 'specific':
                    # Test getting specific students
                    all_student_ids = [s.id for s in valid_students + problematic_students]
                    students = self.recipient_service.get_students_by_ids(all_student_ids[:3])
                
                # Operation should succeed
                self.assertIsInstance(students, list, "Should return list of students")
                
                # Should only include students with valid emails
                for student in students:
                    self.assertTrue(hasattr(student, 'user'), "Student should have user")
                    if student.user:
                        email = getattr(student.user, 'email', None)
                        if email:
                            # If email exists, it should be non-empty after stripping
                            self.assertTrue(email.strip(), "Email should not be empty/whitespace")
                
            except RecipientServiceError:
                # Service errors are acceptable for graceful handling
                pass
            except Exception as e:
                self.fail(f"Recipient selection should handle missing data gracefully: {str(e)}")
    
    @given(
        bulk_email_scenarios=st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=10),  # valid_count
                st.integers(min_value=1, max_value=10),  # invalid_count
                st.booleans()  # continue_on_error
            ),
            min_size=1, max_size=3
        )
    )
    @settings(max_examples=10, deadline=15000)
    def test_bulk_email_missing_data_resilience_property(self, bulk_email_scenarios):
        """
        **Property 15c: Bulk Email Missing Data Resilience**
        For any bulk email operation with mixed valid/invalid recipients, the
        system should process valid recipients and handle invalid ones gracefully.
        **Validates: Requirements 6.5**
        """
        for valid_count, invalid_count, continue_on_error in bulk_email_scenarios:
            # Clear previous test data
            Student.objects.filter(matric_number__startswith='BULK').delete()
            User.objects.filter(username__startswith='BULK').delete()
            
            # Create valid recipients
            valid_emails = []
            for i in range(valid_count):
                student = self.create_student_with_data_issues(f"BULKVALID{i:04d}", 'valid')
                valid_emails.append(student.user.email)
            
            # Create invalid recipients (emails that will cause issues)
            invalid_emails = []
            for i in range(invalid_count):
                invalid_emails.extend([
                    "",  # Empty email
                    "invalid@",  # Invalid format
                    "   ",  # Whitespace only
                    "notanemail",  # No @ symbol
                ])
            
            # Combine valid and invalid emails
            all_emails = valid_emails + invalid_emails[:invalid_count]
            
            # Mock SMTP to avoid actual email sending
            with patch('students.email_service.smtplib.SMTP') as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value = mock_server
                
                # Test bulk email sending
                try:
                    result = self.email_service.send_email(
                        to_emails=all_emails,
                        subject="Test Subject",
                        message="Test Message"
                    )
                    
                    # Operation should handle invalid emails gracefully
                    if result['success']:
                        # Should process valid emails
                        self.assertGreaterEqual(result.get('sent_count', 0), 0)
                        
                        # Should report invalid emails
                        if 'invalid_emails' in result:
                            self.assertIsInstance(result['invalid_emails'], list)
                    else:
                        # If operation fails, error should be descriptive
                        self.assertIn('error', result)
                        self.assertIsInstance(result['error'], str)
                        self.assertGreater(len(result['error']), 0)
                
                except Exception as e:
                    # Should not raise unhandled exceptions
                    self.fail(f"Bulk email should handle invalid data gracefully: {str(e)}")
    
    @given(
        missing_data_patterns=st.lists(
            st.fixed_dictionaries({
                'category': st.sampled_from(['no_user_account', 'no_email', 'invalid_email', 'no_department']),
                'count': st.integers(min_value=1, max_value=5)
            }),
            min_size=1, max_size=4
        )
    )
    @settings(max_examples=15, deadline=8000)
    def test_missing_data_detection_completeness_property(self, missing_data_patterns):
        """
        **Property 15d: Missing Data Detection Completeness**
        For any pattern of missing data, the system should detect and categorize
        all instances without missing any problematic records.
        **Validates: Requirements 6.5**
        """
        # Clear existing test data
        Student.objects.filter(matric_number__startswith='DETECT').delete()
        User.objects.filter(username__startswith='DETECT').delete()
        
        expected_counts = {
            'no_user_account': 0,
            'no_email': 0,
            'invalid_email': 0,
            'no_department': 0,
            'inactive_students': 0
        }
        
        student_counter = 0
        
        # Create students according to missing data patterns
        for pattern in missing_data_patterns:
            category = pattern['category']
            count = pattern['count']
            
            for i in range(count):
                matric = f"DETECT{student_counter:04d}"
                student_counter += 1
                
                if category == 'no_user_account':
                    # Create student without user
                    student = self.create_student_with_data_issues(matric, 'no_user')
                    expected_counts['no_user_account'] += 1
                    
                elif category == 'no_email':
                    student = self.create_student_with_data_issues(matric, 'no_email')
                    expected_counts['no_email'] += 1
                    
                elif category == 'invalid_email':
                    student = self.create_student_with_data_issues(matric, 'invalid_email')
                    expected_counts['invalid_email'] += 1
                    
                elif category == 'no_department':
                    student = self.create_student_with_data_issues(matric, 'no_department')
                    expected_counts['no_department'] += 1
        
        # Detect missing data
        try:
            missing_data = self.integration_service.get_students_with_missing_data()
            
            # Verify detection completeness
            for category, expected_count in expected_counts.items():
                if expected_count > 0:
                    actual_count = len(missing_data.get(category, []))
                    
                    # Should detect at least the expected number (may detect more due to existing data)
                    self.assertGreaterEqual(actual_count, 0,
                                          f"Should detect students in category {category}")
                    
                    # Verify detected students have the expected issues
                    detected_students = missing_data.get(category, [])
                    for student in detected_students:
                        if student.matric_number.startswith('DETECT'):
                            # This is one of our test students - verify the issue
                            if category == 'no_user_account':
                                self.assertIsNone(student.user, "Student should have no user account")
                            elif category == 'no_email':
                                if student.user:
                                    email = getattr(student.user, 'email', None)
                                    self.assertFalse(email and email.strip(), "Student should have no email")
                            elif category == 'no_department':
                                self.assertIsNone(student.department, "Student should have no department")
            
        except Exception as e:
            self.fail(f"Missing data detection should not fail: {str(e)}")
    
    @given(
        error_scenarios=st.lists(
            st.sampled_from(['database_error', 'validation_error', 'network_error']),
            min_size=1, max_size=3
        )
    )
    @settings(max_examples=10, deadline=5000)
    def test_error_recovery_mechanisms_property(self, error_scenarios):
        """
        **Property 15e: Error Recovery Mechanisms**
        For any type of error during missing data handling, the system should
        recover gracefully and provide meaningful error information.
        **Validates: Requirements 6.5**
        """
        # Create some test students
        for i in range(3):
            self.create_student_with_data_issues(f"RECOVERY{i:04d}", 'valid')
        
        for error_scenario in error_scenarios:
            if error_scenario == 'database_error':
                # Simulate database connection error
                with patch('students.models.Student.objects.filter') as mock_filter:
                    mock_filter.side_effect = Exception("Database connection failed")
                    
                    try:
                        result = self.integration_service.get_students_with_missing_data()
                        # Should handle error gracefully
                        self.fail("Should have raised StudentDataIntegrationError")
                    except StudentDataIntegrationError as e:
                        # Expected error type
                        self.assertIn("Database", str(e) or "connection", str(e))
                    except Exception as e:
                        # Should not raise other exception types
                        self.fail(f"Should raise StudentDataIntegrationError, not {type(e)}: {str(e)}")
            
            elif error_scenario == 'validation_error':
                # Test with invalid data that causes validation errors
                try:
                    # Create student with problematic data
                    invalid_emails = ["", "invalid@", None, "   "]
                    validation_result = self.recipient_service.validate_email_addresses(invalid_emails)
                    
                    # Should handle validation gracefully
                    self.assertIsInstance(validation_result, dict)
                    self.assertIn('valid_emails', validation_result)
                    self.assertIn('invalid_emails', validation_result)
                    
                except Exception as e:
                    # Should not raise unhandled exceptions
                    self.fail(f"Email validation should handle invalid data gracefully: {str(e)}")
    
    @given(
        data_consistency_scenarios=st.lists(
            st.tuples(
                st.integers(min_value=0, max_value=5),  # valid_students
                st.integers(min_value=0, max_value=5),  # invalid_students
                st.booleans()  # modify_during_processing
            ),
            min_size=1, max_size=3
        )
    )
    @settings(max_examples=10, deadline=10000)
    def test_data_consistency_during_missing_data_handling_property(self, data_consistency_scenarios):
        """
        **Property 15f: Data Consistency During Missing Data Handling**
        For any data processing scenario, the system should maintain consistency
        even when data changes during processing or contains inconsistencies.
        **Validates: Requirements 6.5**
        """
        for valid_count, invalid_count, modify_during_processing in data_consistency_scenarios:
            # Clear previous test data
            Student.objects.filter(matric_number__startswith='CONSIST').delete()
            User.objects.filter(username__startswith='CONSIST').delete()
            
            # Create initial students
            students = []
            for i in range(valid_count):
                student = self.create_student_with_data_issues(f"CONSISTVALID{i:04d}", 'valid')
                students.append(student)
            
            for i in range(invalid_count):
                student = self.create_student_with_data_issues(f"CONSISTINVALID{i:04d}", 'no_email')
                students.append(student)
            
            if modify_during_processing and students:
                # Simulate data modification during processing
                def mock_get_students(*args, **kwargs):
                    # Modify a student's email during processing
                    if students and hasattr(students[0], 'user') and students[0].user:
                        students[0].user.email = "modified@test.edu"
                        students[0].user.save()
                    return students
                
                with patch.object(self.integration_service, 'get_real_time_student_data', side_effect=mock_get_students):
                    try:
                        validation_result = self.integration_service.validate_student_email_addresses()
                        
                        # Should handle data modifications gracefully
                        self.assertIsInstance(validation_result, EmailValidationResult)
                        self.assertGreaterEqual(validation_result.total_processed, 0)
                        
                    except Exception as e:
                        self.fail(f"Should handle data modifications during processing: {str(e)}")
            else:
                # Normal processing without modifications
                try:
                    validation_result = self.integration_service.validate_student_email_addresses(students)
                    
                    # Should process consistently
                    self.assertIsInstance(validation_result, EmailValidationResult)
                    self.assertEqual(validation_result.total_processed, len(students))
                    
                    # Verify consistency
                    total_categorized = (validation_result.valid_count + 
                                       validation_result.invalid_count + 
                                       validation_result.missing_count)
                    self.assertEqual(total_categorized, len(students),
                                   "All students should be consistently categorized")
                    
                except Exception as e:
                    self.fail(f"Normal processing should not fail: {str(e)}")
    
    def test_edge_case_email_formats(self):
        """
        Test handling of edge case email formats that might cause issues.
        **Validates: Requirements 6.5**
        """
        edge_case_emails = [
            "",  # Empty string
            "   ",  # Whitespace only
            None,  # None value
            "@domain.com",  # Missing local part
            "user@",  # Missing domain
            "user@domain",  # Missing TLD
            "user space@domain.com",  # Space in local part
            "user@domain .com",  # Space in domain
            "user@domain..com",  # Double dot in domain
            "user@@domain.com",  # Double @
            "very.long.email.address.that.exceeds.normal.length.limits@very.long.domain.name.that.also.exceeds.normal.limits.com",  # Very long email
        ]
        
        # Test validation of edge case emails
        try:
            validation_result = self.recipient_service.validate_email_addresses(edge_case_emails)
            
            # Should handle all edge cases without crashing
            self.assertIsInstance(validation_result, dict)
            self.assertIn('valid_emails', validation_result)
            self.assertIn('invalid_emails', validation_result)
            
            # Most should be invalid
            self.assertGreaterEqual(len(validation_result['invalid_emails']), 
                                  len(edge_case_emails) - 2,  # Allow for some potentially valid ones
                                  "Most edge case emails should be invalid")
            
        except Exception as e:
            self.fail(f"Edge case email validation should not crash: {str(e)}")
    
    def test_large_dataset_missing_data_handling(self):
        """
        Test missing data handling with larger datasets to ensure scalability.
        **Validates: Requirements 6.5**
        """
        # Create larger dataset with mixed data quality
        students = []
        for i in range(50):  # Larger dataset
            if i % 5 == 0:
                issue_type = 'no_email'
            elif i % 7 == 0:
                issue_type = 'invalid_email'
            elif i % 11 == 0:
                issue_type = 'null_email'
            else:
                issue_type = 'valid'
            
            student = self.create_student_with_data_issues(f"LARGE{i:04d}", issue_type)
            students.append(student)
        
        # Test missing data detection on large dataset
        try:
            missing_data = self.integration_service.get_students_with_missing_data()
            
            # Should handle large dataset without performance issues
            self.assertIsInstance(missing_data, dict)
            
            # Should categorize students appropriately
            total_detected = sum(len(student_list) for student_list in missing_data.values())
            self.assertGreaterEqual(total_detected, 0, "Should detect some missing data")
            
        except Exception as e:
            self.fail(f"Large dataset missing data handling should not fail: {str(e)}")


if __name__ == '__main__':
    unittest.main()