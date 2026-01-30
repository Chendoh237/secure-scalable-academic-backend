"""
Approval Service

Handles admin approval/rejection workflows for course registrations.
Admins can view pending registrations and approve or reject them.
"""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from students.models import StudentCourseSelection, CourseSelectionAuditLog


def get_all_pending_registrations():
    """
    Returns all pending course registrations across all students.
    
    Returns:
        QuerySet: StudentCourseSelection objects with pending registrations
    """
    return StudentCourseSelection.objects.filter(
        is_offered=True,
        is_approved=False
    ).select_related(
        'student',
        'student__user',
        'course',
        'level',
        'department'
    ).order_by('-created_at')


def approve_registration(registration_id, admin_user):
    """
    Approves a pending course registration.
    Updates is_approved=True, logs the action, and syncs to StudentCourse.
    
    Args:
        registration_id: ID of the StudentCourseSelection to approve
        admin_user: User instance of the admin performing the action
    
    Returns:
        dict: Success message with registration details
    
    Raises:
        ValidationError: If registration not found or already processed
    """
    try:
        selection = StudentCourseSelection.objects.select_related(
            'student', 'course'
        ).get(
            id=registration_id,
            is_offered=True,
            is_approved=False
        )
    except StudentCourseSelection.DoesNotExist:
        raise ValidationError("Registration not found or already processed")
    
    with transaction.atomic():
        # Update approval status
        selection.is_approved = True
        selection.save()
        
        # Sync approved course to StudentCourse model
        from .course_sync_service import sync_approved_courses_to_student_course
        try:
            sync_result = sync_approved_courses_to_student_course(selection.student)
            sync_message = f"Course sync: {sync_result.get('synced_count', 0)} courses synced"
        except Exception as e:
            sync_message = f"Course sync failed: {str(e)}"
        
        # Log the approval
        CourseSelectionAuditLog.objects.create(
            student=selection.student,
            course=selection.course,
            level=selection.level,
            department=selection.department,
            action='UPDATE',
            old_is_offered=True,
            new_is_offered=True,
            change_reason=f'Registration approved by admin: {admin_user.username}. {sync_message}'
        )
    
    return {
        'message': 'Registration approved successfully',
        'registration': {
            'id': selection.id,
            'student_name': selection.student.full_name,
            'course_code': selection.course.code,
            'course_title': selection.course.title,
            'approved_at': timezone.now().isoformat()
        },
        'sync_result': sync_message
    }


def reject_registration(registration_id, admin_user, reason=None):
    """
    Rejects a pending course registration.
    Deletes the StudentCourseSelection record and logs the action.
    
    Args:
        registration_id: ID of the StudentCourseSelection to reject
        admin_user: User instance of the admin performing the action
        reason: Optional reason for rejection
    
    Returns:
        dict: Success message
    
    Raises:
        ValidationError: If registration not found or already processed
    """
    try:
        selection = StudentCourseSelection.objects.select_related(
            'student', 'course'
        ).get(
            id=registration_id,
            is_offered=True,
            is_approved=False
        )
    except StudentCourseSelection.DoesNotExist:
        raise ValidationError("Registration not found or already processed")
    
    # Store info for logging
    student = selection.student
    course = selection.course
    level = selection.level
    department = selection.department
    
    with transaction.atomic():
        # Log the rejection before deletion
        rejection_reason = f'Registration rejected by admin: {admin_user.username}'
        if reason:
            rejection_reason += f' - Reason: {reason}'
        
        CourseSelectionAuditLog.objects.create(
            student=student,
            course=course,
            level=level,
            department=department,
            action='DELETE',
            old_is_offered=True,
            new_is_offered=False,
            change_reason=rejection_reason
        )
        
        # Delete the registration
        selection.delete()
    
    return {
        'message': 'Registration rejected successfully'
    }


def get_registration_history(student_id=None, action_filter=None):
    """
    Returns registration history with optional filtering.
    
    Args:
        student_id: Optional student ID to filter by
        action_filter: Optional action type to filter by ('CREATE', 'UPDATE', 'DELETE')
    
    Returns:
        QuerySet: CourseSelectionAuditLog objects
    """
    queryset = CourseSelectionAuditLog.objects.select_related(
        'student',
        'course',
        'level',
        'department'
    ).order_by('-timestamp')
    
    if student_id:
        queryset = queryset.filter(student_id=student_id)
    
    if action_filter:
        queryset = queryset.filter(action=action_filter)
    
    return queryset
