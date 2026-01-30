from django.urls import path
from .views import face_attendance, manual_attendance, attendance_validation_info
from . import face_tracking_views, notification_views
from django.http import JsonResponse

urlpatterns = [
    path("face-attendance/", face_attendance),
    path("manual-attendance/", manual_attendance),
    path("attendance-validation-info/", attendance_validation_info),
    
    # Face Tracking API endpoints
    path('face-tracking/process-frame/', face_tracking_views.process_face_frame, name='process_face_frame'),
    path('face-tracking/active-sessions/', face_tracking_views.get_active_sessions, name='get_active_sessions'),
    path('face-tracking/session/<uuid:session_id>/attendance/', face_tracking_views.get_session_attendance, name='get_session_attendance'),
    path('face-tracking/model-status/', face_tracking_views.get_face_model_status, name='get_face_model_status'),
    path('face-tracking/reload-models/', face_tracking_views.reload_face_models, name='reload_face_models'),
    path('face-tracking/attendance-summary/', face_tracking_views.get_today_attendance_summary, name='get_today_attendance_summary'),
    path('face-tracking/current-timetable/', face_tracking_views.get_current_timetable_info, name='get_current_timetable_info'),
    path('face-tracking/manual-override/', face_tracking_views.manual_attendance_override, name='manual_attendance_override'),
    path('face-tracking/retrain-models/', face_tracking_views.retrain_face_models, name='retrain_face_models'),
    path('face-tracking/simple-train-models/', face_tracking_views.simple_train_face_models, name='simple_train_face_models'),
    path('face-tracking/config/', face_tracking_views.face_recognition_config, name='face_recognition_config'),
    path('face-tracking/stats/', face_tracking_views.get_face_recognition_stats, name='get_face_recognition_stats'),
    path('face-tracking/live-feed/', face_tracking_views.get_live_attendance_feed, name='get_live_attendance_feed'),
    path('face-tracking/test/', lambda request: JsonResponse({'success': True, 'message': 'Face tracking API is working'}), name='face_tracking_test'),
    
    # Real-time notification endpoints
    path('notifications/recent/', notification_views.get_recent_attendance_notifications, name='recent_attendance_notifications'),
    path('notifications/live-feed/', notification_views.get_live_attendance_feed, name='live_attendance_feed'),
    path('notifications/mark-read/', notification_views.mark_attendance_notifications_read, name='mark_attendance_notifications_read'),
    path('notifications/summary/', notification_views.get_attendance_notification_summary, name='attendance_notification_summary'),
    path('notifications/student/', notification_views.get_student_attendance_notifications, name='student_attendance_notifications'),
    path('notifications/test/', notification_views.test_attendance_notification, name='test_attendance_notification'),
]
