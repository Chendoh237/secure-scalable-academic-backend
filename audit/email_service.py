"""
Email notification service for sending notifications
"""
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from .models import EmailLog
from django.contrib.auth import get_user_model
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class EmailNotificationService:
    """Service for sending email notifications"""
    
    TEMPLATES = {
        'student_approval': {
            'subject': 'Your Registration Has Been Approved',
            'template': 'emails/student_approval.html'
        },
        'student_rejection': {
            'subject': 'Your Registration Status',
            'template': 'emails/student_rejection.html'
        },
        'low_attendance_alert': {
            'subject': 'Low Attendance Alert',
            'template': 'emails/low_attendance_alert.html'
        },
        'course_registration_confirmation': {
            'subject': 'Course Registration Confirmation',
            'template': 'emails/course_registration.html'
        },
        'exam_eligibility_alert': {
            'subject': 'Exam Eligibility Notice',
            'template': 'emails/exam_eligibility.html'
        },
        'password_reset': {
            'subject': 'Reset Your Password',
            'template': 'emails/password_reset.html'
        },
        'admin_alert': {
            'subject': 'System Alert',
            'template': 'emails/admin_alert.html'
        },
    }
    
    @staticmethod
    def send_student_approval_email(student_email, student_name, admin_user=None):
        """Send student approval notification"""
        subject = "Your Registration Has Been Approved"
        context = {
            'student_name': student_name,
            'institution_name': getattr(settings, 'INSTITUTION_NAME', 'University'),
            'portal_url': getattr(settings, 'PORTAL_URL', 'http://localhost:5173'),
        }
        
        return EmailNotificationService._send_email(
            recipient=student_email,
            recipient_name=student_name,
            subject=subject,
            message_type='student_approval',
            context=context,
            initiated_by=admin_user,
            related_entity_type='student'
        )
    
    @staticmethod
    def send_low_attendance_alert(student_email, student_name, attendance_rate, course_name, admin_user=None):
        """Send low attendance alert"""
        subject = f"Low Attendance Alert - {course_name}"
        context = {
            'student_name': student_name,
            'course_name': course_name,
            'attendance_rate': attendance_rate,
            'threshold': getattr(settings, 'ATTENDANCE_THRESHOLD', 75),
            'institution_name': getattr(settings, 'INSTITUTION_NAME', 'University'),
        }
        
        return EmailNotificationService._send_email(
            recipient=student_email,
            recipient_name=student_name,
            subject=subject,
            message_type='low_attendance_alert',
            context=context,
            initiated_by=admin_user,
            related_entity_type='attendance'
        )
    
    @staticmethod
    def send_course_registration_confirmation(student_email, student_name, course_name, admin_user=None):
        """Send course registration confirmation"""
        subject = f"Course Registration Confirmation - {course_name}"
        context = {
            'student_name': student_name,
            'course_name': course_name,
            'institution_name': getattr(settings, 'INSTITUTION_NAME', 'University'),
        }
        
        return EmailNotificationService._send_email(
            recipient=student_email,
            recipient_name=student_name,
            subject=subject,
            message_type='course_registration_confirmation',
            context=context,
            initiated_by=admin_user,
            related_entity_type='course'
        )
    
    @staticmethod
    def send_exam_eligibility_notification(student_email, student_name, eligible_courses, admin_user=None):
        """Send exam eligibility notification"""
        subject = "Your Exam Eligibility Status"
        context = {
            'student_name': student_name,
            'eligible_courses': eligible_courses,
            'institution_name': getattr(settings, 'INSTITUTION_NAME', 'University'),
        }
        
        return EmailNotificationService._send_email(
            recipient=student_email,
            recipient_name=student_name,
            subject=subject,
            message_type='exam_eligibility_alert',
            context=context,
            initiated_by=admin_user,
            related_entity_type='student'
        )
    
    @staticmethod
    def send_admin_alert(admin_email, admin_name, alert_title, alert_message, severity='info', admin_user=None):
        """Send admin alert/notification"""
        subject = f"[{severity.upper()}] {alert_title}"
        context = {
            'admin_name': admin_name,
            'alert_title': alert_title,
            'alert_message': alert_message,
            'severity': severity,
            'institution_name': getattr(settings, 'INSTITUTION_NAME', 'University'),
        }
        
        return EmailNotificationService._send_email(
            recipient=admin_email,
            recipient_name=admin_name,
            subject=subject,
            message_type='admin_alert',
            context=context,
            initiated_by=admin_user,
            related_entity_type='settings'
        )
    
    @staticmethod
    def _send_email(recipient, recipient_name, subject, message_type, context=None, 
                    initiated_by=None, related_entity_type='', related_entity_id='', 
                    template='emails/default.html'):
        """
        Internal method to send email
        
        Args:
            recipient: Email address
            recipient_name: Recipient's name
            subject: Email subject
            message_type: Type of email (for logging)
            context: Template context
            initiated_by: User who initiated the email
            related_entity_type: Type of related entity
            related_entity_id: ID of related entity
            template: Template path
        """
        try:
            context = context or {}
            context['recipient_name'] = recipient_name
            context['subject'] = subject
            context['institution_name'] = getattr(settings, 'INSTITUTION_NAME', 'University')
            context['current_year'] = __import__('datetime').datetime.now().year
            
            # Generate HTML email body
            html_message = render_to_string(template, context)
            text_message = strip_tags(html_message)
            
            # Create email log entry
            email_log = EmailLog.objects.create(
                recipient=recipient,
                recipient_name=recipient_name,
                subject=subject,
                message_type=message_type,
                body=html_message,
                status='pending',
                initiated_by=initiated_by,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id
            )
            
            # Get email settings
            from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@university.local')
            
            # Try to send email
            try:
                # Create email message with HTML alternative
                email = EmailMultiAlternatives(
                    subject=subject,
                    body=text_message,
                    from_email=from_email,
                    to=[recipient]
                )
                email.attach_alternative(html_message, "text/html")
                
                # Check if email backend is configured
                if settings.EMAIL_BACKEND != 'django.core.mail.backends.console.EmailBackend':
                    email.send(fail_silently=False)
                else:
                    # Development mode - just log it
                    logger.info(f"[DEV MODE] Email would be sent to {recipient}: {subject}")
                
                # Update log
                email_log.status = 'sent'
                email_log.sent_at = __import__('django.utils.timezone', fromlist=['now']).now()
                email_log.save()
                
                logger.info(f"Email sent successfully to {recipient}: {subject}")
                return {'success': True, 'email_log_id': email_log.id, 'message': 'Email sent successfully'}
                
            except Exception as e:
                # Email sending failed
                email_log.status = 'failed'
                email_log.error_message = str(e)
                email_log.save()
                
                logger.error(f"Failed to send email to {recipient}: {str(e)}")
                return {'success': False, 'error': str(e), 'email_log_id': email_log.id}
        
        except Exception as e:
            logger.error(f"Error in email notification service: {str(e)}")
            return {'success': False, 'error': str(e)}


