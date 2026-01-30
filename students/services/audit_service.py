"""
Course Selection Audit Service

This service handles the creation and management of audit logs for course selection changes.
It provides a centralized way to track all modifications to student course selections
for compliance, debugging, and administrative purposes.
"""

import uuid
from typing import Dict, Any, Optional, List
from django.utils import timezone
from django.db import transaction
from django.contrib.auth.models import AnonymousUser
import logging

from students.models import Student, StudentCourseSelection, CourseSelectionAuditLog
from courses.models import Course, Level, Department

logger = logging.getLogger(__name__)


class CourseSelectionAuditService:
    """
    Service for managing course selection audit trails
    """
    
    @staticmethod
    def log_course_selection_change(
        student: Student,
        course: Course,
        level: Level,
        department: Department,
        action: str,
        new_is_offered: bool,
        old_is_offered: Optional[bool] = None,
        request=None,
        change_reason: str = "",
        batch_id: Optional[uuid.UUID] = None
    ) -> CourseSelectionAuditLog:
        """
        Create an audit log entry for a course selection change.
        
        Args:
            student: The student making the change
            course: The course being modified
            level: The academic level
            department: The department
            action: The type of action ('CREATE', 'UPDATE', 'DELETE')
            new_is_offered: The new offering status
            old_is_offered: The previous offering status (None for CREATE)
            request: The HTTP request object (for extracting metadata)
            change_reason: Optional reason for the change
            batch_id: UUID for grouping related changes
            
        Returns:
            The created audit log entry
        """
        # Extract request metadata if available
        user_agent = ""
        ip_address = None
        session_key = ""
        
        if request:
            user_agent = request.META.get('HTTP_USER_AGENT', '')[:1000]  # Limit length
            
            # Get IP address (handle proxy headers)
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0].strip()
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            
            # Get session key if available
            if hasattr(request, 'session') and request.session.session_key:
                session_key = request.session.session_key
        
        # Create audit log entry
        audit_log = CourseSelectionAuditLog.objects.create(
            student=student,
            course=course,
            level=level,
            department=department,
            action=action,
            old_is_offered=old_is_offered,
            new_is_offered=new_is_offered,
            user_agent=user_agent,
            ip_address=ip_address,
            session_key=session_key,
            change_reason=change_reason,
            batch_id=batch_id
        )
        
        logger.info(
            f"Audit log created: {student.matric_number} - {course.code} - "
            f"{action} - {audit_log.change_summary}"
        )
        
        return audit_log
    
    @staticmethod
    @transaction.atomic
    def log_course_selection_creation(
        student: Student,
        course: Course,
        level: Level,
        department: Department,
        is_offered: bool,
        request=None,
        change_reason: str = "",
        batch_id: Optional[uuid.UUID] = None
    ) -> CourseSelectionAuditLog:
        """
        Log the creation of a new course selection.
        """
        return CourseSelectionAuditService.log_course_selection_change(
            student=student,
            course=course,
            level=level,
            department=department,
            action='CREATE',
            new_is_offered=is_offered,
            old_is_offered=None,
            request=request,
            change_reason=change_reason,
            batch_id=batch_id
        )
    
    @staticmethod
    @transaction.atomic
    def log_course_selection_update(
        student: Student,
        course: Course,
        level: Level,
        department: Department,
        old_is_offered: bool,
        new_is_offered: bool,
        request=None,
        change_reason: str = "",
        batch_id: Optional[uuid.UUID] = None
    ) -> CourseSelectionAuditLog:
        """
        Log the update of an existing course selection.
        """
        return CourseSelectionAuditService.log_course_selection_change(
            student=student,
            course=course,
            level=level,
            department=department,
            action='UPDATE',
            new_is_offered=new_is_offered,
            old_is_offered=old_is_offered,
            request=request,
            change_reason=change_reason,
            batch_id=batch_id
        )
    
    @staticmethod
    @transaction.atomic
    def log_course_selection_deletion(
        student: Student,
        course: Course,
        level: Level,
        department: Department,
        was_offered: bool,
        request=None,
        change_reason: str = "",
        batch_id: Optional[uuid.UUID] = None
    ) -> CourseSelectionAuditLog:
        """
        Log the deletion of a course selection.
        """
        return CourseSelectionAuditService.log_course_selection_change(
            student=student,
            course=course,
            level=level,
            department=department,
            action='DELETE',
            new_is_offered=False,  # Deletion implies no longer offered
            old_is_offered=was_offered,
            request=request,
            change_reason=change_reason,
            batch_id=batch_id
        )
    
    @staticmethod
    def get_student_audit_history(
        student: Student,
        limit: Optional[int] = None,
        course: Optional[Course] = None,
        action: Optional[str] = None
    ) -> List[CourseSelectionAuditLog]:
        """
        Get audit history for a specific student.
        
        Args:
            student: The student to get history for
            limit: Maximum number of entries to return
            course: Filter by specific course
            action: Filter by specific action type
            
        Returns:
            List of audit log entries
        """
        queryset = CourseSelectionAuditLog.objects.select_related(
            'student', 'course', 'level', 'department'
        ).filter(student=student)
        
        if course:
            queryset = queryset.filter(course=course)
        
        if action:
            queryset = queryset.filter(action=action)
        
        if limit:
            queryset = queryset[:limit]
        
        return list(queryset)
    
    @staticmethod
    def get_course_audit_history(
        course: Course,
        limit: Optional[int] = None,
        student: Optional[Student] = None,
        action: Optional[str] = None
    ) -> List[CourseSelectionAuditLog]:
        """
        Get audit history for a specific course.
        
        Args:
            course: The course to get history for
            limit: Maximum number of entries to return
            student: Filter by specific student
            action: Filter by specific action type
            
        Returns:
            List of audit log entries
        """
        queryset = CourseSelectionAuditLog.objects.select_related(
            'student', 'course', 'level', 'department'
        ).filter(course=course)
        
        if student:
            queryset = queryset.filter(student=student)
        
        if action:
            queryset = queryset.filter(action=action)
        
        if limit:
            queryset = queryset[:limit]
        
        return list(queryset)
    
    @staticmethod
    def get_audit_summary_for_student(student: Student) -> Dict[str, Any]:
        """
        Get a summary of audit activity for a student.
        
        Returns:
            Dictionary containing audit statistics and recent activity
        """
        logs = CourseSelectionAuditLog.objects.filter(student=student)
        
        # Count by action type
        action_counts = {}
        for action, _ in CourseSelectionAuditLog.ACTION_CHOICES:
            action_counts[action.lower()] = logs.filter(action=action).count()
        
        # Get recent activity
        recent_logs = logs.select_related('course')[:10]
        
        # Get unique courses modified
        unique_courses = logs.values_list('course__code', flat=True).distinct().count()
        
        return {
            'student': {
                'matric_number': student.matric_number,
                'full_name': student.full_name
            },
            'total_changes': logs.count(),
            'action_counts': action_counts,
            'unique_courses_modified': unique_courses,
            'first_change': logs.last().timestamp if logs.exists() else None,
            'last_change': logs.first().timestamp if logs.exists() else None,
            'recent_activity': [
                {
                    'course_code': log.course.code,
                    'action': log.action,
                    'change_summary': log.change_summary,
                    'timestamp': log.timestamp
                }
                for log in recent_logs
            ]
        }
    
    @staticmethod
    def get_department_audit_summary(department: Department) -> Dict[str, Any]:
        """
        Get audit summary for all students in a department.
        
        Returns:
            Dictionary containing department-wide audit statistics
        """
        logs = CourseSelectionAuditLog.objects.filter(department=department)
        
        # Count by action type
        action_counts = {}
        for action, _ in CourseSelectionAuditLog.ACTION_CHOICES:
            action_counts[action.lower()] = logs.filter(action=action).count()
        
        # Get unique students and courses
        unique_students = logs.values_list('student', flat=True).distinct().count()
        unique_courses = logs.values_list('course', flat=True).distinct().count()
        
        # Get recent activity
        recent_logs = logs.select_related('student', 'course')[:20]
        
        return {
            'department': {
                'name': department.name,
                'code': department.code
            },
            'total_changes': logs.count(),
            'action_counts': action_counts,
            'unique_students': unique_students,
            'unique_courses': unique_courses,
            'first_change': logs.last().timestamp if logs.exists() else None,
            'last_change': logs.first().timestamp if logs.exists() else None,
            'recent_activity': [
                {
                    'student_matric': log.student.matric_number,
                    'course_code': log.course.code,
                    'action': log.action,
                    'change_summary': log.change_summary,
                    'timestamp': log.timestamp
                }
                for log in recent_logs
            ]
        }
    
    @staticmethod
    @transaction.atomic
    def bulk_log_course_selections(
        selections_data: List[Dict[str, Any]],
        request=None,
        change_reason: str = "Bulk operation"
    ) -> List[CourseSelectionAuditLog]:
        """
        Log multiple course selection changes as a batch operation.
        
        Args:
            selections_data: List of dictionaries containing selection change data
            request: HTTP request object
            change_reason: Reason for the bulk operation
            
        Returns:
            List of created audit log entries
        """
        batch_id = uuid.uuid4()
        audit_logs = []
        
        for data in selections_data:
            audit_log = CourseSelectionAuditService.log_course_selection_change(
                student=data['student'],
                course=data['course'],
                level=data['level'],
                department=data['department'],
                action=data['action'],
                new_is_offered=data['new_is_offered'],
                old_is_offered=data.get('old_is_offered'),
                request=request,
                change_reason=change_reason,
                batch_id=batch_id
            )
            audit_logs.append(audit_log)
        
        logger.info(f"Bulk audit logging completed: {len(audit_logs)} entries with batch_id {batch_id}")
        return audit_logs
    
    @staticmethod
    def cleanup_old_audit_logs(days_to_keep: int = 365) -> int:
        """
        Clean up audit logs older than specified days.
        
        Args:
            days_to_keep: Number of days to retain audit logs
            
        Returns:
            Number of deleted audit log entries
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days_to_keep)
        
        deleted_count, _ = CourseSelectionAuditLog.objects.filter(
            timestamp__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} audit log entries older than {days_to_keep} days")
        return deleted_count


# Convenience functions for common operations
def log_course_selection_create(student, course, level, department, is_offered, request=None, reason=""):
    """Convenience function for logging course selection creation"""
    return CourseSelectionAuditService.log_course_selection_creation(
        student, course, level, department, is_offered, request, reason
    )


def log_course_selection_update(student, course, level, department, old_offered, new_offered, request=None, reason=""):
    """Convenience function for logging course selection updates"""
    return CourseSelectionAuditService.log_course_selection_update(
        student, course, level, department, old_offered, new_offered, request, reason
    )


def log_course_selection_delete(student, course, level, department, was_offered, request=None, reason=""):
    """Convenience function for logging course selection deletion"""
    return CourseSelectionAuditService.log_course_selection_deletion(
        student, course, level, department, was_offered, request, reason
    )


def get_student_audit_summary(student):
    """Convenience function for getting student audit summary"""
    return CourseSelectionAuditService.get_audit_summary_for_student(student)