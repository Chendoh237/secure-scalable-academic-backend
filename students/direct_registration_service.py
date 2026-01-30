"""
Direct Registration Service

Handles direct course registration requiring admin approval.
Students can register for any course in their department, creating pending registrations.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from students.models import StudentCourseSelection, CourseSelectionAuditLog
from students.course_selection_service import can_register_for_course


def register_course_directly(student, course, level):
    """
    Creates a pending course registration for a student.
    Sets is_offered=True and is_approved=False (requires admin approval).
    
    Args:
        student: Student instance
        course: Course instance
        level: Level instance (the level the course belongs to)
    
    Returns:
        StudentCourseSelection: The created pending registration
    
    Raises:
        ValidationError: If registration is not allowed
    """
    # Validate registration eligibility
    can_register, reason = can_register_for_course(student, course)
    if not can_register:
        raise ValidationError(reason)
    
    with transaction.atomic():
        # Create pending registration
        selection = StudentCourseSelection.objects.create(
            student=student,
            course=course,
            level=level,
            department=student.department,
            is_offered=True,
            is_approved=False  # Requires admin approval
        )
        
        # Log the action
        CourseSelectionAuditLog.objects.create(
            student=student,
            course=course,
            level=level,
            department=student.department,
            action='CREATE',
            old_is_offered=None,
            new_is_offered=True,
            change_reason='Direct registration submitted (pending approval)'
        )
        
        return selection


def cancel_pending_registration(student, registration_id):
    """
    Cancels a pending course registration.
    Verifies the registration belongs to the student and is pending.
    
    Args:
        student: Student instance
        registration_id: ID of the StudentCourseSelection to cancel
    
    Returns:
        dict: Success message with course info
    
    Raises:
        ValidationError: If cancellation is not allowed
    """
    try:
        selection = StudentCourseSelection.objects.get(
            id=registration_id,
            student=student
        )
    except StudentCourseSelection.DoesNotExist:
        raise ValidationError("Registration not found or does not belong to you")
    
    # Verify registration is pending
    if selection.is_approved:
        raise ValidationError("Cannot cancel approved registration")
    
    # Store info for response
    course_code = selection.course.code
    course_title = selection.course.title
    
    with transaction.atomic():
        # Log the cancellation before deletion
        CourseSelectionAuditLog.objects.create(
            student=student,
            course=selection.course,
            level=selection.level,
            department=selection.department,
            action='DELETE',
            old_is_offered=selection.is_offered,
            new_is_offered=False,
            change_reason='Pending registration cancelled by student'
        )
        
        # Delete the registration
        selection.delete()
    
    return {
        'message': 'Registration cancelled successfully',
        'course_code': course_code,
        'course_title': course_title
    }
