"""
Property-based tests for Student Timetable Module data models.

These tests validate the database relationship integrity and business rules
for StudentLevelSelection and StudentCourseSelection models.
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from hypothesis import given, strategies as st, assume, settings
from hypothesis.extra.django import from_model

from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import Course, Level, TimetableSlot, DepartmentTimetable, Lecturer
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram
from users.models import User


class StudentTimetableModelPropertyTests(TestCase):
    """
    Property-based tests for Student Timetable Module models.
    
    Property 11: Database Relationship Integrity
    For any stored course selection, the database should maintain proper 
    relationships between Student, Department, Level, Course, and offering 
    status while ensuring SQLite compatibility and referential integrity.
    """
    
    def setUp(self):
        """Set up test data for property tests."""
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
        
        self.department = Department.objects.create(
            name="Computer Science",
            faculty=self.faculty
        )
        
        # Create another department for cross-department validation
        self.other_department = Department.objects.create(
            name="Mathematics",
            faculty=self.faculty
        )
        
        # Create levels
        self.level1 = Level.objects.create(
            name="Level 100",
            code="L100",
            department=self.department
        )
        
        self.level2 = Level.objects.create(
            name="Level 200", 
            code="L200",
            department=self.department
        )
        
        self.other_level = Level.objects.create(
            name="Level 100 Math",
            code="L100M",
            department=self.other_department
        )
        
        # Create courses
        self.course1 = Course.objects.create(
            code="CS101",
            title="Introduction to Programming",
            credit_units=3,
            department=self.department,
            level="L100",
            semester="Semester 1"
        )
        
        self.course2 = Course.objects.create(
            code="CS201",
            title="Data Structures",
            credit_units=3,
            department=self.department,
            level="L200", 
            semester="Semester 1"
        )
        
        self.other_course = Course.objects.create(
            code="MATH101",
            title="Calculus I",
            credit_units=3,
            department=self.other_department,
            level="L100M",
            semester="Semester 1"
        )
        
        # Create timetable and slots
        self.timetable = DepartmentTimetable.objects.create(
            department=self.department,
            name="CS Department Timetable"
        )
        
        # Create lecturer
        self.lecturer_user = User.objects.create_user(
            username="lecturer1",
            email="lecturer@test.com",
            first_name="John",
            last_name="Doe"
        )
        
        self.lecturer = Lecturer.objects.create(
            user=self.lecturer_user,
            employee_id="EMP001",
            department=self.department
        )
        
        # Create timetable slots
        self.slot1 = TimetableSlot.objects.create(
            timetable=self.timetable,
            level=self.level1,
            course=self.course1,
            lecturer=self.lecturer,
            day_of_week='MON',
            start_time='09:00',
            end_time='10:00',
            venue='Room 101'
        )
        
        self.slot2 = TimetableSlot.objects.create(
            timetable=self.timetable,
            level=self.level2,
            course=self.course2,
            lecturer=self.lecturer,
            day_of_week='TUE',
            start_time='10:00',
            end_time='11:00',
            venue='Room 102'
        )
        
        # Create test users and students
        self.user1 = User.objects.create_user(
            username="student1",
            email="student1@test.com",
            first_name="Alice",
            last_name="Smith"
        )
        
        self.user2 = User.objects.create_user(
            username="student2", 
            email="student2@test.com",
            first_name="Bob",
            last_name="Jones"
        )
        
        self.student1 = Student.objects.create(
            user=self.user1,
            full_name="Alice Smith",
            matric_number="CS001",
            institution=self.institution,
            faculty=self.faculty,
            department=self.department,
            program=self.program
        )
        
        self.student2 = Student.objects.create(
            user=self.user2,
            full_name="Bob Jones",
            matric_number="CS002",
            institution=self.institution,
            faculty=self.faculty,
            department=self.department,
            program=self.program
        )
    
    def test_student_level_selection_department_validation(self):
        """
        Property: Students can only select levels from their own department.
        """
        # Valid level selection should work
        level_selection = StudentLevelSelection(
            student=self.student1,
            level=self.level1
        )
        level_selection.full_clean()  # Should not raise ValidationError
        level_selection.save()
        
        # Invalid cross-department level selection should fail
        with self.assertRaises(ValidationError):
            invalid_selection = StudentLevelSelection(
                student=self.student1,
                level=self.other_level  # Different department
            )
            invalid_selection.full_clean()
    
    def test_student_level_selection_uniqueness(self):
        """
        Property: Each student can have only one level selection.
        """
        # Create first level selection
        StudentLevelSelection.objects.create(
            student=self.student1,
            level=self.level1
        )
        
        # Attempting to create another should fail due to OneToOneField
        with self.assertRaises(IntegrityError):
            StudentLevelSelection.objects.create(
                student=self.student1,
                level=self.level2
            )
    
    def test_course_selection_department_validation(self):
        """
        Property: Course selections must maintain department consistency.
        """
        # Valid course selection should work
        course_selection = StudentCourseSelection(
            student=self.student1,
            department=self.department,
            level=self.level1,
            course=self.course1,
            is_offered=True
        )
        course_selection.full_clean()  # Should not raise ValidationError
        course_selection.save()
        
        # Invalid cross-department course selection should fail
        with self.assertRaises(ValidationError):
            invalid_selection = StudentCourseSelection(
                student=self.student1,
                department=self.department,  # Student's department
                level=self.level1,
                course=self.other_course,  # Course from different department
                is_offered=True
            )
            invalid_selection.full_clean()
    
    def test_course_selection_level_validation(self):
        """
        Property: Course selections must be for courses scheduled in the timetable.
        """
        # Valid course selection (course is in timetable for this level)
        course_selection = StudentCourseSelection(
            student=self.student1,
            department=self.department,
            level=self.level1,
            course=self.course1,  # This course is scheduled for level1
            is_offered=True
        )
        course_selection.full_clean()  # Should not raise ValidationError
        course_selection.save()
        
        # Invalid course selection (course not scheduled for this level)
        with self.assertRaises(ValidationError):
            invalid_selection = StudentCourseSelection(
                student=self.student1,
                department=self.department,
                level=self.level1,
                course=self.course2,  # This course is scheduled for level2, not level1
                is_offered=True
            )
            invalid_selection.full_clean()
    
    def test_course_selection_uniqueness(self):
        """
        Property: Each student can have only one selection per course per level.
        """
        # Create first course selection
        StudentCourseSelection.objects.create(
            student=self.student1,
            department=self.department,
            level=self.level1,
            course=self.course1,
            is_offered=True
        )
        
        # Attempting to create duplicate should fail
        with self.assertRaises(IntegrityError):
            StudentCourseSelection.objects.create(
                student=self.student1,
                department=self.department,
                level=self.level1,
                course=self.course1,
                is_offered=False
            )
    
    def test_course_selection_isolation(self):
        """
        Property: Course selections are isolated between students.
        """
        # Student 1 selects course
        selection1 = StudentCourseSelection.objects.create(
            student=self.student1,
            department=self.department,
            level=self.level1,
            course=self.course1,
            is_offered=True
        )
        
        # Student 2 can make different selection for same course
        selection2 = StudentCourseSelection.objects.create(
            student=self.student2,
            department=self.department,
            level=self.level1,
            course=self.course1,
            is_offered=False
        )
        
        # Verify selections are independent
        self.assertTrue(selection1.is_offered)
        self.assertFalse(selection2.is_offered)
        
        # Changing one doesn't affect the other
        selection1.is_offered = False
        selection1.save()
        
        selection2.refresh_from_db()
        self.assertFalse(selection2.is_offered)  # Unchanged
    
    def test_database_referential_integrity(self):
        """
        Property: Database maintains referential integrity on deletions.
        """
        # Create level selection
        level_selection = StudentLevelSelection.objects.create(
            student=self.student1,
            level=self.level1
        )
        
        # Create course selection
        course_selection = StudentCourseSelection.objects.create(
            student=self.student1,
            department=self.department,
            level=self.level1,
            course=self.course1,
            is_offered=True
        )
        
        # Deleting student should cascade delete selections
        student_id = self.student1.id
        self.student1.delete()
        
        # Verify selections are deleted
        self.assertFalse(
            StudentLevelSelection.objects.filter(student_id=student_id).exists()
        )
        self.assertFalse(
            StudentCourseSelection.objects.filter(student_id=student_id).exists()
        )
    
    def test_default_course_offering_state(self):
        """
        Property: Course selections default to offered state.
        """
        course_selection = StudentCourseSelection.objects.create(
            student=self.student1,
            department=self.department,
            level=self.level1,
            course=self.course1
            # is_offered not specified, should default to True
        )
        
        self.assertTrue(course_selection.is_offered)
    
    def test_model_string_representations(self):
        """
        Property: Models have meaningful string representations.
        """
        level_selection = StudentLevelSelection.objects.create(
            student=self.student1,
            level=self.level1
        )
        
        course_selection = StudentCourseSelection.objects.create(
            student=self.student1,
            department=self.department,
            level=self.level1,
            course=self.course1,
            is_offered=True
        )
        
        # Verify string representations are meaningful
        self.assertIn(self.student1.full_name, str(level_selection))
        self.assertIn(self.level1.name, str(level_selection))
        
        self.assertIn(self.student1.full_name, str(course_selection))
        self.assertIn(self.course1.code, str(course_selection))
        self.assertIn("Offered", str(course_selection))
        
        # Test not offered state
        course_selection.is_offered = False
        course_selection.save()
        self.assertIn("Not Offered", str(course_selection))
    
    @given(
        is_offered=st.booleans()
    )
    @settings(max_examples=50, deadline=5000)
    def test_course_selection_boolean_property(self, is_offered):
        """
        Property-based test: Course selection boolean field accepts any boolean value.
        """
        course_selection = StudentCourseSelection.objects.create(
            student=self.student1,
            department=self.department,
            level=self.level1,
            course=self.course1,
            is_offered=is_offered
        )
        
        # Verify the value is stored correctly
        course_selection.refresh_from_db()
        self.assertEqual(course_selection.is_offered, is_offered)
    
    def test_database_indexes_exist(self):
        """
        Property: Database indexes are created for performance optimization.
        """
        from django.db import connection
        
        # Get table names
        with connection.cursor() as cursor:
            # Check if indexes exist (SQLite specific)
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='index' AND tbl_name='students_studentcourseselection'
            """)
            indexes = [row[0] for row in cursor.fetchall()]
            
            # Verify our custom indexes exist
            index_patterns = ['student', 'level', 'departm']
            for pattern in index_patterns:
                self.assertTrue(
                    any(pattern in idx for idx in indexes),
                    f"Index containing '{pattern}' not found in {indexes}"
                )


