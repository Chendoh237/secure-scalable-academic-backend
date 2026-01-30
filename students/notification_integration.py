"""
Email-Notification Integration Service

This service creates in-app notifications when emails are sent to students,
ensuring they receive instant notifications in the web application.
"""

import logging
from typing import List, Dict, Any
from django.contrib.auth import get_user_model
from notifications.models import Notification
from .models import Student

logger = logging.getLogger(__name__)

User = get_user_model()


class EmailNotificationIntegration:
    """
    Service for creating in-app notifications when emails are sent to students.
    """
    
    @staticmethod
    def create_email_notifications(
        sender_user,
        subject: str,
        body: str,
        recipients: List[str],
        email_history_id: int = None
    ) -> Dict[str, Any]:
        """
        Create in-app notifications for students when an email is sent.
        
        Args:
            sender_user: User who sent the email (admin)
            subject: Email subject
            body: Email body content
            recipients: List of recipient email addresses
            email_history_id: Optional email history record ID
            
        Returns:
            Dictionary with creation results
        """
        try:
            notifications_created = 0
            failed_notifications = 0
            
            # Get sender name for notification
            sender_name = getattr(sender_user, 'get_full_name', lambda: sender_user.username)()
            if not sender_name:
                sender_name = sender_user.username
            
            # Create notifications for each recipient
            for email in recipients:
                try:
                    # Find student by email
                    student = Student.objects.filter(user__email=email).first()
                    if not student or not student.user:
                        logger.warning(f"No student found for email: {email}")
                        failed_notifications += 1
                        continue
                    
                    # Create notification
                    notification = Notification.objects.create(
                        recipient=student.user,
                        title=f"📧 New Email: {subject}",
                        message=EmailNotificationIntegration._truncate_message(body),
                        notification_type='info',
                        description=f"Email from {sender_name}",
                        icon='mail',
                        link=f"/student/notifications" if email_history_id else ""
                    )
                    
                    notifications_created += 1
                    logger.info(f"Created notification for student: {student.full_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to create notification for {email}: {str(e)}")
                    failed_notifications += 1
            
            # Log summary
            logger.info(f"Email notifications created: {notifications_created}, failed: {failed_notifications}")
            
            return {
                'success': True,
                'notifications_created': notifications_created,
                'failed_notifications': failed_notifications,
                'total_recipients': len(recipients)
            }
            
        except Exception as e:
            logger.error(f"Failed to create email notifications: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'notifications_created': 0,
                'failed_notifications': len(recipients)
            }
    
    @staticmethod
    def create_system_announcement(
        sender_user,
        title: str,
        message: str,
        recipient_type: str = 'all',
        department_ids: List[int] = None,
        level_ids: List[str] = None,
        student_ids: List[int] = None
    ) -> Dict[str, Any]:
        """
        Create system-wide announcements as notifications.
        
        Args:
            sender_user: User creating the announcement
            title: Announcement title
            message: Announcement message
            recipient_type: Type of recipients ('all', 'department', 'level', 'specific')
            department_ids: List of department IDs (for department type)
            level_ids: List of level IDs (for level type)
            student_ids: List of student IDs (for specific type)
            
        Returns:
            Dictionary with creation results
        """
        try:
            from .recipient_service import recipient_service
            
            # Build recipient list using existing service
            recipient_config = {
                'type': recipient_type,
                'department_ids': department_ids or [],
                'level_ids': level_ids or [],
                'student_ids': student_ids or []
            }
            
            # Get student emails
            emails, metadata = recipient_service.build_recipient_list(recipient_config)
            
            # Get sender name
            sender_name = getattr(sender_user, 'get_full_name', lambda: sender_user.username)()
            if not sender_name:
                sender_name = sender_user.username
            
            notifications_created = 0
            failed_notifications = 0
            
            # Create notifications for each student
            for email in emails:
                try:
                    student = Student.objects.filter(user__email=email).first()
                    if not student or not student.user:
                        failed_notifications += 1
                        continue
                    
                    notification = Notification.objects.create(
                        recipient=student.user,
                        title=f"📢 {title}",
                        message=message,
                        notification_type='system',
                        description=f"System announcement from {sender_name}",
                        icon='megaphone',
                        link="/student/announcements"
                    )
                    
                    notifications_created += 1
                    
                except Exception as e:
                    logger.error(f"Failed to create announcement for {email}: {str(e)}")
                    failed_notifications += 1
            
            return {
                'success': True,
                'notifications_created': notifications_created,
                'failed_notifications': failed_notifications,
                'total_recipients': len(emails),
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to create system announcement: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'notifications_created': 0,
                'failed_notifications': 0
            }
    
    @staticmethod
    def create_course_notification(
        sender_user,
        title: str,
        message: str,
        course_id: int,
        department_id: int = None
    ) -> Dict[str, Any]:
        """
        Create course-specific notifications for enrolled students.
        
        Args:
            sender_user: User creating the notification
            title: Notification title
            message: Notification message
            course_id: Course ID
            department_id: Optional department filter
            
        Returns:
            Dictionary with creation results
        """
        try:
            # Get students enrolled in the course
            from .models import StudentCourseSelection
            
            queryset = StudentCourseSelection.objects.filter(
                course_id=course_id,
                is_offered=True,
                is_approved=True
            ).select_related('student', 'student__user')
            
            if department_id:
                queryset = queryset.filter(department_id=department_id)
            
            course_selections = queryset.all()
            
            # Get sender name
            sender_name = getattr(sender_user, 'get_full_name', lambda: sender_user.username)()
            if not sender_name:
                sender_name = sender_user.username
            
            notifications_created = 0
            failed_notifications = 0
            
            # Create notifications for enrolled students
            for selection in course_selections:
                try:
                    if not selection.student.user:
                        failed_notifications += 1
                        continue
                    
                    notification = Notification.objects.create(
                        recipient=selection.student.user,
                        title=f"📚 {title}",
                        message=message,
                        notification_type='course',
                        description=f"Course update from {sender_name}",
                        icon='book',
                        link=f"/student/courses/{course_id}"
                    )
                    
                    notifications_created += 1
                    
                except Exception as e:
                    logger.error(f"Failed to create course notification for {selection.student.full_name}: {str(e)}")
                    failed_notifications += 1
            
            return {
                'success': True,
                'notifications_created': notifications_created,
                'failed_notifications': failed_notifications,
                'total_recipients': len(course_selections)
            }
            
        except Exception as e:
            logger.error(f"Failed to create course notifications: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'notifications_created': 0,
                'failed_notifications': 0
            }
    
    @staticmethod
    def _truncate_message(message: str, max_length: int = 200) -> str:
        """
        Truncate message for notification display.
        
        Args:
            message: Original message
            max_length: Maximum length for truncated message
            
        Returns:
            Truncated message
        """
        if len(message) <= max_length:
            return message
        
        # Find last complete word within limit
        truncated = message[:max_length]
        last_space = truncated.rfind(' ')
        
        if last_space > 0:
            truncated = truncated[:last_space]
        
        return truncated + "..."
    
    @staticmethod
    def notify_email_delivery_status(
        email_history_id: int,
        recipient_email: str,
        delivery_status: str,
        error_message: str = None
    ) -> bool:
        """
        Notify student about email delivery status (optional feature).
        
        Args:
            email_history_id: Email history record ID
            recipient_email: Recipient email address
            delivery_status: Delivery status ('sent', 'delivered', 'failed', etc.)
            error_message: Optional error message
            
        Returns:
            True if notification created successfully
        """
        try:
            # Only notify on failures or important status changes
            if delivery_status not in ['failed', 'bounced']:
                return True
            
            # Find student
            student = Student.objects.filter(user__email=recipient_email).first()
            if not student or not student.user:
                return False
            
            # Create delivery status notification
            title = "📧 Email Delivery Issue"
            if delivery_status == 'failed':
                message = "We couldn't deliver a recent email to your address. Please check your email settings."
            elif delivery_status == 'bounced':
                message = "A recent email bounced back. Please verify your email address is correct."
            else:
                message = f"Email delivery status: {delivery_status}"
            
            if error_message:
                message += f" Error: {error_message}"
            
            notification = Notification.objects.create(
                recipient=student.user,
                title=title,
                message=message,
                notification_type='warning',
                description="Email delivery notification",
                icon='alert-triangle',
                link="/student/settings"
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to create delivery status notification: {str(e)}")
            return False


# Global integration service instance
email_notification_integration = EmailNotificationIntegration()