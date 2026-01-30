"""
Integration Tests for Course Registration & Approval Feature

Tests the complete workflow:
1. Timetable course selection (auto-approved)
2. Direct course registration (pending approval)
3. Admin approval/rejection
4. My Courses unified view
5. Attendance system integration
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from students.models import Student, StudentCourseSelection, StudentLevelSelection
from courses.models import Course, Level, DepartmentTimetable, TimetableSlot
from institutions.models import Institution, Faculty, Department

User = get_user_model()


class CourseRegistrationApprovalIntegrationTest(TestCase):
    """Integration tests for the complete course registration and approval workflow"""
    
    def setUp(self):
        """Set up test data"""
        # Create institution hierarchy
        self.institution = Institution.objects.create(
            name="Test University",
            code="TU"
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
        
        # Create levels
        self.level_200 = Level.objects.create(
            name="200 Level",
            code="200",
            department=self.department
        )
        
        self.level_300 = Level.objects.create(
            name="300 Level",
            code="300",
            department=self.department
        )
        
        # Create courses
        self.course_200_1 = Course.objects.create(
            code="CS201",
            title="Data Structures",
            department=self.department,
            level=self.level_200,
            credit_units=3
        )
        
        self.course_200_2 = Course.objects.create(
            code="CS202",
            title="Algorithms",
            department=self.department,
            level=self.level_200,
            credit_units=3
        )
        
        self.course_300_1 = Course.objects.create(
            code="CS301",
            title="Database Systems",
            department=self.department,
            level=self.level_300,
            credit_units=3
        )
        
        # Create timetable
        self.timetable = DepartmentTimetable.objects.create(
            department=self.department,
            name="CS Timetable",
            academic_year="2023/2024",
            semester="First"
        )
        
        # Add courses to timetable
        TimetableSlot.objects.create(
            timetable=self.timetable,
            course=self.course_200_1,
            level=self.level_200,
            day_of_week=1,
            start_time="09:00",
            end_time="11:00"
        )
        
        TimetableSlot.objects.create(
            timetable=self.timetable,
            course=self.course_200_2,
            level=self.level_200,
            day_of_week=2,
            start_time="09:00",
            end_time="11:00"
        )
        
        # Create student user
        self.student_user = User.objects.create_user(
            username="student1",
            password="testpass123",
            email="student1@test.com"
        )
        
        self.student = Student.objects.create(
            user=self.student_user,
            full_name="Test Student",
            matric_number="2020/001",
            institution=self.institution,
            faculty=self.faculty,
            department=self.department,
            program=None,
            is_active=True
        )
        
        # Set student's level
        StudentLevelSelection.objects.create(
            student=self.student,
            level=self.level_200
        )
        
        # Create admin user
        self.admin_user = User.objects.create_superuser(
            username="admin",
            password="adminpass123",
            email="admin@test.com"
        )
        
        # Set up API clients
        self.student_client = APIClient()
        self.student_client.force_authenticate(user=self.student_user)
        
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(user=self.admin_user)
    
    def test_complete_workflow(self):
        """Test the complete course registration and approval workflow"""
        
        # Step 1: Student marks timetable course as offering (auto-approved)
        from students.timetable_selection_service import mark_timetable_course_offering
        
        selection = mark_timetable_course_offering(
            self.student,
            self.course_200_1,
            self.level_200
        )
        
        self.assertTrue(selection.is_offered)
        self.assertTrue(selection.is_approved)  # Auto-approved
        
        # Step 2: Verify course appears in My Courses
        response = self.student_client.get('/students/courses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['courses']), 1)
        self.assertEqual(response.data['courses'][0]['course']['code'], 'CS201')
        
        # Step 3: Student registers for a course from another level (pending)
        response = self.student_client.post('/students/courses/register/', {
            'course_id': self.course_300_1.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'pending')
        
        # Step 4: Verify pending registration appears in pending list
        response = self.student_client.get('/students/courses/pending/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['pending_registrations']), 1)
        self.assertEqual(response.data['pending_registrations'][0]['course']['code'], 'CS301')
        
        # Step 5: Verify pending course does NOT appear in My Courses yet
        response = self.student_client.get('/students/courses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['courses']), 1)  # Only the approved timetable course
        
        # Step 6: Admin views pending registrations
        response = self.admin_client.get('/admin/course-registrations/pending/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['pending_registrations']), 1)
        
        pending_id = response.data['pending_registrations'][0]['id']
        
        # Step 7: Admin approves the registration
        response = self.admin_client.post(f'/admin/course-registrations/{pending_id}/approve/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 8: Verify approved course now appears in My Courses
        response = self.student_client.get('/students/courses/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['courses']), 2)  # Both courses now
        
        course_codes = [c['course']['code'] for c in response.data['courses']]
        self.assertIn('CS201', course_codes)
        self.assertIn('CS301', course_codes)
        
        # Step 9: Verify no more pending registrations
        response = self.student_client.get('/students/courses/pending/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['pending_registrations']), 0)
    
    def test_duplicate_registration_prevention(self):
        """Test that duplicate registrations are prevented"""
        
        # Mark course as offering (approved)
        from students.timetable_selection_service import mark_timetable_course_offering
        mark_timetable_course_offering(self.student, self.course_200_1, self.level_200)
        
        # Try to register for the same course again
        response = self.student_client.post('/students/courses/register/', {
            'course_id': self.course_200_1.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_cancellation_workflow(self):
        """Test student can cancel pending registrations"""
        
        # Register for a course
        response = self.student_client.post('/students/courses/register/', {
            'course_id': self.course_300_1.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        registration_id = response.data['id']
        
        # Cancel the registration
        response = self.student_client.delete(f'/students/courses/registration/{registration_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify no pending registrations
        response = self.student_client.get('/students/courses/pending/')
        self.assertEqual(len(response.data['pending_registrations']), 0)
        
        # Verify course is available for registration again
        response = self.student_client.get('/students/courses/available/')
        course_ids = [c['id'] for c in response.data['courses']]
        self.assertIn(self.course_300_1.id, course_ids)
    
    def test_rejection_workflow(self):
        """Test admin can reject pending registrations"""
        
        # Student registers for a course
        response = self.student_client.post('/students/courses/register/', {
            'course_id': self.course_300_1.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Admin gets pending registrations
        response = self.admin_client.get('/admin/course-registrations/pending/')
        pending_id = response.data['pending_registrations'][0]['id']
        
        # Admin rejects the registration
        response = self.admin_client.post(
            f'/admin/course-registrations/{pending_id}/reject/',
            {'reason': 'Course is full'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify registration is deleted
        self.assertFalse(
            StudentCourseSelection.objects.filter(id=pending_id).exists()
        )
        
        # Verify student has no pending registrations
        response = self.student_client.get('/students/courses/pending/')
        self.assertEqual(len(response.data['pending_registrations']), 0)
    
    def test_available_courses_filtering(self):
        """Test that available courses excludes approved and pending courses"""
        
        # Initially, all courses should be available
        response = self.student_client.get('/students/courses/available/')
        self.assertEqual(len(response.data['courses']), 3)
        
        # Mark one course as offering (approved)
        from students.timetable_selection_service import mark_timetable_course_offering
        mark_timetable_course_offering(self.student, self.course_200_1, self.level_200)
        
        # Register for another course (pending)
        self.student_client.post('/students/courses/register/', {
            'course_id': self.course_300_1.id
        })
        
        # Now only one course should be available
        response = self.student_client.get('/students/courses/available/')
        self.assertEqual(len(response.data['courses']), 1)
        self.assertEqual(response.data['courses'][0]['code'], 'CS202')
    
    def test_attendance_integration(self):
        """Test that approved courses are available for attendance tracking"""
        from students.course_selection_service import get_my_courses
        
        # Mark timetable course as offering
        from students.timetable_selection_service import mark_timetable_course_offering
        mark_timetable_course_offering(self.student, self.course_200_1, self.level_200)
        
        # Register and approve a direct registration
        from students.direct_registration_service import register_course_directly
        from students.approval_service import approve_registration
        
        selection = register_course_directly(self.student, self.course_300_1, self.level_300)
        approve_registration(selection.id, self.admin_user)
        
        # Get My Courses (same as attendance query)
        my_courses = get_my_courses(self.student)
        
        # Should have both courses
        self.assertEqual(my_courses.count(), 2)
        
        # All should be approved and offered
        for course_selection in my_courses:
            self.assertTrue(course_selection.is_offered)
            self.assertTrue(course_selection.is_approved)


class CourseRegistrationServiceTest(TestCase):
    """Unit tests for course registration services"""
    
    def setUp(self):
        """Set up test data"""
        # Create minimal test data
        self.institution = Institution.objects.create(name="Test Uni", code="TU")
        self.faculty = Faculty.objects.create(name="Faculty", code="FAC", institution=self.institution)
        self.department = Department.objects.create(name="Dept", code="DEP", faculty=self.faculty)
        self.level = Level.objects.create(name="200", code="200", department=self.department)
        
        self.course = Course.objects.create(
            code="CS201",
            title="Test Course",
            department=self.department,
            level=self.level,
            credit_units=3
        )
        
        self.user = User.objects.create_user(username="test", password="test")
        self.student = Student.objects.create(
            user=self.user,
            full_name="Test",
            matric_number="2020/001",
            institution=self.institution,
            faculty=self.faculty,
            department=self.department,
            program=None
        )
    
    def test_can_register_for_course(self):
        """Test duplicate detection logic"""
        from students.course_selection_service import can_register_for_course
        
        # Initially should be able to register
        can_register, reason = can_register_for_course(self.student, self.course)
        self.assertTrue(can_register)
        
        # Create approved registration
        StudentCourseSelection.objects.create(
            student=self.student,
            course=self.course,
            level=self.level,
            department=self.department,
            is_offered=True,
            is_approved=True
        )
        
        # Now should not be able to register
        can_register, reason = can_register_for_course(self.student, self.course)
        self.assertFalse(can_register)
        self.assertIn("already registered", reason.lower())
    
    def test_get_available_courses(self):
        """Test available courses query"""
        from students.course_selection_service import get_available_courses_for_registration
        
        # Create another course
        course2 = Course.objects.create(
            code="CS202",
            title="Test Course 2",
            department=self.department,
            level=self.level,
            credit_units=3
        )
        
        # Initially both courses available
        available = get_available_courses_for_registration(self.student)
        self.assertEqual(available.count(), 2)
        
        # Register for one course
        StudentCourseSelection.objects.create(
            student=self.student,
            course=self.course,
            level=self.level,
            department=self.department,
            is_offered=True,
            is_approved=False  # Even pending should exclude
        )
        
        # Now only one course available
        available = get_available_courses_for_registration(self.student)
        self.assertEqual(available.count(), 1)
        self.assertEqual(available.first().code, 'CS202')


if __name__ == '__main__':
    import django
    django.setup()
    from django.test.utils import get_runner
    from django.conf import settings
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(["students.test_course_registration_approval"])
