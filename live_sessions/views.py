from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.db.models import Count, Avg
import json
import uuid
import secrets

from .models import LiveSession, LiveSessionParticipant, LiveSessionRecording, LiveSessionMessage
from .serializers import (LiveSessionSerializer, LiveSessionCreateSerializer, 
                        LiveSessionParticipantSerializer, LiveSessionRecordingSerializer,
                        LiveSessionMessageSerializer)
from users.models import User

def generate_meeting_id():
    """Generate unique meeting ID"""
    return f"session_{uuid.uuid4().hex[:12]}"

def generate_meeting_password():
    """Generate random meeting password"""
    return secrets.token_hex(3).upper()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def live_sessions_list(request):
    """Get all live sessions"""
    sessions = LiveSession.objects.all()
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter:
        sessions = sessions.filter(status=status_filter)
    
    # Filter by instructor if provided
    instructor_id = request.GET.get('instructor')
    if instructor_id:
        sessions = sessions.filter(instructor_id=instructor_id)
    
    serializer = LiveSessionSerializer(sessions, many=True)
    return Response({
        'success': True,
        'data': serializer.data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_live_session(request):
    """Create a new live session"""
    try:
        data = request.data.copy()
        data['instructor'] = request.user.id
        data['meeting_id'] = generate_meeting_id()
        
        if data.get('require_password'):
            data['meeting_password'] = generate_meeting_password()
        
        serializer = LiveSessionCreateSerializer(data=data)
        if serializer.is_valid():
            session = serializer.save()
            
            # Log activity
            from users.views import log_admin_activity
            log_admin_activity(request, 'CREATE_LIVE_SESSION', f'Created live session: {session.title}')
            
            return Response({
                'success': True,
                'message': 'Live session created successfully',
                'data': LiveSessionSerializer(session).data
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'message': 'Validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_live_session(request, session_id):
    """Start a live session"""
    try:
        session = get_object_or_404(LiveSession, id=session_id)
        
        # Check permissions - allow admin users or session instructor
        if not (session.instructor == request.user or request.user.is_admin_user() or request.user.is_staff):
            return Response({
                'success': False,
                'message': 'Permission denied: You must be an admin or the session instructor'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if session.status != 'scheduled':
            return Response({
                'success': False,
                'message': 'Session cannot be started'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        session.start_session()
        
        # Log activity
        from users.views import log_admin_activity
        log_admin_activity(request, 'START_LIVE_SESSION', f'Started live session: {session.title}')
        
        return Response({
            'success': True,
            'message': 'Live session started',
            'data': LiveSessionSerializer(session).data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_live_session(request, session_id):
    """End a live session"""
    try:
        session = get_object_or_404(LiveSession, id=session_id)
        
        # Check permissions - allow admin users or session instructor
        if not (session.instructor == request.user or request.user.is_admin_user() or request.user.is_staff):
            return Response({
                'success': False,
                'message': 'Permission denied: You must be an admin or the session instructor'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if session.status != 'live':
            return Response({
                'success': False,
                'message': 'Session is not live'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        session.end_session()
        
        # Remove all active participants
        LiveSessionParticipant.objects.filter(session=session, is_active=True).update(
            is_active=False, 
            left_at=timezone.now()
        )
        
        # Log activity
        from users.views import log_admin_activity
        log_admin_activity(request, 'END_LIVE_SESSION', f'Ended live session: {session.title}')
        
        return Response({
            'success': True,
            'message': 'Live session ended',
            'data': LiveSessionSerializer(session).data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def live_session_participants(request, session_id):
    """Get session participants"""
    try:
        session = get_object_or_404(LiveSession, id=session_id)
        
        # Check permissions
        if session.instructor != request.user and not request.user.is_admin_user():
            return Response({
                'success': False,
                'message': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        participants = LiveSessionParticipant.objects.filter(session=session)
        serializer = LiveSessionParticipantSerializer(participants, many=True)
        
        return Response({
            'success': True,
            'data': serializer.data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def live_session_analytics(request, session_id):
    """Get session analytics"""
    try:
        session = get_object_or_404(LiveSession, id=session_id)
        
        # Check permissions
        if session.instructor != request.user and not request.user.is_admin_user():
            return Response({
                'success': False,
                'message': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Calculate analytics
        participants = LiveSessionParticipant.objects.filter(session=session)
        total_participants = participants.count()
        active_participants = participants.filter(is_active=True).count()
        
        # Connection quality stats
        quality_stats = participants.values('connection_quality').annotate(count=Count('id'))
        
        # Average participation duration
        avg_duration = participants.aggregate(
            avg_duration=Avg('total_duration')
        )['avg_duration'] or 0
        
        # Message stats
        message_count = LiveSessionMessage.objects.filter(session=session).count()
        
        analytics = {
            'total_participants': total_participants,
            'active_participants': active_participants,
            'peak_participants': session.peak_participants,
            'average_participation_duration': round(avg_duration, 2),
            'total_messages': message_count,
            'connection_quality_distribution': list(quality_stats),
            'session_duration': session.duration_minutes,
            'is_recorded': session.is_recorded,
            'recording_url': session.recording_url
        }
        
        return Response({
            'success': True,
            'data': analytics
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)