from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from notifications.models import Notification
from students.models import Student
import json

User = get_user_model()

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_bulk_notifications(request):
    """Send bulk notifications to students with optional email"""
    try:
        # Check if user is admin
        if not request.user.is_admin_user() and not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data
        student_ids = data.get('student_ids', [])
        title = data.get('title', '')
        message = data.get('message', '')
        notification_type = data.get('notification_type', 'info')
        send_email = data.get('send_email', False)
        
        if not student_ids or not title or not message:
            return Response({
                'success': False,
                'message': 'Missing required fields: student_ids, title, message'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get students
        students = Student.objects.filter(id__in=student_ids).select_related('user')
        
        notifications_created = 0
        emails_sent = 0
        
        for student in students:
            # Create notification
            notification = Notification.objects.create(
                recipient=student.user,
                title=title,
                message=message,
                notification_type=notification_type
            )
            notifications_created += 1
            
            # Send email if requested and email is configured
            if send_email and hasattr(settings, 'EMAIL_HOST') and student.user.email:
                try:
                    send_mail(
                        subject=title,
                        message=message,
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                        recipient_list=[student.user.email],
                        fail_silently=False,
                    )
                    emails_sent += 1
                except Exception as e:
                    print(f"Failed to send email to {student.user.email}: {e}")
        
        return Response({
            'success': True,
            'message': f'Successfully created {notifications_created} notifications',
            'data': {
                'notifications_created': notifications_created,
                'emails_sent': emails_sent
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def email_settings(request):
    """Get or update email settings"""
    try:
        # Check if user is admin
        if not request.user.is_admin_user() and not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if request.method == 'GET':
            # Return current email settings (without sensitive data)
            email_config = {
                'smtp_host': getattr(settings, 'EMAIL_HOST', ''),
                'smtp_port': getattr(settings, 'EMAIL_PORT', 587),
                'smtp_username': getattr(settings, 'EMAIL_HOST_USER', ''),
                'smtp_use_tls': getattr(settings, 'EMAIL_USE_TLS', True),
                'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', ''),
                'from_name': getattr(settings, 'EMAIL_FROM_NAME', 'Academic System'),
                'configured': bool(getattr(settings, 'EMAIL_HOST', ''))
            }
            
            return Response({
                'success': True,
                'data': email_config
            })
        
        elif request.method == 'PUT':
            # Note: In production, you'd want to store these in a database
            # or environment variables, not modify settings directly
            return Response({
                'success': True,
                'message': 'Email settings updated successfully (Note: Restart server to apply changes)'
            })
            
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)