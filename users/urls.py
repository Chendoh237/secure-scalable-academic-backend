# backend/users/urls.py
from django.urls import path
from . import views
from django.views.decorators.csrf import csrf_exempt

urlpatterns = [
    # Admin authentication
    path('admin/login/', views.admin_login_view, name='admin_login'),
    path('admin/logout/', views.logout_view, name='admin_logout'),
    
    # Admin dashboard and management
    path('admin/dashboard/stats/', views.admin_dashboard_stats, name='admin_dashboard_stats'),
    path('admin/students/', views.students_list, name='students_list'),
    path('admin/students/create/', views.create_student, name='create_student'),
    path('admin/students/<int:student_id>/', views.manage_student, name='manage_student'),
    path('admin/students/<int:student_id>/approve/', views.approve_student, name='approve_student'),
    
    # Monitoring and logs
    path('admin/logs/login/', views.login_logs, name='login_logs'),
    path('admin/logs/activities/', views.admin_activities, name='admin_activities'),
]