"""
Property-based tests for Student Timetable Module API endpoints.

These tests validate the API behavior and access control for the student
timetable functionality.
"""

import pytest
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from hypothesis import given, strategies as st, assume, settings
from hypothesis.extra.django import from_model

from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import Course, Level, TimetableSlot, DepartmentTimetable, Lecturer
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram
from users.models import User


class StudentTimetableAPIPropertyTests(TestCase):
    """
    Property-based tests for Student Timetable Module API endpoints.
    
    Property 1: Department-Based Level Access Control
    For any student and department combination, the system should only return 
    levels that belong to the student's department, and students should only 
    be able to select levels from their own department.
    """
    
    def setUp(self):
        """Set up test data for API property tests."""
        self.client = APIClient()
        
        # Create test institution hierarchy
        self.institution = Institution.objects.create(
            name="Test University",
            code="TU"
        )
        
        self.program = AcademicProgram.objects.create(
            name="Computer Science Program",
            code="CSP",
            institution=self.institution
        )
        
        self.faculty = Faculty.objects.create(
            name="School of Engineering",
            program=self.program
        )
        
        self.department1 = Department.objects.create(
            name="Computer Science",
            faculty=self.faculty
        )
        
        self.department2 = Department.objects.create(
            name="Mathematics",
            faculty=self.faculty
        )
        
        # Create levels for different departments
        self.level1_dept1 = Level.objects.create(
            name="Level 100 CS",
            code="L100CS",
            department=self.department1
        )
        
        self.level2_dept1 = Level.objects.create(
            name="Level 200 CS",
            code="L200CS",
            department=self.department1
        )
        
        self.level1_dept2 = Level.objects.create(
            name="Level 100 Math",
            code="L100M",
            department=self.department2
        )
        
        # Create test users and students
        self.user1 = User.objects.create_user(
            username="student1",
            email="student1@test.com",
            password="testpass123"
        )
        
        self.user2 = User.objects.create_user(
            username="student2",
            email="student2@test.com", 
            password="testpass123"
        )
        
        self.student1 = Student.objects.create(
            user=self.user1,
            full_name="Alice Smith",
            matric_number="CS001",
            institution=self.institution,
            faculty=self.faculty,
            department=self.department1,  # CS department
            program=self.program
        )
        
        self.student2 = Student.objects.create(
            user=self.user2,
            full_name="Bob Jones",
            matric_number="MATH001",
            institution=self.institution,
            faculty=self.faculty,
            department=self.department2,  # Math department
            program=self.program
        )
        
        # Create courses and timetable setup
        self.course1 = Course.objects.create(
            code="CS101",
            title="Introduction to Programming",
            credit_units=3,
            department=self.department1,
            level="L100CS",
            semester="Semester 1"
        )
        
        self.timetable1 = DepartmentTimetable.objects.create(
            department=self.department1,
            name="CS Department Timetable"
        )
        
        # Create lecturer
        self.lecturer_user = User.objects.create_user(
            username="lecturer1",
            email="lecturer@test.com"
        )
        
        self.lecturer = Lecturer.objects.create(
            user=self.lecturer_user,
            employee_id="EMP001",
            department=self.department1
        )
        
        # Create timetable slot
        self.slot1 = TimetableSlot.objects.create(
            timetable=self.timetable1,
            level=self.level1_dept1,
            course=self.course1,
            lecturer=self.lecturer,
            day_of_week='MON',
            start_time='09:00',
            end_time='10:00',
            venue='Room 101'
        )
    
    def test_level_access_control_property(self):
        """
        Property 1: Department-Based Level Access Control
        Students should only see levels from their own department.
        """
        # Test for student in CS department
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/students/levels/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        levels = response.data['levels']
        
        # Verify all returned levels belong to student's department
        for level in levels:
            level_obj = Level.objects.get(id=level['id'])
            self.assertEqual(level_obj.department, self.student1.department)
        
        # Verify CS levels are included
        cs_level_ids = [level['id'] for level in levels]
        self.assertIn(self.level1_dept1.id, cs_level_ids)
        self.assertIn(self.level2_dept1.id, cs_level_ids)
        
        # Verify Math levels are NOT included
        self.assertNotIn(self.level1_dept2.id, cs_level_ids)
        
        # Test for student in Math department
        self.client.force_authenticate(user=self.user2)
        response = self.client.get('/students/levels/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        levels = response.data['levels']
        
        # Verify all returned levels belong to Math department
        for level in levels:
            level_obj = Level.objects.get(id=level['id'])
            self.assertEqual(level_obj.department, self.student2.department)
        
        # Verify Math levels are included
        math_level_ids = [level['id'] for level in levels]
        self.assertIn(self.level1_dept2.id, math_level_ids)
        
        # Verify CS levels are NOT included
        self.assertNotIn(self.level1_dept1.id, math_level_ids)
        self.assertNotIn(self.level2_dept1.id, math_level_ids)
    
    def test_cross_department_level_selection_prevention(self):
        """
        Property 1: Students cannot select levels from other departments.
        """
        self.client.force_authenticate(user=self.user1)  # CS student
        
        # Valid level selection (same department)
        response = self.client.post('/students/level-selection/', {
            'level_id': self.level1_dept1.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Invalid level selection (different department)
        response = self.client.post('/students/level-selection/', {
            'level_id': self.level1_dept2.id  # Math level
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('department', response.data['error'].lower())
    
    def test_unauthenticated_access_prevention(self):
        """
        Property: Unauthenticated users cannot access any endpoints.
        """
        # Test all endpoints without authentication
        endpoints = [
            '/students/levels/',
            '/students/level-selection/',
            '/students/timetable/',
            '/students/course-selections/'
        ]
        
        for endpoint in endpoints:
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_student_without_department_handling(self):
        """
        Property: Students without departments get appropriate error messages.
        """
        # Create user without department
        user_no_dept = User.objects.create_user(
            username="nodept",
            email="nodept@test.com",
            password="testpass123"
        )
        
        student_no_dept = Student.objects.create(
            user=user_no_dept,
            full_name="No Department",
            matric_number="NODEPT001",
            institution=self.institution,
            faculty=self.faculty,
            department=None,  # No department
            program=self.program
        )
        
        self.client.force_authenticate(user=user_no_dept)
        
        response = self.client.get('/students/levels/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('department', response.data['error'].lower())
    
    def test_level_selection_persistence(self):
        """
        Property: Level selections persist across requests.
        """
        self.client.force_authenticate(user=self.user1)
        
        # Set level selection
        response = self.client.post('/students/level-selection/', {
            'level_id': self.level1_dept1.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify persistence by retrieving
        response = self.client.get('/students/level-selection/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['level_selection']['id'], 
            self.level1_dept1.id
        )
        
        # Update level selection
        response = self.client.post('/students/level-selection/', {
            'level_id': self.level2_dept1.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)  # Update, not create
        
        # Verify update persisted
        response = self.client.get('/students/level-selection/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data['level_selection']['id'], 
            self.level2_dept1.id
        )
    
    def test_timetable_access_requires_level_selection(self):
        """
        Property 3: Timetable Access Control
        Students cannot access timetable without selecting a level.
        """
        self.client.force_authenticate(user=self.user1)
        
        # Try to access timetable without level selection
        response = self.client.get('/students/timetable/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('level', response.data['error'].lower())
        
        # Select a level
        self.client.post('/students/level-selection/', {
            'level_id': self.level1_dept1.id
        })
        
        # Now timetable access should work
        response = self.client.get('/students/timetable/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('timetable', response.data)
    
    def test_timetable_data_accuracy(self):
        """
        Property 2: Timetable Data Accuracy
        Timetable should contain exactly the courses for student's department and level.
        """
        self.client.force_authenticate(user=self.user1)
        
        # Select level
        self.client.post('/students/level-selection/', {
            'level_id': self.level1_dept1.id
        })
        
        # Get timetable
        response = self.client.get('/students/timetable/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        timetable = response.data['timetable']
        
        # Verify timetable contains expected course
        course_codes = [slot['course']['code'] for slot in timetable]
        self.assertIn(self.course1.code, course_codes)
        
        # Verify level information is correct
        self.assertEqual(response.data['level']['id'], self.level1_dept1.id)
        self.assertEqual(response.data['department'], self.department1.name)
    
    def test_course_selection_validation(self):
        """
        Property 10: Course Selection Validation
        Students can only select courses within their level and department.
        """
        self.client.force_authenticate(user=self.user1)
        
        # Select level
        self.client.post('/students/level-selection/', {
            'level_id': self.level1_dept1.id
        })
        
        # Valid course selection
        response = self.client.post('/students/course-selections/', {
            'selections': [
                {
                    'course_id': self.course1.id,
                    'is_offered': True
                }
            ]
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Try to select non-existent course
        response = self.client.post('/students/course-selections/', {
            'selections': [
                {
                    'course_id': 99999,  # Non-existent
                    'is_offered': True
                }
            ]
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    @given(
        is_offered=st.booleans()
    )
    @settings(max_examples=20, deadline=5000)
    def test_course_selection_boolean_values(self, is_offered):
        """
        Property-based test: Course selections accept any boolean value.
        """
        self.client.force_authenticate(user=self.user1)
        
        # Select level
        self.client.post('/students/level-selection/', {
            'level_id': self.level1_dept1.id
        })
        
        # Test with generated boolean value
        response = self.client.post('/students/course-selections/', {
            'selections': [
                {
                    'course_id': self.course1.id,
                    'is_offered': is_offered
                }
            ]
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify the value was stored correctly
        response = self.client.get('/students/course-selections/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        selections = response.data['course_selections']
        if selections:  # If any selections exist
            course_selection = next(
                (s for s in selections if s['course']['id'] == self.course1.id),
                None
            )
            if course_selection:
                self.assertEqual(course_selection['is_offered'], is_offered)
    
    def test_api_error_handling_consistency(self):
        """
        Property: All API endpoints return consistent error formats.
        """
        self.client.force_authenticate(user=self.user1)
        
        # Test various error conditions
        error_responses = []
        
        # Invalid level selection
        response = self.client.post('/students/level-selection/', {
            'level_id': 99999
        })
        error_responses.append(response)
        
        # Invalid course selection
        response = self.client.post('/students/course-selections/', {
            'selections': [{'course_id': 99999, 'is_offered': True}]
        })
        error_responses.append(response)
        
        # Verify all error responses have 'error' field
        for response in error_responses:
            self.assertIn('error', response.data)
            self.assertIsInstance(response.data['error'], str)
            self.assertGreater(len(response.data['error']), 0)
    
    def test_api_data_integrity_property(self):
        """
        Property 16: API Data Integrity
        All API operations maintain data consistency and referential integrity.
        """
        self.client.force_authenticate(user=self.user1)
        
        # Test atomic operations - level selection should clear course selections
        # First select a level
        response = self.client.post('/students/level-selection/', {
            'level_id': self.level1_dept1.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Create course selection
        response = self.client.post('/students/course-selections/', {
            'selections': [
                {
                    'course_id': self.course1.id,
                    'is_offered': True
                }
            ]
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify course selection exists
        response = self.client.get('/students/course-selections/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['course_selections']), 0)
        
        # Change level - should clear course selections
        response = self.client.post('/students/level-selection/', {
            'level_id': self.level2_dept1.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify course selections were cleared
        response = self.client.get('/students/course-selections/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['course_selections']), 0)
        
        # Test referential integrity - deleting referenced objects should be handled
        # This is more of a database-level test, but we can verify API behavior
        
        # Test data consistency across multiple operations
        operations = [
            # Select level
            ('POST', '/students/level-selection/', {'level_id': self.level1_dept1.id}),
            # Get timetable
            ('GET', '/students/timetable/', {}),
            # Make course selections
            ('POST', '/students/course-selections/', {
                'selections': [{'course_id': self.course1.id, 'is_offered': False}]
            }),
            # Verify selections
            ('GET', '/students/course-selections/', {}),
        ]
        
        for method, endpoint, data in operations:
            if method == 'GET':
                response = self.client.get(endpoint)
            else:
                response = self.client.post(endpoint, data)
            
            # All operations should succeed or return expected errors
            self.assertIn(response.status_code, [200, 201, 400, 404])
            
            # All responses should have consistent structure
            self.assertIsInstance(response.data, dict)
            
            # Error responses should have error field
            if response.status_code >= 400:
                self.assertIn('error', response.data)


class StudentTimetableAPIIntegrationTests(TestCase):
    """
    Integration tests for Student Timetable Module API endpoints.
    """
    
    def setUp(self):
        """Set up test data for integration tests."""
        # Reuse setup from property tests
        self.property_test_setup = StudentTimetableAPIPropertyTests()
        self.property_test_setup.setUp()
        
        # Copy references for convenience
        self.client = self.property_test_setup.client
        self.user1 = self.property_test_setup.user1
        self.student1 = self.property_test_setup.student1
        self.level1_dept1 = self.property_test_setup.level1_dept1
        self.course1 = self.property_test_setup.course1


class StudentLevelSelectionValidationTests(TestCase):
    """
    Unit tests for level selection validation logic.
    
    These tests focus on specific validation scenarios and edge cases
    for level selection functionality.
    """
    
    def setUp(self):
        """Set up test data for validation tests."""
        self.client = APIClient()
        
        # Create minimal test data
        self.institution = Institution.objects.create(
            name="Test University",
            code="TU"
        )
        
        self.program = AcademicProgram.objects.create(
            name="Test Program",
            code="TP",
            institution=self.institution
        )
        
        self.faculty = Faculty.objects.create(
            name="Test Faculty",
            program=self.program
        )
        
        self.department = Department.objects.create(
            name="Test Department",
            faculty=self.faculty
        )
        
        self.level = Level.objects.create(
            name="Test Level",
            code="TL",
            department=self.department
        )
        
        self.user = User.objects.create_user(
            username="testuser",
            email="test@test.com",
            password="testpass123"
        )
        
        self.student = Student.objects.create(
            user=self.user,
            full_name="Test Student",
            matric_number="TEST001",
            institution=self.institution,
            faculty=self.faculty,
            department=self.department,
            program=self.program
        )
    
    def test_valid_level_selection(self):
        """Test that valid level selection succeeds."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post('/students/level-selection/', {
            'level_id': self.level.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['level_selection']['id'], self.level.id)
        self.assertTrue(response.data['created'])
    
    def test_missing_level_id_validation(self):
        """Test that missing level_id returns validation error."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post('/students/level-selection/', {})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('level_id', response.data['error'])
    
    def test_invalid_level_id_validation(self):
        """Test that invalid level_id returns not found error."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post('/students/level-selection/', {
            'level_id': 99999  # Non-existent
        })
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('not found', response.data['error'].lower())
    
    def test_cross_department_level_validation(self):
        """Test that selecting level from different department fails."""
        # Create another department and level
        other_department = Department.objects.create(
            name="Other Department",
            faculty=self.faculty
        )
        
        other_level = Level.objects.create(
            name="Other Level",
            code="OL",
            department=other_department
        )
        
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post('/students/level-selection/', {
            'level_id': other_level.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('department', response.data['error'].lower())
    
    def test_level_selection_update(self):
        """Test that updating level selection works correctly."""
        # Create another level in same department
        new_level = Level.objects.create(
            name="New Level",
            code="NL",
            department=self.department
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Create initial selection
        response = self.client.post('/students/level-selection/', {
            'level_id': self.level.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Update selection
        response = self.client.post('/students/level-selection/', {
            'level_id': new_level.id
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['level_selection']['id'], new_level.id)
        self.assertFalse(response.data['created'])
    
    def test_level_selection_retrieval(self):
        """Test retrieving current level selection."""
        self.client.force_authenticate(user=self.user)
        
        # No selection initially
        response = self.client.get('/students/level-selection/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['level_selection'])
        
        # Create selection
        self.client.post('/students/level-selection/', {
            'level_id': self.level.id
        })
        
        # Retrieve selection
        response = self.client.get('/students/level-selection/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data['level_selection'])
        self.assertEqual(response.data['level_selection']['id'], self.level.id)
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated access is denied."""
        # Don't authenticate
        
        response = self.client.get('/students/level-selection/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
        response = self.client.post('/students/level-selection/', {
            'level_id': self.level.id
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_non_student_user_access_denied(self):
        """Test that non-student users cannot access endpoints."""
        # Create user without student profile
        non_student_user = User.objects.create_user(
            username="nonstudent",
            email="nonstudent@test.com",
            password="testpass123"
        )
        
        self.client.force_authenticate(user=non_student_user)
        
        response = self.client.get('/students/level-selection/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('student profile', response.data['error'].lower())
    
    def test_student_without_department_handling(self):
        """Test handling of student without assigned department."""
        # Create student without department
        user_no_dept = User.objects.create_user(
            username="nodept",
            email="nodept@test.com",
            password="testpass123"
        )
        
        student_no_dept = Student.objects.create(
            user=user_no_dept,
            full_name="No Department Student",
            matric_number="NODEPT001",
            institution=self.institution,
            faculty=self.faculty,
            department=None,  # No department
            program=self.program
        )
        
        self.client.force_authenticate(user=user_no_dept)
        
        response = self.client.get('/students/levels/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('department', response.data['error'].lower())
    
    def test_level_selection_clears_course_selections(self):
        """Test that changing level clears existing course selections."""
        # Create course and course selection
        course = Course.objects.create(
            code="TEST101",
            title="Test Course",
            credit_units=3,
            department=self.department,
            level="TL",
            semester="Semester 1"
        )
        
        # Create timetable setup
        timetable = DepartmentTimetable.objects.create(
            department=self.department,
            name="Test Timetable"
        )
        
        lecturer_user = User.objects.create_user(
            username="lecturer",
            email="lecturer@test.com"
        )
        
        lecturer = Lecturer.objects.create(
            user=lecturer_user,
            employee_id="EMP001",
            department=self.department
        )
        
        TimetableSlot.objects.create(
            timetable=timetable,
            level=self.level,
            course=course,
            lecturer=lecturer,
            day_of_week='MON',
            start_time='09:00',
            end_time='10:00',
            venue='Room 101'
        )
        
        self.client.force_authenticate(user=self.user)
        
        # Select level
        self.client.post('/students/level-selection/', {
            'level_id': self.level.id
        })
        
        # Create course selection
        StudentCourseSelection.objects.create(
            student=self.student,
            department=self.department,
            level=self.level,
            course=course,
            is_offered=False
        )
        
        # Verify course selection exists
        self.assertTrue(
            StudentCourseSelection.objects.filter(student=self.student).exists()
        )
        
        # Create new level and change selection
        new_level = Level.objects.create(
            name="New Level",
            code="NL",
            department=self.department
        )
        
        self.client.post('/students/level-selection/', {
            'level_id': new_level.id
        })
        
        # Verify course selections were cleared
        self.assertFalse(
            StudentCourseSelection.objects.filter(student=self.student).exists()
        )
    
    def test_error_response_format_consistency(self):
        """Test that all error responses follow consistent format."""
        self.client.force_authenticate(user=self.user)
        
        error_scenarios = [
            # Missing level_id
            ({}, status.HTTP_400_BAD_REQUEST),
            # Invalid level_id
            ({'level_id': 99999}, status.HTTP_404_NOT_FOUND),
        ]
        
        for data, expected_status in error_scenarios:
            response = self.client.post('/students/level-selection/', data)
            self.assertEqual(response.status_code, expected_status)
            self.assertIn('error', response.data)
            self.assertIsInstance(response.data['error'], str)
            self.assertGreater(len(response.data['error']), 0)
    
    def test_complete_student_workflow(self):
        """
        Integration test: Complete student workflow from login to course selection.
        """
        self.client.force_authenticate(user=self.user1)
        
        # Step 1: Get available levels
        response = self.client.get('/students/levels/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        levels = response.data['levels']
        self.assertGreater(len(levels), 0)
        
        # Step 2: Select a level
        level_id = levels[0]['id']
        response = self.client.post('/students/level-selection/', {
            'level_id': level_id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 3: Get timetable
        response = self.client.get('/students/timetable/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        timetable = response.data['timetable']
        
        # Step 4: Make course selections
        if timetable:
            course_id = timetable[0]['course']['id']
            response = self.client.post('/students/course-selections/', {
                'selections': [
                    {
                        'course_id': course_id,
                        'is_offered': False  # Opt out
                    }
                ]
            })
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            # Step 5: Verify selections persist
            response = self.client.get('/students/course-selections/')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            selections = response.data['course_selections']
            
            course_selection = next(
                (s for s in selections if s['course']['id'] == course_id),
                None
            )
            self.assertIsNotNone(course_selection)
            self.assertFalse(course_selection['is_offered'])
    
    def test_api_response_format_consistency(self):
        """
        Integration test: All API responses follow consistent format.
        """
        self.client.force_authenticate(user=self.user1)
        
        # Test successful responses
        endpoints_and_expected_keys = [
            ('/students/levels/', ['levels', 'student_department']),
            ('/students/level-selection/', ['level_selection']),  # GET
        ]
        
        for endpoint, expected_keys in endpoints_and_expected_keys:
            response = self.client.get(endpoint)
            if response.status_code == 200:
                for key in expected_keys:
                    self.assertIn(key, response.data)
    
    def test_concurrent_student_access(self):
        """
        Integration test: Multiple students can use the system simultaneously.
        """
        # Authenticate both students
        client1 = APIClient()
        client2 = APIClient()
        
        client1.force_authenticate(user=self.property_test_setup.user1)
        client2.force_authenticate(user=self.property_test_setup.user2)
        
        # Both students select levels simultaneously
        response1 = client1.post('/students/level-selection/', {
            'level_id': self.property_test_setup.level1_dept1.id
        })
        
        response2 = client2.post('/students/level-selection/', {
            'level_id': self.property_test_setup.level1_dept2.id
        })
        
        # Both should succeed
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        # Verify selections are independent
        response1 = client1.get('/students/level-selection/')
        response2 = client2.get('/students/level-selection/')
        
        self.assertEqual(
            response1.data['level_selection']['id'],
            self.property_test_setup.level1_dept1.id
        )
        self.assertEqual(
            response2.data['level_selection']['id'],
            self.property_test_setup.level1_dept2.id
        )