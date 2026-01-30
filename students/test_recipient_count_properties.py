"""
Property-Based Tests for Recipient Count Accuracy

This module contains property-based tests to validate that recipient count
calculations are accurate across different selection criteria.

**Validates: Requirements 2.6**
"""

import pytest
from hypothesis import given, strategies as st, assume
from django.test import TestCase
from django.contrib.auth import get_user_model
from students.models import Student
from institutions.models import Department, Faculty, Institution
from students.recipient_service import RecipientService, recipient_service

User = get_user_model()


class TestRecipientCountAccuracy(TestCase):
    """
    Property-based tests for recipient count accuracy.
    
    **Property 6: Recipient Count Accuracy**
    **Validates: Requirements 2.6**
    """
    
    def setUp(self):
        """Set up test data"""
        # Create institution hierarchy
        self.institution = Institution.objects.create(
            name="Test University",
            code="TU"
        )
        
        self.faculty = Faculty.objects.create(
            name="Test Faculty",
            institution=self.institution
        )
        
        # Create departments
        self.dept1 = Department.objects.create(
            name="Computer Science",
            faculty=self.faculty,
            institution=self.institution
        )
        
        self.dept2 = Department.objects.create(
            name="Mathematics",
            faculty=self.faculty,
            institution=self.institution
        )
        
        # Create users and students
        self.students = []
        for i in range(10):
            user = User.objects.create_user(
                username=f'student{i}',
                email=f'student{i}@test.com',
                password='testpass123'
            )
            
            # Alternate between departments
            dept = self.dept1 if i % 2 == 0 else self.dept2
            
            student = Student.objects.create(
                user=user,
                matricule=f'STU{i:03d}',
                full_name=f'Student {i}',
                department=dept,
                faculty=self.faculty,
                institution=self.institution,
                level=f'{(i % 4 + 1)}00',  # Levels: 100, 200, 300, 400
                is_active=True
            )
            self.students.append(student)
    
    @given(
        department_selection=st.lists(
            st.integers(min_value=0, max_value=1),
            min_size=1,
            max_size=2
        )
    )
    def test_department_recipient_count_accuracy(self, department_selection):
        """
        Property: Department-based recipient count must match actual filtered students
        
        **Validates: Requirements 2.6**
        """
        # Map selection indices to actual department IDs
        available_depts = [self.dept1, self.dept2]
        selected_dept_ids = [available_depts[i].id for i in department_selection]
        
        # Build recipient configuration
        recipient_config = {
            'type': 'department',
            'department_ids': selected_dept_ids
        }
        
        # Get recipients and count from service
        recipients, metadata = recipient_service.build_recipient_list(recipient_config)
        service_count = len(recipients)
        
        # Calculate expected count by direct database query
        expected_students = Student.objects.filter(
            department_id__in=selected_dept_ids,
            is_active=True,
            user__email__isnull=False
        ).exclude(user__email='')
        expected_count = expected_students.count()
        
        # Property: Service count must match expected count
        assert service_count == expected_count, (
            f"Recipient count mismatch for departments {selected_dept_ids}: "
            f"service returned {service_count}, expected {expected_count}"
        )
        
        # Property: All returned recipients must have valid email addresses
        for recipient in recipients:
            assert '@' in recipient, f"Invalid email format: {recipient}"
            assert recipient.strip() != '', "Empty email address found"
    
    @given(
        level_selection=st.lists(
            st.sampled_from(['100', '200', '300', '400']),
            min_size=1,
            max_size=4,
            unique=True
        )
    )
    def test_level_recipient_count_accuracy(self, level_selection):
        """
        Property: Level-based recipient count must match actual filtered students
        
        **Validates: Requirements 2.6**
        """
        # Build recipient configuration
        recipient_config = {
            'type': 'level',
            'level_ids': level_selection
        }
        
        # Get recipients and count from service
        recipients, metadata = recipient_service.build_recipient_list(recipient_config)
        service_count = len(recipients)
        
        # Calculate expected count by direct database query
        expected_students = Student.objects.filter(
            level__in=level_selection,
            is_active=True,
            user__email__isnull=False
        ).exclude(user__email='')
        expected_count = expected_students.count()
        
        # Property: Service count must match expected count
        assert service_count == expected_count, (
            f"Recipient count mismatch for levels {level_selection}: "
            f"service returned {service_count}, expected {expected_count}"
        )
        
        # Property: All recipients must belong to selected levels
        actual_levels = set(
            Student.objects.filter(
                user__email__in=recipients,
                is_active=True
            ).values_list('level', flat=True)
        )
        
        for level in actual_levels:
            assert level in level_selection, (
                f"Student with level {level} found in results, "
                f"but only levels {level_selection} were selected"
            )
    
    @given(
        custom_emails=st.lists(
            st.text(
                alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
                min_size=3,
                max_size=10
            ).map(lambda x: f"{x}@test.com"),
            min_size=1,
            max_size=5,
            unique=True
        )
    )
    def test_custom_email_recipient_count_accuracy(self, custom_emails):
        """
        Property: Custom email recipient count must match provided email list
        
        **Validates: Requirements 2.6**
        """
        # Filter out any invalid emails
        valid_emails = [email for email in custom_emails if '@' in email and '.' in email]
        assume(len(valid_emails) > 0)  # Skip test if no valid emails
        
        # Build recipient configuration
        recipient_config = {
            'type': 'custom',
            'emails': valid_emails
        }
        
        # Get recipients and count from service
        recipients, metadata = recipient_service.build_recipient_list(recipient_config)
        service_count = len(recipients)
        
        # Property: Service count must match provided email count
        assert service_count == len(valid_emails), (
            f"Recipient count mismatch for custom emails: "
            f"service returned {service_count}, expected {len(valid_emails)}"
        )
        
        # Property: All provided emails must be in recipients
        for email in valid_emails:
            assert email in recipients, f"Custom email {email} not found in recipients"
        
        # Property: No extra emails should be added
        for recipient in recipients:
            assert recipient in valid_emails, f"Unexpected recipient {recipient} found"
    
    def test_all_students_recipient_count_accuracy(self):
        """
        Property: 'All students' selection must include all active students with emails
        
        **Validates: Requirements 2.6**
        """
        # Build recipient configuration for all students
        recipient_config = {
            'type': 'all'
        }
        
        # Get recipients and count from service
        recipients, metadata = recipient_service.build_recipient_list(recipient_config)
        service_count = len(recipients)
        
        # Calculate expected count by direct database query
        expected_students = Student.objects.filter(
            is_active=True,
            user__email__isnull=False
        ).exclude(user__email='')
        expected_count = expected_students.count()
        
        # Property: Service count must match expected count
        assert service_count == expected_count, (
            f"Recipient count mismatch for all students: "
            f"service returned {service_count}, expected {expected_count}"
        )
        
        # Property: All active students with emails must be included
        expected_emails = set(
            expected_students.values_list('user__email', flat=True)
        )
        
        for email in expected_emails:
            assert email in recipients, f"Active student email {email} not found in recipients"
    
    @given(
        department_count=st.integers(min_value=1, max_value=2),
        level_count=st.integers(min_value=1, max_value=4)
    )
    def test_combined_filter_recipient_count_accuracy(self, department_count, level_count):
        """
        Property: Combined department and level filters must produce accurate counts
        
        **Validates: Requirements 2.6**
        """
        # Select departments and levels
        available_depts = [self.dept1, self.dept2]
        selected_depts = available_depts[:department_count]
        selected_dept_ids = [dept.id for dept in selected_depts]
        
        available_levels = ['100', '200', '300', '400']
        selected_levels = available_levels[:level_count]
        
        # Test department filter
        dept_config = {
            'type': 'department',
            'department_ids': selected_dept_ids
        }
        dept_recipients, _ = recipient_service.build_recipient_list(dept_config)
        
        # Test level filter
        level_config = {
            'type': 'level',
            'level_ids': selected_levels
        }
        level_recipients, _ = recipient_service.build_recipient_list(level_config)
        
        # Calculate expected intersection
        expected_students = Student.objects.filter(
            department_id__in=selected_dept_ids,
            level__in=selected_levels,
            is_active=True,
            user__email__isnull=False
        ).exclude(user__email='')
        expected_intersection_count = expected_students.count()
        
        # Property: Intersection of department and level filters should be consistent
        dept_emails = set(dept_recipients)
        level_emails = set(level_recipients)
        actual_intersection = dept_emails.intersection(level_emails)
        
        # The intersection count should match students that satisfy both criteria
        expected_intersection_emails = set(
            expected_students.values_list('user__email', flat=True)
        )
        
        assert len(actual_intersection) == len(expected_intersection_emails), (
            f"Intersection count mismatch: "
            f"got {len(actual_intersection)}, expected {len(expected_intersection_emails)}"
        )
    
    def test_inactive_students_excluded_from_count(self):
        """
        Property: Inactive students must be excluded from recipient counts
        
        **Validates: Requirements 2.6**
        """
        # Deactivate some students
        inactive_students = self.students[:3]
        for student in inactive_students:
            student.is_active = False
            student.save()
        
        # Test all students selection
        recipient_config = {'type': 'all'}
        recipients, metadata = recipient_service.build_recipient_list(recipient_config)
        
        # Property: Inactive students must not be included
        inactive_emails = [student.user.email for student in inactive_students]
        for email in inactive_emails:
            assert email not in recipients, f"Inactive student email {email} found in recipients"
        
        # Property: Count must exclude inactive students
        active_count = Student.objects.filter(
            is_active=True,
            user__email__isnull=False
        ).exclude(user__email='').count()
        
        assert len(recipients) == active_count, (
            f"Recipient count should exclude inactive students: "
            f"got {len(recipients)}, expected {active_count}"
        )
    
    def test_students_without_email_excluded_from_count(self):
        """
        Property: Students without email addresses must be excluded from recipient counts
        
        **Validates: Requirements 2.6**
        """
        # Remove email from some students
        students_without_email = self.students[:2]
        for student in students_without_email:
            student.user.email = ''
            student.user.save()
        
        # Test all students selection
        recipient_config = {'type': 'all'}
        recipients, metadata = recipient_service.build_recipient_list(recipient_config)
        
        # Property: Students without email must not be included
        for student in students_without_email:
            assert student.user.email not in recipients, (
                f"Student without email found in recipients: {student.matricule}"
            )
        
        # Property: Count must exclude students without email
        students_with_email_count = Student.objects.filter(
            is_active=True,
            user__email__isnull=False
        ).exclude(user__email='').count()
        
        assert len(recipients) == students_with_email_count, (
            f"Recipient count should exclude students without email: "
            f"got {len(recipients)}, expected {students_with_email_count}"
        )


if __name__ == '__main__':
    pytest.main([__file__])