class StudentTimetableModelIntegrationTests(TestCase):
    """
    Integration tests for Student Timetable Module models with existing system.
    """
    
    def setUp(self):
        """Set up test data for integration tests."""
        # Reuse setup from property tests
        self.property_test_setup = StudentTimetableModelPropertyTests()
        self.property_test_setup.setUp()
        
        # Copy references for convenience
        self.student1 = self.property_test_setup.student1
        self.department = self.property_test_setup.department
        self.level1 = self.property_test_setup.level1
        self.course1 = self.property_test_setup.course1
    
    def test_integration_with_existing_student_model(self):
        """
        Test that new models integrate properly with existing Student model.
        """
        # Create level selection
        level_selection = StudentLevelSelection.objects.create(
            student=self.student1,
            level=self.level1
        )
        
        # Verify reverse relationship works
        self.assertEqual(self.student1.level_selection, level_selection)
        
        # Create course selection
        course_selection = StudentCourseSelection.objects.create(
            student=self.student1,
            department=self.department,
            level=self.level1,
            course=self.course1,
            is_offered=True
        )
        
        # Verify reverse relationship works
        self.assertIn(course_selection, self.student1.course_selections.all())
    
    def test_sqlite_compatibility(self):
        """
        Test that models work correctly with SQLite database.
        """
        from django.db import connection
        
        # Verify we're using SQLite
        self.assertTrue(connection.vendor == 'sqlite')
        
        # Test transaction handling
        with transaction.atomic():
            level_selection = StudentLevelSelection.objects.create(
                student=self.student1,
                level=self.level1
            )
            
            course_selection = StudentCourseSelection.objects.create(
                student=self.student1,
                department=self.department,
                level=self.level1,
                course=self.course1,
                is_offered=True
            )
        
        # Verify data was committed
        self.assertTrue(
            StudentLevelSelection.objects.filter(student=self.student1).exists()
        )
        self.assertTrue(
            StudentCourseSelection.objects.filter(student=self.student1).exists()
        )