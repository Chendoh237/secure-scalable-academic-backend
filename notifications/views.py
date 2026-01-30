from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import Notification
from .serializers import NotificationSerializer, NotificationCreateSerializer


class NotificationListView(APIView):
    """Get all notifications for authenticated user"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get all notifications for current user"""
        notifications = Notification.objects.filter(recipient=request.user)
        
        # Filter by read status if provided
        is_read = request.query_params.get('is_read')
        if is_read is not None:
            is_read_bool = is_read.lower() == 'true'
            notifications = notifications.filter(is_read=is_read_bool)
        
        # Filter by type if provided
        notification_type = request.query_params.get('type')
        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)
        
        serializer = NotificationSerializer(notifications, many=True)
        return Response({
            'success': True,
            'count': notifications.count(),
            'unread_count': notifications.filter(is_read=False).count(),
            'data': serializer.data
        })
    
    def post(self, request):
        """Create a new notification (admin only)"""
        if not request.user.is_admin_user():
            return Response({
                'success': False,
                'message': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        data = request.data.copy()
        data['recipient'] = request.user.id
        
        serializer = NotificationCreateSerializer(data=data)
        if serializer.is_valid():
            notification = serializer.save(recipient=request.user)
            return Response({
                'success': True,
                'message': 'Notification created successfully',
                'data': NotificationSerializer(notification).data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    """Mark a specific notification as read"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.mark_as_read()
        
        return Response({
            'success': True,
            'message': 'Notification marked as read',
            'data': NotificationSerializer(notification).data
        })
    except Notification.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Notification not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all unread notifications as read"""
    notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    )
    
    count = notifications.count()
    for notification in notifications:
        notification.mark_as_read()
    
    return Response({
        'success': True,
        'message': f'{count} notifications marked as read',
        'marked_count': count
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_unread(request, notification_id):
    """Mark a specific notification as unread"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.mark_as_unread()
        
        return Response({
            'success': True,
            'message': 'Notification marked as unread',
            'data': NotificationSerializer(notification).data
        })
    except Notification.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Notification not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Delete a specific notification"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.delete()
        
        return Response({
            'success': True,
            'message': 'Notification deleted successfully'
        })
    except Notification.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Notification not found'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_all_notifications(request):
    """Delete all notifications for current user"""
    count = Notification.objects.filter(recipient=request.user).delete()[0]
    
    return Response({
        'success': True,
        'message': f'{count} notifications deleted',
        'deleted_count': count
    })
