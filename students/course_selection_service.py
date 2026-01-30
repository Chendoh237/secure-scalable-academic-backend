"""
Course Selection Service

Provides core business logic for course registration and approval workflows.
Supports two enrollment types:
1. Timetable-based enrollment (auto-approved)
2. Direct registration (requires admin approval)
"""

from django.db.models import Q
from students.models import StudentCourseSelection
from courses.models import Course


def can_register_for_course(student, course):
    """
    Determines if a student can register for a course.
    
    Args:
        student: Student instance
        course: Course instance
    
    Returns:
        tuple: (can_register: bool, reason: str)
    """
    # Check for existing approved registration
    existing_approved = StudentCourseSelection.objects.filter(
        student=student,
        course=course,
        is_approved=True
    ).exists()
    
    if existing_approved:
        return (False, "Already registered for this course")
    
    # Check for pending registration
    existing_pending = StudentCourseSelection.objects.filter(
        student=student,
        course=course,
        is_offered=True,
        is_approved=False
    ).exists()
    
    if existing_pending:
        return (False, "Registration already pending for this course")
    
    # Check department membership
    if course.department != student.department:
        return (False, "Course not in your department")
    
    return (True, "")


def get_available_courses_for_registration(student):
    """
    Returns courses available for direct registration.
    Excludes courses already approved or pending.
    
    Args:
        student: Student instance
    
    Returns:
        QuerySet: Available Course objects
    """
    # Get all courses in student's department
    department_courses = Course.objects.filter(
        department=student.department
    )
    
    # Get courses student is already registered for (approved or pending)
    registered_course_ids = StudentCourseSelection.objects.filter(
        student=student,
        is_offered=True
    ).values_list('course_id', flat=True)
    
    # Exclude registered courses
    available_courses = department_courses.exclude(
        id__in=registered_course_ids
    )
    
    return available_courses


def get_my_courses(student):
    """
    Returns all approved courses for a student.
    Includes both timetable and registered courses.
    
    Args:
        student: Student instance
    
    Returns:
        QuerySet: StudentCourseSelection objects with approved courses
    """
    return StudentCourseSelection.objects.filter(
        student=student,
        is_offered=True,
        is_approved=True
    ).select_related('course', 'level', 'department')


def get_pending_registrations(student):
    """
    Returns pending course registrations for a student.
    
    Args:
        student: Student instance
    
    Returns:
        QuerySet: StudentCourseSelection objects with pending registrations
    """
    return StudentCourseSelection.objects.filter(
        student=student,
        is_offered=True,
        is_approved=False
    ).select_related('course', 'level', 'department')
