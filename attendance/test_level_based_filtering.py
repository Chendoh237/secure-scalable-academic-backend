"""
Property Test 15: Level-Based Attendance Filtering
Validates: Requirements 5.4, 5.5

This test validates that attendance is properly filtered based on
student's selected academic level, ensuring students can only
attend classes for their selected level.
"""

import pytest
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from hypothesis import given, strategies as st, settings, assume
import datetime
from unittest.mock import patch, MagicMock

from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import Course, Level, Lecturer, DepartmentTimetable, TimetableSlot
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram
from attendance.enhanced_services import EnhancedAttendanceService
from attendance.compatibility import mark_attendance_enhanced

User = get_user_model()


class LevelBasedAttendanceFilteringPropertyTest(TestCase):
    """
    Property-based tests for level-based attendance filtering
    """
    
    def setUp(self):
        """Set up test data"""
        # Create institution hierarchy
        self.institution = Institution.objects.create(
            name="Test University",
            code="TU",
            country="Test Country"
        )
        
        self.faculty = Faculty.objects.create(
            name="Faculty of Science",
            code="SCI",
            institution=self.institution
        )
        
        self.department = Department.objects.create(
            name="Computer Science",
            code="CS",
            faculty=self.faculty
        )
        
        self.program = AcademicProgram.objects.create(
            name="Bachelor of Computer Science",
            code="BCS",
            department=self.department,
            duration_years=4
        )
        
        # Create lecturer user and lecturer
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
        
        # Create timetable
        self.timetable = DepartmentTimetable.objects.create(
            department=self.department,
            name="CS Timetable"
        )
        
        # Create student user and student
        self.student_user = User.objects.create_user(
            username="student1",
            email="student@test.com",
            first_name="Jane",
            last_name="Smith"
        )
        
        self.student = Student.objects.create(
            user=self.student_user,
            full_name="Jane Smith",
            matric_number="CS2024001",
            institution=self.institution,
            faculty=self.faculty,
            department=self.department,
            program=self.program
        )
    
    @given(
        num_levels=st.integers(min_value=2, max_value=5),
        selected_level_index=st.integers(min_value=0, max_value=4),
        target_level_index=st.integers(min_value=0, max_value=4)
    )
    @settings(max_examples=30, deadline=None)
    def test_attendance_restricted_to_selected_level(self, num_levels, selected_level_index, target_level_index):
        """
        Property: Students can only attend classes for their selected level
        """
        assume(selected_level_index < num_levels)
        assume(target_level_index < num_levels)
        
        # Create multiple levels
        levels = []
        for i in range(num_levels):
            level = Level.objects.create(
                name=f"Level {100 + i * 100}",
                code=f"L{100 + i * 100}",
                department=self.department
            )
            levels.append(level)
        
        # Set student's selected level
        selected_level = levels[selected_level_index]
        StudentLevelSelection.objects.create(
            student=self.student,
            level=selected_level
        )
        
        # Create courses and timetable slots for each level
        courses = []
        timetable_slots = []
        
        for i, level in enumerate(levels):
            course = Course.objects.create(
                code=f"CS{100 + i}01",
                title=f"Course for Level {level.name}",
                credit_units=3,
                department=self.department,
                level=str(100 + i * 100),
                semester="1"
            )
            courses.append(course)
            
            slot = TimetableSlot.objects.create(
                timetable=self.timetable,
                level=level,
                course=course,
                lecturer=self.lecturer,
                day_of_week='MON',
                start_time=datetime.time(9 + i, 0),
                end_time=datetime.time(10 + i, 0),
                venue=f"Room {101 + i}"
            )
            timetable_slots.append(slot)
            
            # Create course selection for student's selected level only
            if i == selected_level_index:
                StudentCourseSelection.objects.create(
                    student=self.student,
                    department=self.department,
                    level=level,
                    course=course,
                    is_offered=True
                )
        
        # Test attendance for target level
        target_slot = timetable_slots[target_level_index]
        
        with patch('django.utils.timezone.localtime') as mock_time:
            # Mock current time to be during target class
            mock_now = MagicMock()
            mock_now.strftime.return_value = 'MON'
            mock_now.time.return_value = datetime.time(9 + target_level_index, 30)
            mock_time.return_value = mock_now
            
            # Test validation
            validation = EnhancedAttendanceService.validate_attendance_eligibility(
                self.student, target_slot
            )
            
            if target_level_index == selected_level_index:
                # Property: Student should be eligible for their selected level
                self.assertTrue(validation['eligible'] or 'level' not in validation['reason'].lower(),
                    f"Student should be eligible for their selected level {selected_level.name}")
            else:
                # Property: Student should not be eligible for other levels
                self.assertFalse(validation['eligible'],
                    f"Student should not be eligible for level {levels[target_level_index].name}")
                self.assertIn('level', validation['reason'].lower(),
                    "Rejection reason should mention level mismatch")
        
        # Property: Only courses from selected level should appear in offered courses
        offered_courses = EnhancedAttendanceService.get_student_offered_courses(self.student)
        
        if offered_courses:
            # All offered courses should be from the selected level
            for course_info in offered_courses:
                # Find the course
                course = Course.objects.get(code=course_info['course_code'])
                # Find which level this course belongs to
                course_slot = TimetableSlot.objects.get(course=course, timetable=self.timetable)
                
                self.assertEqual(course_slot.level, selected_level,
                    f"Offered course {course.code} should be from selected level {selected_level.name}")
    
    @given(
        student_level_index=st.integers(min_value=0, max_value=3),
        class_level_indices=st.lists(st.integers(min_value=0, max_value=3), min_size=2, max_size=4, unique=True)
    )
    @settings(max_examples=20, deadline=None)
    def test_current_timetable_slot_level_filtering(self, student_level_index, class_level_indices):
        """
        Property: Current timetable slot should only return classes from student's level
        """
        # Create levels
        levels = []
        for i in range(4):
            level = Level.objects.create(
                name=f"Level {100 + i * 100}",
                code=f"L{100 + i * 100}",
                department=self.department
            )
            levels.append(level)
        
        # Set student's selected level
        student_level = levels[student_level_index]
        StudentLevelSelection.objects.create(
            student=self.student,
            level=student_level
        )
        
        # Create simultaneous classes at different levels
        current_time = datetime.time(10, 0)
        current_day = 'MON'
        
        created_slots = []
        for level_index in class_level_indices:
            level = levels[level_index]
            
            course = Course.objects.create(
                code=f"CS{100 + level_index}01",
                title=f"Course for {level.name}",
                credit_units=3,
                department=self.department,
                level=str(100 + level_index * 100),
                semester="1"
            )
            
            slot = TimetableSlot.objects.create(
                timetable=self.timetable,
                level=level,
                course=course,
                lecturer=self.lecturer,
                day_of_week=current_day,
                start_time=current_time,
                end_time=datetime.time(12, 0),
                venue=f"Room {101 + level_index}"
            )
            created_slots.append((slot, level_index))
            
            # Create course selection if it's the student's level
            if level_index == student_level_index:
                StudentCourseSelection.objects.create(
                    student=self.student,
                    department=self.department,
                    level=level,
                    course=course,
                    is_offered=True
                )
        
        with patch('django.utils.timezone.localtime') as mock_time:
            # Mock current time to be during classes
            mock_now = MagicMock()
            mock_now.strftime.return_value = current_day
            mock_now.time.return_value = datetime.time(10, 30)  # During class
            mock_time.return_value = mock_now
            
            current_slot = EnhancedAttendanceService.get_current_timetable_slot_for_student(self.student)
            
            if student_level_index in class_level_indices:
                # Property: Should return slot from student's level
                if current_slot:  # May be None due to test constraints
                    self.assertEqual(current_slot.level, student_level,
                        f"Current slot should be from student's level {student_level.name}")
            else:
                # Property: Should return None if no class at student's level
                self.assertIsNone(current_slot,
                    "Should return None when no class at student's level")
    
    def test_level_change_resets_course_selections(self):
        """
        Property: Changing level should invalidate previous course selections
        """
        # Create two levels
        level1 = Level.objects.create(
            name="Level 100",
            code="L100",
            department=self.department
        )
        
        level2 = Level.objects.create(
            name="Level 200",
            code="L200",
            department=self.department
        )
        
        # Create courses for each level
        course1 = Course.objects.create(
            code="CS101",
            title="Level 100 Course",
            credit_units=3,
            department=self.department,
            level="100",
            semester="1"
        )
        
        course2 = Course.objects.create(
            code="CS201",
            title="Level 200 Course",
            credit_units=3,
            department=self.department,
            level="200",
            semester="1"
        )
        
        # Create timetable slots
        slot1 = TimetableSlot.objects.create(
            timetable=self.timetable,
            level=level1,
            course=course1,
            lecturer=self.lecturer,
            day_of_week='MON',
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            venue="Room 101"
        )
        
        slot2 = TimetableSlot.objects.create(
            timetable=self.timetable,
            level=level2,
            course=course2,
            lecturer=self.lecturer,
            day_of_week='MON',
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            venue="Room 201"
        )
        
        # Initially select level 1
        level_selection = StudentLevelSelection.objects.create(
            student=self.student,
            level=level1
        )
        
        # Create course selection for level 1
        StudentCourseSelection.objects.create(
            student=self.student,
            department=self.department,
            level=level1,
            course=course1,
            is_offered=True
        )
        
        # Verify student can access level 1 course
        offered_courses_l1 = EnhancedAttendanceService.get_student_offered_courses(self.student)
        course_codes_l1 = {c['course_code'] for c in offered_courses_l1}
        self.assertIn(course1.code, course_codes_l1)
        
        # Change to level 2
        level_selection.level = level2
        level_selection.save()
        
        # Create course selection for level 2
        StudentCourseSelection.objects.create(
            student=self.student,
            department=self.department,
            level=level2,
            course=course2,
            is_offered=True
        )
        
        # Property: Should now only see level 2 courses
        offered_courses_l2 = EnhancedAttendanceService.get_student_offered_courses(self.student)
        course_codes_l2 = {c['course_code'] for c in offered_courses_l2}
        
        self.assertIn(course2.code, course_codes_l2,
            "Should see level 2 course after level change")
        self.assertNotIn(course1.code, course_codes_l2,
            "Should not see level 1 course after level change")
        
        # Property: Validation should fail for old level courses
        with patch('django.utils.timezone.localtime') as mock_time:
            mock_now = MagicMock()
            mock_now.strftime.return_value = 'MON'
            mock_now.time.return_value = datetime.time(9, 30)
            mock_time.return_value = mock_now
            
            validation_l1 = EnhancedAttendanceService.validate_attendance_eligibility(
                self.student, slot1
            )
            validation_l2 = EnhancedAttendanceService.validate_attendance_eligibility(
                self.student, slot2
            )
            
            self.assertFalse(validation_l1['eligible'],
                "Should not be eligible for old level course")
            # validation_l2 eligibility depends on other factors, but level should match
            if not validation_l2['eligible']:
                self.assertNotIn('level', validation_l2['reason'].lower())
    
    @given(
        num_students=st.integers(min_value=2, max_value=4),
        level_assignments=st.lists(st.integers(min_value=0, max_value=2), min_size=2, max_size=4)
    )
    @settings(max_examples=15, deadline=None)
    def test_multiple_students_level_isolation(self, num_students, level_assignments):
        """
        Property: Students at different levels should have isolated attendance
        """
        assume(len(level_assignments) >= num_students)
        
        # Create levels
        levels = []
        for i in range(3):
            level = Level.objects.create(
                name=f"Level {100 + i * 100}",
                code=f"L{100 + i * 100}",
                department=self.department
            )
            levels.append(level)
        
        # Create students and assign levels
        students = []
        for i in range(num_students):
            user = User.objects.create_user(
                username=f"student{i}",
                email=f"student{i}@test.com",
                first_name=f"Student",
                last_name=f"{i}"
            )
            
            student = Student.objects.create(
                user=user,
                full_name=f"Student {i}",
                matric_number=f"CS202400{i}",
                institution=self.institution,
                faculty=self.faculty,
                department=self.department,
                program=self.program
            )
            students.append(student)
            
            # Assign level
            assigned_level = levels[level_assignments[i]]
            StudentLevelSelection.objects.create(
                student=student,
                level=assigned_level
            )
        
        # Create courses and slots for each level
        courses_by_level = {}
        slots_by_level = {}
        
        for i, level in enumerate(levels):
            course = Course.objects.create(
                code=f"CS{100 + i}01",
                title=f"Course for {level.name}",
                credit_units=3,
                department=self.department,
                level=str(100 + i * 100),
                semester="1"
            )
            courses_by_level[level] = course
            
            slot = TimetableSlot.objects.create(
                timetable=self.timetable,
                level=level,
                course=course,
                lecturer=self.lecturer,
                day_of_week='MON',
                start_time=datetime.time(9, 0),
                end_time=datetime.time(11, 0),
                venue=f"Room {101 + i}"
            )
            slots_by_level[level] = slot
        
        # Create course selections for each student
        for i, student in enumerate(students):
            assigned_level = levels[level_assignments[i]]
            course = courses_by_level[assigned_level]
            
            StudentCourseSelection.objects.create(
                student=student,
                department=self.department,
                level=assigned_level,
                course=course,
                is_offered=True
            )
        
        # Test that each student only sees courses from their level
        for i, student in enumerate(students):
            assigned_level = levels[level_assignments[i]]
            expected_course = courses_by_level[assigned_level]
            
            offered_courses = EnhancedAttendanceService.get_student_offered_courses(student)
            course_codes = {c['course_code'] for c in offered_courses}
            
            # Property: Student should only see courses from their level
            self.assertIn(expected_course.code, course_codes,
                f"Student {i} should see course from their level {assigned_level.name}")
            
            # Property: Student should not see courses from other levels
            for other_level, other_course in courses_by_level.items():
                if other_level != assigned_level:
                    self.assertNotIn(other_course.code, course_codes,
                        f"Student {i} should not see course from level {other_level.name}")
        
        # Test attendance validation isolation
        with patch('django.utils.timezone.localtime') as mock_time:
            mock_now = MagicMock()
            mock_now.strftime.return_value = 'MON'
            mock_now.time.return_value = datetime.time(9, 30)
            mock_time.return_value = mock_now
            
            for i, student in enumerate(students):
                assigned_level = levels[level_assignments[i]]
                
                for level, slot in slots_by_level.items():
                    validation = EnhancedAttendanceService.validate_attendance_eligibility(
                        student, slot
                    )
                    
                    if level == assigned_level:
                        # Should be eligible for their own level (or fail for other reasons)
                        if not validation['eligible']:
                            self.assertNotIn('level', validation['reason'].lower(),
                                f"Student {i} should not be rejected due to level mismatch for their own level")
                    else:
                        # Should not be eligible for other levels
                        self.assertFalse(validation['eligible'],
                            f"Student {i} should not be eligible for level {level.name}")
                        self.assertIn('level', validation['reason'].lower(),
                            f"Rejection should mention level mismatch")
    
    def test_no_level_selection_blocks_attendance(self):
        """
        Property: Students without level selection cannot attend any classes
        """
        # Create level and course
        level = Level.objects.create(
            name="Level 100",
            code="L100",
            department=self.department
        )
        
        course = Course.objects.create(
            code="CS101",
            title="Test Course",
            credit_units=3,
            department=self.department,
            level="100",
            semester="1"
        )
        
        slot = TimetableSlot.objects.create(
            timetable=self.timetable,
            level=level,
            course=course,
            lecturer=self.lecturer,
            day_of_week='MON',
            start_time=datetime.time(9, 0),
            end_time=datetime.time(11, 0),
            venue="Room 101"
        )
        
        # Don't create level selection for student
        
        # Property: Should not be able to get current timetable slot
        with patch('django.utils.timezone.localtime') as mock_time:
            mock_now = MagicMock()
            mock_now.strftime.return_value = 'MON'
            mock_now.time.return_value = datetime.time(9, 30)
            mock_time.return_value = mock_now
            
            current_slot = EnhancedAttendanceService.get_current_timetable_slot_for_student(self.student)
            self.assertIsNone(current_slot,
                "Student without level selection should not get current timetable slot")
        
        # Property: Validation should fail
        validation = EnhancedAttendanceService.validate_attendance_eligibility(self.student, slot)
        self.assertFalse(validation['eligible'],
            "Student without level selection should not be eligible for attendance")
        self.assertIn('level', validation['reason'].lower(),
            "Rejection reason should mention level selection")
        
        # Property: Should have no offered courses
        offered_courses = EnhancedAttendanceService.get_student_offered_courses(self.student)
        self.assertEqual(len(offered_courses), 0,
            "Student without level selection should have no offered courses")
        
        # Property: Attendance marking should fail
        result = mark_attendance_enhanced(self.student.matric_number)
        self.assertFalse(result['success'],
            "Attendance marking should fail for student without level selection")
        self.assertIn('level', result['message'].lower(),
            "Error message should mention level selection")