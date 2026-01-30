"""
API views for real-time attendance notifications
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.utils import timezone
from .notification_service import AttendanceNotificationService
from notifications.models import Notification
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_recent_attendance_notifications(request):
    """
    Get recent attendance notifications for the current user
    """
    try:
        limit = int(request.GET.get('limit', 10))
        hours = int(request.GET.get('hours', 24))
        
        logger.info(f"Recent notifications request from user: {request.user.username}, limit: {limit}, hours: {hours}")
        
        notifications = AttendanceNotificationService.get_recent_attendance_notifications(
            user=request.user,
            limit=limit,
            hours=hours
        )
        
        user_type = 'admin' if (hasattr(request.user, 'is_admin_user') and request.user.is_admin_user()) or request.user.is_staff else 'student'
        
        return Response({
            'success': True,
            'count': len(notifications),
            'notifications': notifications,
            'user_type': user_type
        })
        
    except Exception as e:
        logger.error(f"Error getting recent attendance notifications: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_live_attendance_feed(request):
    """
    Get live attendance feed for admin dashboard
    """
    try:
        # Debug logging
        logger.info(f"Live feed request from user: {request.user.username}, role: {getattr(request.user, 'role', 'unknown')}")
        
        # Check if user has admin role
        if not hasattr(request.user, 'role'):
            logger.warning(f"User {request.user.username} has no role attribute")
            return Response({
                'success': False,
                'error': 'User role not found'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Allow admin users and staff users to access live feed
        if not (request.user.is_admin_user() or request.user.is_staff or request.user.is_superuser):
            logger.warning(f"User {request.user.username} with role {request.user.role} denied access to live feed")
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        hours = int(request.GET.get('hours', 2))  # Default to last 2 hours for live feed
        limit = int(request.GET.get('limit', 20))
        
        logger.info(f"Fetching live feed for {hours} hours, limit {limit}")
        
        # Get recent attendance notifications
        notifications = AttendanceNotificationService.get_recent_attendance_notifications(
            user=request.user,
            limit=limit,
            hours=hours
        )
        
        # Get attendance summary
        summary_result = AttendanceNotificationService.get_attendance_summary_for_notifications(hours=hours)
        summary = summary_result.get('summary', {}) if summary_result.get('success') else {}
        
        logger.info(f"Live feed response: {len(notifications)} notifications, summary: {bool(summary)}")
        
        return Response({
            'success': True,
            'live_feed': {
                'notifications': notifications,
                'summary': summary,
                'time_period': f'Last {hours} hours',
                'last_updated': timezone.now().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting live attendance feed: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_attendance_notifications_read(request):
    """
    Mark attendance notifications as read
    """
    try:
        notification_ids = request.data.get('notification_ids')  # Optional: specific IDs
        
        result = AttendanceNotificationService.mark_attendance_notifications_read(
            user=request.user,
            notification_ids=notification_ids
        )
        
        return Response(result)
        
    except Exception as e:
        logger.error(f"Error marking attendance notifications as read: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attendance_notification_summary(request):
    """
    Get attendance notification summary for dashboard
    """
    try:
        hours = int(request.GET.get('hours', 24))
        
        logger.info(f"Notification summary request from user: {request.user.username}, hours: {hours}")
        
        # Get summary data
        summary_result = AttendanceNotificationService.get_attendance_summary_for_notifications(hours=hours)
        
        if not summary_result.get('success'):
            return Response({
                'success': False,
                'error': summary_result.get('error', 'Failed to get summary')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Get unread notification count for current user
        unread_count = Notification.objects.filter(
            recipient=request.user,
            notification_type__in=['attendance', 'success', 'warning', 'error'],
            is_read=False
        ).count()
        
        user_type = 'admin' if (hasattr(request.user, 'is_admin_user') and request.user.is_admin_user()) or request.user.is_staff else 'student'
        
        return Response({
            'success': True,
            'summary': summary_result['summary'],
            'user_notifications': {
                'unread_count': unread_count,
                'user_type': user_type
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting attendance notification summary: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_attendance_notifications(request):
    """
    Get attendance notifications specifically for student portal
    """
    try:
        # Get student-specific notifications
        limit = int(request.GET.get('limit', 10))
        hours = int(request.GET.get('hours', 168))  # Default to last week
        
        notifications = AttendanceNotificationService.get_recent_attendance_notifications(
            user=request.user,
            limit=limit,
            hours=hours
        )
        
        # Filter for student-relevant notifications
        student_notifications = [
            notification for notification in notifications
            if 'Your Attendance' in notification.get('title', '') or 
               notification.get('link', '').startswith('/student/')
        ]
        
        return Response({
            'success': True,
            'count': len(student_notifications),
            'notifications': student_notifications,
            'time_period': f'Last {hours} hours'
        })
        
    except Exception as e:
        logger.error(f"Error getting student attendance notifications: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def test_attendance_notification(request):
    """
    Test endpoint for creating sample attendance notifications (development only)
    """
    try:
        # Allow admin users and staff users to create test notifications
        if not ((hasattr(request.user, 'is_admin_user') and request.user.is_admin_user()) or request.user.is_staff or request.user.is_superuser):
            return Response({
                'success': False,
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Create a test notification
        test_notification = Notification.objects.create(
            recipient=request.user,
            title='🧪 Test Attendance Notification',
            message='This is a test notification for real-time attendance system',
            description=f'Generated at: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}\nUser: {request.user.get_full_name() or request.user.username}',
            notification_type='info',
            icon='test-tube',
            link='/admin/face-tracking/'
        )
        
        return Response({
            'success': True,
            'message': 'Test notification created successfully',
            'notification': {
                'id': test_notification.id,
                'title': test_notification.title,
                'message': test_notification.message,
                'created_at': test_notification.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating test attendance notification: {e}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)