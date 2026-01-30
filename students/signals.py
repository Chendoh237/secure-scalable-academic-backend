"""
Django signals for automatic audit logging of course selection changes.

These signals automatically create audit log entries whenever StudentCourseSelection
objects are created, updated, or deleted, ensuring complete traceability of all
course selection modifications.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.db import transaction
import logging
import threading

from students.models import StudentCourseSelection, CourseSelectionAuditLog
from students.services.audit_service import CourseSelectionAuditService

logger = logging.getLogger(__name__)

# Thread-local storage for request context
_thread_locals = threading.local()


def set_current_request(request):
    """Set the current request in thread-local storage for signal handlers"""
    _thread_locals.request = request


def get_current_request():
    """Get the current request from thread-local storage"""
    return getattr(_thread_locals, 'request', None)


def set_change_reason(reason):
    """Set a change reason in thread-local storage"""
    _thread_locals.change_reason = reason


def get_change_reason():
    """Get the change reason from thread-local storage"""
    return getattr(_thread_locals, 'change_reason', '')


def clear_thread_locals():
    """Clear thread-local storage"""
    for attr in ['request', 'change_reason']:
        if hasattr(_thread_locals, attr):
            delattr(_thread_locals, attr)


@receiver(pre_save, sender=StudentCourseSelection)
def capture_old_course_selection_state(sender, instance, **kwargs):
    """
    Capture the old state of a course selection before it's saved.
    This is needed for UPDATE operations to track what changed.
    """
    if instance.pk:  # Only for existing objects (updates)
        try:
            old_instance = StudentCourseSelection.objects.get(pk=instance.pk)
            # Store old state in the instance for use in post_save
            instance._old_is_offered = old_instance.is_offered
        except StudentCourseSelection.DoesNotExist:
            # Object doesn't exist yet, this shouldn't happen but handle gracefully
            instance._old_is_offered = None
    else:
        # New object, no old state
        instance._old_is_offered = None


@receiver(post_save, sender=StudentCourseSelection)
def log_course_selection_save(sender, instance, created, **kwargs):
    """
    Automatically log course selection creation and updates.
    """
    try:
        request = get_current_request()
        change_reason = get_change_reason()
        
        if created:
            # Log creation
            CourseSelectionAuditService.log_course_selection_creation(
                student=instance.student,
                course=instance.course,
                level=instance.level,
                department=instance.department,
                is_offered=instance.is_offered,
                request=request,
                change_reason=change_reason or "Course selection created"
            )
            logger.info(f"Logged course selection creation: {instance.student.matric_number} - {instance.course.code}")
        else:
            # Log update
            old_is_offered = getattr(instance, '_old_is_offered', None)
            
            # Only log if the offering status actually changed
            if old_is_offered is not None and old_is_offered != instance.is_offered:
                CourseSelectionAuditService.log_course_selection_update(
                    student=instance.student,
                    course=instance.course,
                    level=instance.level,
                    department=instance.department,
                    old_is_offered=old_is_offered,
                    new_is_offered=instance.is_offered,
                    request=request,
                    change_reason=change_reason or "Course selection updated"
                )
                logger.info(f"Logged course selection update: {instance.student.matric_number} - {instance.course.code}")
            
            # Clean up the temporary attribute
            if hasattr(instance, '_old_is_offered'):
                delattr(instance, '_old_is_offered')
                
    except Exception as e:
        # Don't let audit logging failures break the main operation
        logger.error(f"Error logging course selection save: {e}")


@receiver(post_delete, sender=StudentCourseSelection)
def log_course_selection_delete(sender, instance, **kwargs):
    """
    Automatically log course selection deletions.
    """
    try:
        request = get_current_request()
        change_reason = get_change_reason()
        
        CourseSelectionAuditService.log_course_selection_deletion(
            student=instance.student,
            course=instance.course,
            level=instance.level,
            department=instance.department,
            was_offered=instance.is_offered,
            request=request,
            change_reason=change_reason or "Course selection deleted"
        )
        logger.info(f"Logged course selection deletion: {instance.student.matric_number} - {instance.course.code}")
        
    except Exception as e:
        # Don't let audit logging failures break the main operation
        logger.error(f"Error logging course selection deletion: {e}")


# Context managers for setting request and change reason
class AuditContext:
    """Context manager for setting audit context (request and change reason)"""
    
    def __init__(self, request=None, change_reason=""):
        self.request = request
        self.change_reason = change_reason
        self.old_request = None
        self.old_reason = None
    
    def __enter__(self):
        # Save old values
        self.old_request = get_current_request()
        self.old_reason = get_change_reason()
        
        # Set new values
        if self.request:
            set_current_request(self.request)
        if self.change_reason:
            set_change_reason(self.change_reason)
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore old values
        clear_thread_locals()
        if self.old_request:
            set_current_request(self.old_request)
        if self.old_reason:
            set_change_reason(self.old_reason)


# Middleware for automatically setting request context
class CourseSelectionAuditMiddleware:
    """
    Middleware to automatically set the current request in thread-local storage
    for audit logging purposes.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Set request in thread-local storage
        set_current_request(request)
        
        try:
            response = self.get_response(request)
        finally:
            # Clean up thread-local storage
            clear_thread_locals()
        
        return response


# Utility functions for manual audit logging
def with_audit_context(request=None, change_reason=""):
    """
    Decorator/context manager for setting audit context.
    
    Usage as decorator:
    @with_audit_context(request=request, change_reason="Bulk update")
    def my_function():
        # Course selection changes here will be logged with context
        pass
    
    Usage as context manager:
    with with_audit_context(request=request, change_reason="Manual change"):
        # Course selection changes here will be logged with context
        pass
    """
    return AuditContext(request=request, change_reason=change_reason)


def bulk_update_course_selections_with_audit(selections_data, request=None, change_reason="Bulk update"):
    """
    Perform bulk course selection updates with proper audit logging.
    
    Args:
        selections_data: List of dicts with keys: student, course, level, department, is_offered
        request: HTTP request object
        change_reason: Reason for the bulk operation
    """
    with AuditContext(request=request, change_reason=change_reason):
        with transaction.atomic():
            for data in selections_data:
                selection, created = StudentCourseSelection.objects.get_or_create(
                    student=data['student'],
                    course=data['course'],
                    level=data['level'],
                    defaults={
                        'department': data['department'],
                        'is_offered': data['is_offered']
                    }
                )
                
                if not created and selection.is_offered != data['is_offered']:
                    selection.is_offered = data['is_offered']
                    selection.save()