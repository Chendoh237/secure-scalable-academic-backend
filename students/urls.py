from django.urls import path
from .views import (
    AttendanceHistoryView,
    AvailableCoursesView,
    RegisterCourseView,
    StudentLoginView,
    StudentProfileView,
    DashboardOverviewView,
    StudentCoursesView,
    StudentTimetableView,
    NewStudentTimetableView,
    StudentTimetableByLevelView,
    StudentTimetableByDepartmentView,
    AttendanceSummaryView,
    attendance_summary,
    attendance_history,
    exam_eligibility,
    UserProfileView,
    check_student_status,
    student_settings,
    detailed_attendance_history,
    get_student_timetable_simple,
    sync_student_courses
)
from .simple_views import SimpleRegistrationView
from .api_views import StudentCoursesView as APIStudentCoursesView, AvailableCoursesView as APIAvailableCoursesView, RegisterCourseView as APIRegisterCourseView
from .admin_views import (
    dashboard_stats,
    active_sessions,
    low_attendance_students,
    admin_students,
    admin_student_detail,
    approve_student,
    admin_courses,
    admin_course_detail,
    admin_departments,
    admin_department_detail,
    attendance_records,
    export_attendance_records,
    test_query_params,
    analytics_data,
    get_admin_levels,  # Add this
    sync_student_timetable,
    update_student_attendance_from_timetable,
    notify_student_of_changes,
    train_face_model_api,
    get_face_training_status,
    train_single_student_face,
    admin_live_sessions
)
from .student_timetable_views import (
    get_available_levels,
    manage_level_selection,
    get_student_timetable,
    manage_course_selections
)
from .audit_views import (
    get_audit_logs,
    get_student_audit_summary,
    get_department_audit_summary,
    get_audit_statistics,
    export_audit_logs,
    cleanup_old_audit_logs
)
from .monitoring_views import (
    system_health_check,
    get_performance_metrics,
    manage_alerts,
    get_system_metrics,
    monitoring_dashboard,
    reset_monitoring_data,
    monitoring_config
)
from .views import admin_settings
from .course_registration_views import (
    AvailableCoursesView as CourseRegAvailableCoursesView,
    CourseRegistrationView,
    MyCoursesView,
    PendingRegistrationsView,
    CancelRegistrationView
)
from .admin_course_registration_views import (
    PendingRegistrationsAdminView,
    ApproveRegistrationView,
    RejectRegistrationView,
    RegistrationHistoryView
)
from .simple_email_views import simple_email_settings, send_bulk_notifications
from .email_views import (
    get_smtp_configuration,
    save_smtp_configuration,
    test_smtp_connection,
    get_smtp_providers,
    delete_smtp_configuration,
    get_email_templates,
    render_email_template,
    get_recipient_options,
    validate_recipients,
    send_bulk_email,
    get_email_history,
    get_email_delivery_details,
    get_email_statistics,
    create_system_announcement,
    create_course_notification,
    # Student Data Integration endpoints
    get_integration_health_report,
    validate_student_emails,
    get_students_with_missing_data,
    refresh_student_data_cache,
    assess_delivery_readiness
)

