from django.urls import path
from . import views

# URL patterns for institutions app - UPDATED
urlpatterns = [
    # Basic endpoints
    path('programs/', views.get_programs, name='get_programs'),
    path('faculties/', views.get_faculties, name='get_faculties'),
    path('departments/', views.get_departments, name='get_departments'),
    path('courses/', views.get_courses, name='get_courses'),
    
    # Admin endpoints - NEWLY ADDED
    path('admin/departments/', views.admin_departments, name='admin_departments'),
    path('admin/departments/<int:dept_id>/', views.admin_department_detail, name='admin_department_detail'),
    path('admin/courses/', views.admin_courses_enhanced, name='admin_courses_enhanced'),
    path('admin/courses/create/', views.admin_course_create, name='admin_course_create'),
]