class BulkEmailService:
    """Service for sending bulk emails"""
    
    @staticmethod
    def send_low_attendance_alerts(students_data, admin_user=None):
        """
        Send low attendance alerts to multiple students
        
        Args:
            students_data: List of dicts with keys: email, name, attendance_rate, course_name
            admin_user: User initiating the bulk email
        
        Returns:
            Dict with success/failed counts
        """
        results = {'success': 0, 'failed': 0, 'email_logs': []}
        
        for student in students_data:
            try:
                result = EmailNotificationService.send_low_attendance_alert(
                    student_email=student['email'],
                    student_name=student['name'],
                    attendance_rate=student.get('attendance_rate', 0),
                    course_name=student.get('course_name', 'Unknown Course'),
                    admin_user=admin_user
                )
                
                if result.get('success'):
                    results['success'] += 1
                    results['email_logs'].append(result['email_log_id'])
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error sending alert to {student.get('email')}: {str(e)}")
                results['failed'] += 1
        
        return results
    
    @staticmethod
    def send_approval_notifications(approved_students, admin_user=None):
        """Send approval notifications to multiple students"""
        results = {'success': 0, 'failed': 0, 'email_logs': []}
        
        for student in approved_students:
            try:
                result = EmailNotificationService.send_student_approval_email(
                    student_email=student.get('email'),
                    student_name=student.get('name'),
                    admin_user=admin_user
                )
                
                if result.get('success'):
                    results['success'] += 1
                    results['email_logs'].append(result['email_log_id'])
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error sending approval to {student.get('email')}: {str(e)}")
                results['failed'] += 1
        
        return results