urlpatterns = [
    # Auth endpoints
    path('register/', SimpleRegistrationView.as_view(), name="simple_register"),
    path('login/', StudentLoginView.as_view(), name="student_login"),
    
    # Profile endpoint (main one used by frontend)
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('students/profile/', UserProfileView.as_view(), name='user-profile-alt'),
    
    # Admin endpoints
    path('admin/dashboard/stats/', dashboard_stats, name='admin_dashboard_stats'),
    path('admin/sessions/active/', active_sessions, name='admin_active_sessions'),
    path('admin/students/', admin_students, name='admin_students'),
    path('admin/students/<int:student_id>/', admin_student_detail, name='admin_student_detail'),
    path('admin/students/<int:student_id>/approve/', approve_student, name='admin_approve_student'),
    path('admin/students/low-attendance/', low_attendance_students, name='admin_low_attendance'),
    path('admin/courses/', admin_courses, name='admin_courses'),
    path('admin/courses/<int:course_id>/', admin_course_detail, name='admin_course_detail'),
    path('admin/departments/', admin_departments, name='admin_departments'),
    path('admin/departments/<int:dept_id>/', admin_department_detail, name='admin_department_detail'),
    path('admin/attendance/', attendance_records, name='admin_attendance_records'),
    path('admin/attendance/test/', test_query_params, name='admin_test_query_params'),
    path('admin/attendance/export/', export_attendance_records, name='admin_export_attendance_records'),
    path('admin/analytics/', analytics_data, name='admin_analytics_data'),
    path('admin/levels/', get_admin_levels, name='admin_levels'),  # Add this
    path('admin/settings/', admin_settings, name='admin_settings'),
    path('admin/settings/email/', simple_email_settings, name='admin_email_settings'),
    path('admin/notifications/bulk/', send_bulk_notifications, name='admin_bulk_notifications'),
    path('admin/live-sessions/', admin_live_sessions, name='admin_live_sessions'),
    
    # Student Settings (read-only access to relevant settings)
    path('student/settings/', student_settings, name='student_settings'),
    
    # Course Registration & Approval API endpoints (Admin)
    path('admin/course-registrations/pending/', PendingRegistrationsAdminView.as_view(), name='admin_pending_registrations'),
    path('admin/course-registrations/<int:registration_id>/approve/', ApproveRegistrationView.as_view(), name='admin_approve_registration'),
    path('admin/course-registrations/<int:registration_id>/reject/', RejectRegistrationView.as_view(), name='admin_reject_registration'),
    path('admin/course-registrations/history/', RegistrationHistoryView.as_view(), name='admin_registration_history'),
    
    # Face Training endpoints
    path('admin/face-training/status/', get_face_training_status, name='get_face_training_status'),
    path('admin/face-training/train-all/', train_face_model_api, name='train_face_model_api'),
    path('admin/face-training/train/<int:student_id>/', train_single_student_face, name='train_single_student_face'),
    
    # Email Management API endpoints (Admin only)
    path('admin/email/smtp/config/', get_smtp_configuration, name='admin_get_smtp_config'),
    path('admin/email/smtp/config/save/', save_smtp_configuration, name='admin_save_smtp_config'),
    path('admin/email/smtp/config/test/', test_smtp_connection, name='admin_test_smtp_connection'),
    path('admin/email/smtp/providers/', get_smtp_providers, name='admin_get_smtp_providers'),
    path('admin/email/smtp/config/delete/', delete_smtp_configuration, name='admin_delete_smtp_config'),
    
    # Email Composition and Sending API endpoints (Admin only)
    path('admin/email/templates/', get_email_templates, name='admin_get_email_templates'),
    path('admin/email/templates/render/', render_email_template, name='admin_render_email_template'),
    path('admin/email/recipients/options/', get_recipient_options, name='admin_get_recipient_options'),
    path('admin/email/recipients/validate/', validate_recipients, name='admin_validate_recipients'),
    path('admin/email/send/', send_bulk_email, name='admin_send_bulk_email'),
    
    # Email History API endpoints (Admin only)
    path('admin/email/history/', get_email_history, name='admin_get_email_history'),
    path('admin/email/history/<int:history_id>/details/', get_email_delivery_details, name='admin_get_email_delivery_details'),
    path('admin/email/statistics/', get_email_statistics, name='admin_get_email_statistics'),
    
    # Email-Notification Integration API endpoints (Admin only)
    path('admin/email/notifications/system/', create_system_announcement, name='admin_create_system_announcement'),
    path('admin/email/notifications/course/', create_course_notification, name='admin_create_course_notification'),
    
    # API v1 endpoints
    path('api/v1/courses/', APIStudentCoursesView.as_view(), name='api_student_courses'),
    path('api/v1/courses/available/', APIAvailableCoursesView.as_view(), name='api_available_courses'),
    path('api/v1/courses/register/', APIRegisterCourseView.as_view(), name='api_register_course'),
    
    # Dashboard and student data
    path('dashboard/overview/', DashboardOverviewView.as_view(), name='dashboard_overview'),
    path('students/dashboard/overview/', DashboardOverviewView.as_view(), name='students_dashboard_overview'),
    
    # Student Timetable Module API endpoints (MUST BE BEFORE GENERIC PATTERNS)
    path('students/levels/', get_available_levels, name='student_available_levels'),
    path('students/level-selection/', manage_level_selection, name='student_level_selection'),
    path('students/course-selections/', manage_course_selections, name='student_course_selections'),
    path('students/sync-courses/', sync_student_courses, name='student_sync_courses'),
    
    # Course Registration & Approval API endpoints (Student)
    path('students/courses/available/', CourseRegAvailableCoursesView.as_view(), name='student_available_courses_registration'),
    path('students/courses/register/', CourseRegistrationView.as_view(), name='student_course_registration'),
    path('students/courses/', MyCoursesView.as_view(), name='student_my_courses'),
    path('students/courses/pending/', PendingRegistrationsView.as_view(), name='student_pending_registrations'),
    path('students/courses/registration/<int:registration_id>/', CancelRegistrationView.as_view(), name='student_cancel_registration'),
    
    # Course management
    path('courses/', StudentCoursesView.as_view(), name='student_courses'),
    path('students/courses/', StudentCoursesView.as_view(), name='students_courses'),
    path('timetable/', StudentTimetableView.as_view(), name='student_timetable'),
    path('students/timetable/', get_student_timetable_simple, name='students_timetable_simple'),  # Fixed endpoint
    path('timetable/new/', NewStudentTimetableView.as_view(), name='new_student_timetable'),
    path('students/timetable/new/', NewStudentTimetableView.as_view(), name='new_students_timetable'),
    path('timetable/level/<str:level_id>/', StudentTimetableByLevelView.as_view(), name='student_timetable_by_level'),
    path('students/timetable/level/<str:level_id>/', StudentTimetableByLevelView.as_view(), name='students_timetable_by_level'),
    path('timetable/department/<str:department_id>/', StudentTimetableByDepartmentView.as_view(), name='student_timetable_by_department'),
    path('students/timetable/department/<str:department_id>/', StudentTimetableByDepartmentView.as_view(), name='students_timetable_by_department'),
    path('attendance/summary/', AttendanceSummaryView.as_view(), name='attendance_summary'),
    path('students/attendance/summary/', AttendanceSummaryView.as_view(), name='students_attendance_summary'),
    path('attendance/history/', AttendanceHistoryView.as_view(), name='attendance_history'),
    path('students/attendance/history/', AttendanceHistoryView.as_view(), name='students_attendance_history'),
    path('students/attendance/detailed/', detailed_attendance_history, name='students_detailed_attendance_history'),
    path('exam-eligibility/', exam_eligibility, name='exam_eligibility'),
    path('students/exam-eligibility/', exam_eligibility, name='students_exam_eligibility'),
    
    # Test endpoint
    path('check-status/', check_student_status, name='check_student_status'),

    # Student Timetable Synchronization
    path('admin/students/<str:student_id>/sync-timetable/', sync_student_timetable, name='sync_student_timetable'),
    path('admin/students/<str:student_id>/update-attendance-from-timetable/', update_student_attendance_from_timetable, name='update_student_attendance_from_timetable'),
    path('admin/students/<str:student_id>/notify/', notify_student_of_changes, name='notify_student_of_changes'),
    
    # Course Selection Audit Trail API endpoints (Admin only)
    path('admin/audit/logs/', get_audit_logs, name='admin_audit_logs'),
    path('admin/audit/students/<int:student_id>/', get_student_audit_summary, name='admin_student_audit_summary'),
    path('admin/audit/departments/<int:department_id>/', get_department_audit_summary, name='admin_department_audit_summary'),
    path('admin/audit/statistics/', get_audit_statistics, name='admin_audit_statistics'),
    path('admin/audit/export/', export_audit_logs, name='admin_export_audit_logs'),
    path('admin/audit/cleanup/', cleanup_old_audit_logs, name='admin_cleanup_audit_logs'),
    
    # System Monitoring API endpoints (Admin only)
    path('admin/monitoring/health/', system_health_check, name='admin_system_health'),
    path('admin/monitoring/performance/', get_performance_metrics, name='admin_performance_metrics'),
    path('admin/monitoring/alerts/', manage_alerts, name='admin_manage_alerts'),
    path('admin/monitoring/metrics/', get_system_metrics, name='admin_system_metrics'),
    path('admin/monitoring/dashboard/', monitoring_dashboard, name='admin_monitoring_dashboard'),
    path('admin/monitoring/reset/', reset_monitoring_data, name='admin_reset_monitoring'),
    path('admin/monitoring/config/', monitoring_config, name='admin_monitoring_config'),
    
    # Student Data Integration API endpoints (Admin only)
    path('admin/email/integration/health/', get_integration_health_report, name='admin_get_integration_health'),
    path('admin/email/integration/validate-emails/', validate_student_emails, name='admin_validate_student_emails'),
    path('admin/email/integration/missing-data/', get_students_with_missing_data, name='admin_get_missing_data'),
    path('admin/email/integration/refresh-cache/', refresh_student_data_cache, name='admin_refresh_cache'),
    path('admin/email/integration/delivery-readiness/', assess_delivery_readiness, name='admin_assess_delivery_readiness'),
]