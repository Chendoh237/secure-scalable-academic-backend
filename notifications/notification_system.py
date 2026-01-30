"""
Comprehensive Notification System
In-app notifications with WhatsApp integration architecture
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from django.db import models, transaction
from django.utils import timezone
from django.core.cache import cache
from django.template.loader import render_to_string
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import requests
from celery import shared_task
import uuid

from users.models import User
from students.models import Student
from administration.system_config import system_config_service

logger = logging.getLogger(__name__)

class Notification(models.Model):
    """
    In-app notification model
    """
    NOTIFICATION_TYPES = [
        ('info', 'Information'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('error', 'Error'),
        ('attendance', 'Attendance'),
        ('course', 'Course'),
        ('exam', 'Exam'),
        ('system', 'System'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='normal')
    
    # Metadata
    data = models.JSONField(default=dict, blank=True, help_text="Additional notification data")
    action_url = models.URLField(blank=True, help_text="URL for notification action")
    action_text = models.CharField(max_length=50, blank=True, help_text="Text for action button")
    
    # Status tracking
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_sent = models.BooleanField(default=True)
    sent_at = models.DateTimeField(auto_now_add=True)
    
    # External delivery tracking
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    whatsapp_sent = models.BooleanField(default=False)
    whatsapp_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Expiration
    expires_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type', 'created_at']),
            models.Index(fields=['priority', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.get_full_name()}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False


class NotificationTemplate(models.Model):
    """
    Notification templates for consistent messaging
    """
    TEMPLATE_TYPES = [
        ('attendance_low', 'Low Attendance Warning'),
        ('attendance_critical', 'Critical Attendance Warning'),
        ('course_approved', 'Course Registration Approved'),
        ('course_rejected', 'Course Registration Rejected'),
        ('exam_eligibility', 'Exam Eligibility Status'),
        ('session_reminder', 'Class Session Reminder'),
        ('system_maintenance', 'System Maintenance'),
        ('welcome', 'Welcome Message'),
    ]
    
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES, unique=True)
    title_template = models.CharField(max_length=200)
    message_template = models.TextField()
    email_template = models.TextField(blank=True)
    whatsapp_template = models.TextField(blank=True)
    
    # Template settings
    is_active = models.BooleanField(default=True)
    priority = models.CharField(max_length=10, choices=Notification.PRIORITY_LEVELS, default='normal')
    notification_type = models.CharField(max_length=20, choices=Notification.NOTIFICATION_TYPES, default='info')
    
    # Delivery settings
    send_email = models.BooleanField(default=False)
    send_whatsapp = models.BooleanField(default=False)
    expires_after_hours = models.PositiveIntegerField(default=72, help_text="Hours after which notification expires")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_template_type_display()}"
    
    def render_notification(self, context: Dict[str, Any]) -> Dict[str, str]:
        """Render notification content with context"""
        try:
            from django.template import Context, Template
            
            title = Template(self.title_template).render(Context(context))
            message = Template(self.message_template).render(Context(context))
            
            result = {
                'title': title,
                'message': message,
                'priority': self.priority,
                'notification_type': self.notification_type
            }
            
            if self.email_template:
                result['email_content'] = Template(self.email_template).render(Context(context))
            
            if self.whatsapp_template:
                result['whatsapp_content'] = Template(self.whatsapp_template).render(Context(context))
            
            return result
            
        except Exception as e:
            logger.error(f"Error rendering notification template {self.template_type}: {e}")
            return {
                'title': 'Notification',
                'message': 'You have a new notification',
                'priority': 'normal',
                'notification_type': 'info'
            }


class NotificationService:
    """
    Comprehensive notification service
    """
    
    def __init__(self):
        self.whatsapp_enabled = system_config_service.get_setting('notifications.enable_whatsapp_notifications', False)
        self.email_enabled = system_config_service.get_setting('notifications.enable_email_notifications', True)
        self.whatsapp_api_url = getattr(settings, 'WHATSAPP_API_URL', '')
        self.whatsapp_api_token = getattr(settings, 'WHATSAPP_API_TOKEN', '')
    
    def send_notification(self, 
                         recipient: User, 
                         title: str, 
                         message: str,
                         notification_type: str = 'info',
                         priority: str = 'normal',
                         data: Optional[Dict] = None,
                         action_url: str = '',
                         action_text: str = '',
                         send_email: bool = False,
                         send_whatsapp: bool = False,
                         expires_after_hours: int = 72) -> Notification:
        """Send a notification to a user"""
        try:
            # Calculate expiration
            expires_at = timezone.now() + timedelta(hours=expires_after_hours) if expires_after_hours > 0 else None
            
            # Create notification
            notification = Notification.objects.create(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority,
                data=data or {},
                action_url=action_url,
                action_text=action_text,
                expires_at=expires_at
            )
            
            # Send external notifications asynchronously
            if send_email and self.email_enabled:
                self._send_email_notification.delay(notification.id)
            
            if send_whatsapp and self.whatsapp_enabled:
                self._send_whatsapp_notification.delay(notification.id)
            
            # Update unread count cache
            self._update_unread_count_cache(recipient)
            
            logger.info(f"Notification sent to {recipient.email}: {title}")
            return notification
            
        except Exception as e:
            logger.error(f"Error sending notification to {recipient.email}: {e}")
            raise
    
    def send_template_notification(self,
                                 recipient: User,
                                 template_type: str,
                                 context: Dict[str, Any]) -> Optional[Notification]:
        """Send notification using a template"""
        try:
            template = NotificationTemplate.objects.get(
                template_type=template_type,
                is_active=True
            )
            
            # Render template
            rendered = template.render_notification(context)
            
            # Send notification
            notification = self.send_notification(
                recipient=recipient,
                title=rendered['title'],
                message=rendered['message'],
                notification_type=rendered['notification_type'],
                priority=rendered['priority'],
                data=context,
                send_email=template.send_email,
                send_whatsapp=template.send_whatsapp,
                expires_after_hours=template.expires_after_hours
            )
            
            return notification
            
        except NotificationTemplate.DoesNotExist:
            logger.warning(f"Notification template '{template_type}' not found")
            return None
        except Exception as e:
            logger.error(f"Error sending template notification: {e}")
            return None
    
    def send_bulk_notification(self,
                             recipients: List[User],
                             title: str,
                             message: str,
                             **kwargs) -> List[Notification]:
        """Send notification to multiple users"""
        notifications = []
        
        for recipient in recipients:
            try:
                notification = self.send_notification(
                    recipient=recipient,
                    title=title,
                    message=message,
                    **kwargs
                )
                notifications.append(notification)
            except Exception as e:
                logger.error(f"Error sending bulk notification to {recipient.email}: {e}")
                continue
        
        return notifications
    
    def get_user_notifications(self,
                             user: User,
                             unread_only: bool = False,
                             limit: int = 50,
                             notification_type: Optional[str] = None) -> List[Notification]:
        """Get notifications for a user"""
        try:
            queryset = Notification.objects.filter(recipient=user)
            
            if unread_only:
                queryset = queryset.filter(is_read=False)
            
            if notification_type:
                queryset = queryset.filter(notification_type=notification_type)
            
            # Exclude expired notifications
            queryset = queryset.filter(
                models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
            )
            
            return list(queryset.order_by('-created_at')[:limit])
            
        except Exception as e:
            logger.error(f"Error getting notifications for user {user.id}: {e}")
            return []
    
    def mark_notification_as_read(self, notification_id: str, user: User) -> bool:
        """Mark a notification as read"""
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=user
            )
            notification.mark_as_read()
            
            # Update unread count cache
            self._update_unread_count_cache(user)
            
            return True
            
        except Notification.DoesNotExist:
            logger.warning(f"Notification {notification_id} not found for user {user.id}")
            return False
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False
    
    def mark_all_as_read(self, user: User) -> int:
        """Mark all notifications as read for a user"""
        try:
            count = Notification.objects.filter(
                recipient=user,
                is_read=False
            ).update(
                is_read=True,
                read_at=timezone.now()
            )
            
            # Update unread count cache
            self._update_unread_count_cache(user)
            
            return count
            
        except Exception as e:
            logger.error(f"Error marking all notifications as read for user {user.id}: {e}")
            return 0
    
    def get_unread_count(self, user: User) -> int:
        """Get unread notification count for user"""
        try:
            # Try cache first
            cache_key = f"unread_notifications:{user.id}"
            count = cache.get(cache_key)
            
            if count is None:
                count = Notification.objects.filter(
                    recipient=user,
                    is_read=False
                ).filter(
                    models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
                ).count()
                
                # Cache for 5 minutes
                cache.set(cache_key, count, 300)
            
            return count
            
        except Exception as e:
            logger.error(f"Error getting unread count for user {user.id}: {e}")
            return 0
    
    def delete_notification(self, notification_id: str, user: User) -> bool:
        """Delete a notification"""
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=user
            )
            notification.delete()
            
            # Update unread count cache
            self._update_unread_count_cache(user)
            
            return True
            
        except Notification.DoesNotExist:
            return False
        except Exception as e:
            logger.error(f"Error deleting notification: {e}")
            return False
    
    def cleanup_expired_notifications(self) -> int:
        """Clean up expired notifications"""
        try:
            count = Notification.objects.filter(
                expires_at__lt=timezone.now()
            ).delete()[0]
            
            logger.info(f"Cleaned up {count} expired notifications")
            return count
            
        except Exception as e:
            logger.error(f"Error cleaning up expired notifications: {e}")
            return 0
    
    def _update_unread_count_cache(self, user: User):
        """Update unread count cache for user"""
        try:
            cache_key = f"unread_notifications:{user.id}"
            cache.delete(cache_key)
        except Exception as e:
            logger.error(f"Error updating unread count cache: {e}")
    
    @shared_task
    def _send_email_notification(self, notification_id: str):
        """Send email notification (Celery task)"""
        try:
            notification = Notification.objects.get(id=notification_id)
            
            # Import Django email functionality
            from django.core.mail import send_mail
            from django.conf import settings
            from django.template.loader import render_to_string
            
            # Get user's email
            recipient_email = notification.recipient.email
            if not recipient_email:
                logger.warning(f"No email address for user {notification.recipient.id}")
                return
            
            # Prepare email content
            subject = f"[{getattr(settings, 'INSTITUTION_NAME', 'University')}] {notification.title}"
            
            # Try to render email template if available
            try:
                # Look for notification template
                template = NotificationTemplate.objects.get(
                    template_type=notification.notification_type,
                    is_active=True
                )
                if template.email_template:
                    context = notification.data or {}
                    context.update({
                        'title': notification.title,
                        'message': notification.message,
                        'recipient_name': notification.recipient.get_full_name(),
                        'action_url': notification.action_url,
                        'action_text': notification.action_text
                    })
                    
                    from django.template import Context, Template
                    email_body = Template(template.email_template).render(Context(context))
                else:
                    email_body = notification.message
            except NotificationTemplate.DoesNotExist:
                email_body = notification.message
            
            # Send email
            try:
                send_mail(
                    subject=subject,
                    message=email_body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@university.edu'),
                    recipient_list=[recipient_email],
                    fail_silently=False,
                    html_message=email_body if '<' in email_body else None
                )
                
                # Mark as sent
                notification.email_sent = True
                notification.email_sent_at = timezone.now()
                notification.save(update_fields=['email_sent', 'email_sent_at'])
                
                logger.info(f"Email notification sent to {recipient_email} for notification {notification.id}")
                
            except Exception as email_error:
                logger.error(f"Failed to send email to {recipient_email}: {email_error}")
                
        except Notification.DoesNotExist:
            logger.error(f"Notification {notification_id} not found")
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
    
    @shared_task
    def _send_whatsapp_notification(self, notification_id: str):
        """Send WhatsApp notification (Celery task)"""
        try:
            notification = Notification.objects.get(id=notification_id)
            
            if not self.whatsapp_enabled or not self.whatsapp_api_url:
                logger.warning("WhatsApp notifications not configured")
                return
            
            # Get user's phone number
            phone_number = getattr(notification.recipient, 'phone_number', '')
            if not phone_number:
                logger.warning(f"No phone number for user {notification.recipient.id}")
                return
            
            # Prepare WhatsApp message
            message_data = {
                'to': phone_number,
                'type': 'text',
                'text': {
                    'body': f"{notification.title}\n\n{notification.message}"
                }
            }
            
            # Send via WhatsApp API
            headers = {
                'Authorization': f'Bearer {self.whatsapp_api_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(
                self.whatsapp_api_url,
                json=message_data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                notification.whatsapp_sent = True
                notification.whatsapp_sent_at = timezone.now()
                notification.save(update_fields=['whatsapp_sent', 'whatsapp_sent_at'])
                logger.info(f"WhatsApp notification sent for {notification.id}")
            else:
                logger.error(f"WhatsApp API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Error sending WhatsApp notification: {e}")


# Global notification service instance
notification_service = NotificationService()


# Attendance-specific notification functions
def send_low_attendance_warning(student: Student, attendance_rate: float, course_code: str = None):
    """Send low attendance warning to student"""
    try:
        context = {
            'student_name': student.full_name,
            'matric_number': student.matric_number,
            'attendance_rate': attendance_rate,
            'course_code': course_code or 'overall',
            'threshold': system_config_service.get_setting('notifications.low_attendance_warning_threshold', 60.0)
        }
        
        notification_service.send_template_notification(
            recipient=student.user,
            template_type='attendance_low',
            context=context
        )
        
    except Exception as e:
        logger.error(f"Error sending low attendance warning: {e}")


def send_course_registration_notification(student: Student, course_code: str, status: str, reason: str = ''):
    """Send course registration status notification"""
    try:
        template_type = 'course_approved' if status in ['approved', 'auto_approved'] else 'course_rejected'
        
        context = {
            'student_name': student.full_name,
            'course_code': course_code,
            'status': status,
            'reason': reason
        }
        
        notification_service.send_template_notification(
            recipient=student.user,
            template_type=template_type,
            context=context
        )
        
    except Exception as e:
        logger.error(f"Error sending course registration notification: {e}")


def send_exam_eligibility_notification(student: Student, eligible_courses: List[str], ineligible_courses: List[str]):
    """Send exam eligibility notification"""
    try:
        context = {
            'student_name': student.full_name,
            'eligible_courses': eligible_courses,
            'ineligible_courses': ineligible_courses,
            'threshold': system_config_service.get_setting('attendance.exam_eligibility_threshold', 75.0)
        }
        
        notification_service.send_template_notification(
            recipient=student.user,
            template_type='exam_eligibility',
            context=context
        )
        
    except Exception as e:
        logger.error(f"Error sending exam eligibility notification: {e}")


# API Endpoints
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """Get notifications for the current user"""
    try:
        unread_only = request.GET.get('unread_only', 'false').lower() == 'true'
        limit = int(request.GET.get('limit', 50))
        notification_type = request.GET.get('type')
        
        notifications = notification_service.get_user_notifications(
            user=request.user,
            unread_only=unread_only,
            limit=limit,
            notification_type=notification_type
        )
        
        notifications_data = []
        for notification in notifications:
            notifications_data.append({
                'id': str(notification.id),
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type,
                'priority': notification.priority,
                'is_read': notification.is_read,
                'read_at': notification.read_at.isoformat() if notification.read_at else None,
                'created_at': notification.created_at.isoformat(),
                'action_url': notification.action_url,
                'action_text': notification.action_text,
                'data': notification.data,
                'expires_at': notification.expires_at.isoformat() if notification.expires_at else None
            })
        
        unread_count = notification_service.get_unread_count(request.user)
        
        return Response({
            'success': True,
            'data': {
                'notifications': notifications_data,
                'unread_count': unread_count,
                'total_count': len(notifications_data)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get notifications'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    try:
        success = notification_service.mark_notification_as_read(notification_id, request.user)
        
        if success:
            return Response({
                'success': True,
                'message': 'Notification marked as read'
            })
        else:
            return Response({
                'success': False,
                'message': 'Notification not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Error marking notification as read: {e}")
        return Response({
            'success': False,
            'message': 'Failed to mark notification as read'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    try:
        count = notification_service.mark_all_as_read(request.user)
        
        return Response({
            'success': True,
            'message': f'Marked {count} notifications as read',
            'data': {
                'marked_count': count
            }
        })
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {e}")
        return Response({
            'success': False,
            'message': 'Failed to mark notifications as read'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete a notification"""
    try:
        success = notification_service.delete_notification(notification_id, request.user)
        
        if success:
            return Response({
                'success': True,
                'message': 'Notification deleted'
            })
        else:
            return Response({
                'success': False,
                'message': 'Notification not found'
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        logger.error(f"Error deleting notification: {e}")
        return Response({
            'success': False,
            'message': 'Failed to delete notification'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    """Get unread notification count"""
    try:
        count = notification_service.get_unread_count(request.user)
        
        return Response({
            'success': True,
            'data': {
                'unread_count': count
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting unread count: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get unread count'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)