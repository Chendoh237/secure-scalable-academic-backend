"""
Audit logging service for tracking all administrative actions
"""
from .models import AuditLog
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    """Service for logging audit events"""
    
    @staticmethod
    def log_action(
        admin,
        action,
        entity_type,
        entity_id,
        entity_name='',
        description='',
        old_values=None,
        new_values=None,
        ip_address='',
        user_agent='',
        request_path='',
        success=True,
        error_message=''
    ):
        """
        Create an audit log entry
        
        Args:
            admin: User object (admin performing action)
            action: Action type (CREATE, UPDATE, DELETE, etc.)
            entity_type: Type of entity (student, course, department, etc.)
            entity_id: ID of the affected entity
            entity_name: Human-readable name of the entity
            description: Description of the action
            old_values: Previous values (dict)
            new_values: New values (dict)
            ip_address: IP address of request
            user_agent: User agent string
            request_path: API path
            success: Whether action succeeded
            error_message: Error message if failed
        """
        try:
            audit_log = AuditLog.objects.create(
                admin=admin,
                admin_username=admin.username if admin else 'system',
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id),
                entity_name=entity_name,
                description=description,
                old_values=old_values or {},
                new_values=new_values or {},
                ip_address=ip_address,
                user_agent=user_agent,
                request_path=request_path,
                success=success,
                error_message=error_message
            )
            logger.info(f"Audit log created: {audit_log}")
            return audit_log
        except Exception as e:
            logger.error(f"Failed to create audit log: {str(e)}")
            return None
    
    @staticmethod
    def log_student_approval(admin, student_id, student_name, ip_address='', user_agent=''):
        """Log student approval action"""
        return AuditLogger.log_action(
            admin=admin,
            action='APPROVE',
            entity_type='student',
            entity_id=student_id,
            entity_name=student_name,
            description=f"Approved student registration: {student_name}",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_student_creation(admin, student_id, student_data, ip_address='', user_agent=''):
        """Log student creation"""
        return AuditLogger.log_action(
            admin=admin,
            action='CREATE',
            entity_type='student',
            entity_id=student_id,
            entity_name=student_data.get('full_name', 'Unknown'),
            description=f"Created new student record",
            new_values=student_data,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_student_update(admin, student_id, student_name, old_values, new_values, ip_address='', user_agent=''):
        """Log student update"""
        return AuditLogger.log_action(
            admin=admin,
            action='UPDATE',
            entity_type='student',
            entity_id=student_id,
            entity_name=student_name,
            description=f"Updated student record: {student_name}",
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_student_deletion(admin, student_id, student_name, ip_address='', user_agent=''):
        """Log student deletion"""
        return AuditLogger.log_action(
            admin=admin,
            action='DELETE',
            entity_type='student',
            entity_id=student_id,
            entity_name=student_name,
            description=f"Deleted student record: {student_name}",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_course_operation(admin, action, course_id, course_name, data=None, ip_address='', user_agent=''):
        """Log course operations"""
        return AuditLogger.log_action(
            admin=admin,
            action=action,
            entity_type='course',
            entity_id=course_id,
            entity_name=course_name,
            description=f"{action.title()} course: {course_name}",
            new_values=data or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_settings_change(admin, setting_name, old_value, new_value, ip_address='', user_agent=''):
        """Log system settings changes"""
        return AuditLogger.log_action(
            admin=admin,
            action='SETTINGS_CHANGE',
            entity_type='settings',
            entity_id=setting_name,
            entity_name=setting_name,
            description=f"Changed setting: {setting_name}",
            old_values={'value': old_value},
            new_values={'value': new_value},
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_login(user, ip_address='', user_agent=''):
        """Log user login"""
        return AuditLogger.log_action(
            admin=user,
            action='LOGIN',
            entity_type='user',
            entity_id=user.id,
            entity_name=user.username,
            description=f"User logged in: {user.username}",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_logout(user, ip_address='', user_agent=''):
        """Log user logout"""
        return AuditLogger.log_action(
            admin=user,
            action='LOGOUT',
            entity_type='user',
            entity_id=user.id,
            entity_name=user.username,
            description=f"User logged out: {user.username}",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_export(admin, entity_type, export_format, count, ip_address='', user_agent=''):
        """Log data export"""
        return AuditLogger.log_action(
            admin=admin,
            action='EXPORT',
            entity_type=entity_type,
            entity_id='bulk_export',
            entity_name=f"Exported {count} {entity_type} records",
            description=f"Exported {count} {entity_type} records as {export_format}",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_import(admin, entity_type, count, success_count, failed_count, ip_address='', user_agent=''):
        """Log data import"""
        success = failed_count == 0
        return AuditLogger.log_action(
            admin=admin,
            action='IMPORT',
            entity_type=entity_type,
            entity_id='bulk_import',
            entity_name=f"Imported {success_count} {entity_type} records",
            description=f"Imported {count} {entity_type} records ({success_count} successful, {failed_count} failed)",
            new_values={'imported': success_count, 'failed': failed_count},
            ip_address=ip_address,
            user_agent=user_agent,
            success=success
        )


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def get_user_agent(request):
    """Get user agent from request"""
    return request.META.get('HTTP_USER_AGENT', '')
