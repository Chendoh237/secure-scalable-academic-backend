"""
Comprehensive API URL Configuration
Production-ready attendance management system endpoints
"""

from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Authentication endpoints
from authentication.jwt_auth import (
    login, logout, refresh_token, verify_token_endpoint, register_student
)

# Admin dashboard endpoints
from administration.admin_dashboard import (
    get_admin_dashboard_overview,
    get_attendance_analytics,
    get_student_performance_analytics,
    get_system_activity_logs,
    get_face_recognition_analytics,
    get_admin_alerts,
    export_attendance_report
)

# System configuration endpoints
from administration.system_config import (
    get_system_configuration,
    update_system_configuration,
    reset_configuration_to_defaults,
    get_attendance_thresholds,
    update_attendance_thresholds
)

# Student dashboard endpoints
from students.student_dashboard import (
    get_student_dashboard_overview,
    get_student_courses,
    get_student_timetable,
    get_student_attendance_history,
    register_for_course,
    withdraw_from_course
)

# Face tracking endpoints
from attendance.face_tracking_views import (
    process_face_frame,
    get_active_sessions,
    get_session_attendance,
    get_face_model_status,
    reload_face_models,
    get_today_attendance_summary,
    get_current_timetable_info,
    get_face_recognition_stats,
    get_live_attendance_feed,
    manual_attendance_override,
    retrain_face_models,
    simple_train_face_models,
    face_recognition_config
)

# Notification endpoints
from notifications.notification_system import (
    get_notifications,
    mark_notification_read,
    mark_all_notifications_read,
    delete_notification,
    get_unread_count
)

# Enhanced face recognition endpoints
def enhanced_face_recognition_urls():
    """Enhanced face recognition API endpoints"""
    from rest_framework.decorators import api_view, permission_classes
    from rest_framework.permissions import IsAuthenticated
    from rest_framework.response import Response
    from rest_framework import status
    from attendance.enhanced_face_recognition import enhanced_face_recognition_engine
    
    @api_view(['POST'])
    @permission_classes([IsAuthenticated])
    def train_face_models(request):
        """Train enhanced face recognition models"""
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        force_retrain = request.data.get('force_retrain', False)
        result = enhanced_face_recognition_engine.train_models(force_retrain)
        
        return Response({
            'success': result['success'],
            'message': result['message'],
            'data': result
        })
    
    @api_view(['GET'])
    @permission_classes([IsAuthenticated])
    def get_enhanced_model_status(request):
        """Get enhanced face recognition model status"""
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        status_info = enhanced_face_recognition_engine.get_model_status()
        
        return Response({
            'success': True,
            'data': status_info
        })
    
    @api_view(['POST'])
    @permission_classes([IsAuthenticated])
    def update_face_recognition_config(request):
        """Update face recognition configuration"""
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        config = request.data
        result = enhanced_face_recognition_engine.update_configuration(config)
        
        return Response(result)
    
    @api_view(['POST'])
    @permission_classes([IsAuthenticated])
    def process_enhanced_face_frame(request):
        """Process face frame with enhanced recognition engine"""
        frame_data = request.data.get('frame_data')
        session_id = request.data.get('session_id')
        department_id = request.data.get('department_id')
        
        if not frame_data:
            return Response({
                'success': False,
                'message': 'Frame data is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = enhanced_face_recognition_engine.process_frame(
            frame_data, session_id, department_id
        )
        
        return Response(result)
    
    return [
        path('enhanced/train/', train_face_models, name='train_enhanced_face_models'),
        path('enhanced/status/', get_enhanced_model_status, name='get_enhanced_model_status'),
        path('enhanced/config/', update_face_recognition_config, name='update_face_recognition_config'),
        path('enhanced/process/', process_enhanced_face_frame, name='process_enhanced_face_frame'),
    ]

# Main URL patterns
urlpatterns = [
    # Authentication endpoints
    path('auth/login/', login, name='login'),
    path('auth/logout/', logout, name='logout'),
    path('auth/refresh/', refresh_token, name='refresh_token'),
    path('auth/verify/', verify_token_endpoint, name='verify_token'),
    path('auth/register/student/', register_student, name='register_student'),
    
    # Admin dashboard endpoints
    path('admin/dashboard/overview/', get_admin_dashboard_overview, name='admin_dashboard_overview'),
    path('admin/analytics/attendance/', get_attendance_analytics, name='admin_attendance_analytics'),
    path('admin/analytics/students/', get_student_performance_analytics, name='admin_student_analytics'),
    path('admin/analytics/face-recognition/', get_face_recognition_analytics, name='admin_face_recognition_analytics'),
    path('admin/activity-logs/', get_system_activity_logs, name='admin_activity_logs'),
    path('admin/alerts/', get_admin_alerts, name='admin_alerts'),
    path('admin/export/attendance/', export_attendance_report, name='export_attendance_report'),
    
    # System configuration endpoints
    path('admin/config/', get_system_configuration, name='get_system_configuration'),
    path('admin/config/update/', update_system_configuration, name='update_system_configuration'),
    path('admin/config/reset/', reset_configuration_to_defaults, name='reset_configuration'),
    path('admin/config/attendance-thresholds/', get_attendance_thresholds, name='get_attendance_thresholds'),
    path('admin/config/attendance-thresholds/update/', update_attendance_thresholds, name='update_attendance_thresholds'),
    
    # Student dashboard endpoints
    path('student/dashboard/', get_student_dashboard_overview, name='student_dashboard'),
    path('student/courses/', get_student_courses, name='student_courses'),
    path('student/timetable/', get_student_timetable, name='student_timetable'),
    path('student/attendance/history/', get_student_attendance_history, name='student_attendance_history'),
    path('student/courses/register/', register_for_course, name='register_for_course'),
    path('student/courses/withdraw/', withdraw_from_course, name='withdraw_from_course'),
    
    # Face tracking endpoints
    path('face-tracking/process/', process_face_frame, name='process_face_frame'),
    path('face-tracking/sessions/active/', get_active_sessions, name='get_active_sessions'),
    path('face-tracking/sessions/<str:session_id>/attendance/', get_session_attendance, name='get_session_attendance'),
    path('face-tracking/models/status/', get_face_model_status, name='get_face_model_status'),
    path('face-tracking/models/reload/', reload_face_models, name='reload_face_models'),
    path('face-tracking/models/train/', retrain_face_models, name='retrain_face_models'),
    path('face-tracking/models/train/simple/', simple_train_face_models, name='simple_train_face_models'),
    path('face-tracking/config/', face_recognition_config, name='face_recognition_config'),
    path('face-tracking/attendance/today/', get_today_attendance_summary, name='get_today_attendance_summary'),
    path('face-tracking/timetable/current/', get_current_timetable_info, name='get_current_timetable_info'),
    path('face-tracking/stats/', get_face_recognition_stats, name='get_face_recognition_stats'),
    path('face-tracking/feed/live/', get_live_attendance_feed, name='get_live_attendance_feed'),
    path('face-tracking/attendance/manual/', manual_attendance_override, name='manual_attendance_override'),
    
    # Enhanced face recognition endpoints
    *enhanced_face_recognition_urls(),
    
    # Notification endpoints
    path('notifications/', get_notifications, name='get_notifications'),
    path('notifications/<str:notification_id>/read/', mark_notification_read, name='mark_notification_read'),
    path('notifications/read-all/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/<str:notification_id>/delete/', delete_notification, name='delete_notification'),
    path('notifications/unread-count/', get_unread_count, name='get_unread_count'),
    
    # Academic management endpoints (existing)
    path('departments/', include('institutions.urls')),
    path('courses/', include('courses.urls')),
    path('students/', include('students.urls')),
    path('attendance/', include('attendance.urls')),
    path('users/', include('users.urls')),
    
    # Live sessions endpoints (existing)
    path('live-sessions/', include('live_sessions.urls')),
    
    # Audit endpoints (existing)
    path('audit/', include('audit.urls')),
]

# Additional utility endpoints
def create_utility_endpoints():
    """Create utility endpoints for system health and information"""
    from rest_framework.decorators import api_view
    from rest_framework.response import Response
    from django.utils import timezone
    from django.db import connection
    
    @api_view(['GET'])
    def health_check(request):
        """System health check endpoint"""
        try:
            # Test database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            return Response({
                'status': 'healthy',
                'timestamp': timezone.now().isoformat(),
                'database': 'connected',
                'version': '1.0.0'
            })
        except Exception as e:
            return Response({
                'status': 'unhealthy',
                'timestamp': timezone.now().isoformat(),
                'error': str(e)
            }, status=500)
    
    @api_view(['GET'])
    def system_info(request):
        """Get system information"""
        from django.conf import settings
        
        return Response({
            'system_name': 'Attendance Management System',
            'version': '1.0.0',
            'environment': getattr(settings, 'ENVIRONMENT', 'development'),
            'features': {
                'face_recognition': True,
                'jwt_authentication': True,
                'notifications': True,
                'analytics': True,
                'multi_role_support': True,
                'real_time_tracking': True
            },
            'timestamp': timezone.now().isoformat()
        })
    
    return [
        path('health/', health_check, name='health_check'),
        path('system/info/', system_info, name='system_info'),
    ]

# Add utility endpoints
urlpatterns.extend(create_utility_endpoints())

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# API versioning support
v1_patterns = [
    path('v1/', include(urlpatterns)),
]

# Root API patterns
api_patterns = [
    path('api/', include(urlpatterns)),
    path('api/', include(v1_patterns)),
]