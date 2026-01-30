from django.urls import path
from . import views

app_name = 'academics'

urlpatterns = [
    # Academic Year endpoints
    path('years/', views.get_academic_years, name='get_academic_years'),
    path('years/current/', views.get_current_academic_year, name='get_current_academic_year'),
    path('years/create/', views.create_academic_year, name='create_academic_year'),
    
    # Semester endpoints
    path('semesters/', views.get_semesters, name='get_semesters'),
    path('semesters/current/', views.get_current_semester, name='get_current_semester'),
    
    # Student Level endpoints
    path('levels/', views.get_student_levels, name='get_student_levels'),
    path('levels/<int:level_id>/', views.get_student_level_detail, name='get_student_level_detail'),
    
    # Grade Scale endpoints
    path('grade-scales/', views.get_grade_scales, name='get_grade_scales'),
    path('grade-scales/<int:scale_id>/', views.get_grade_scale_detail, name='get_grade_scale_detail'),
    
    # Course Category endpoints
    path('course-categories/', views.get_course_categories, name='get_course_categories'),
    path('course-categories/<int:category_id>/', views.get_course_category_detail, name='get_course_category_detail'),
    
    # Admin endpoints
    path('admin/overview/', views.admin_academics_overview, name='admin_academics_overview'),
    path('admin/grade-scales/create/', views.admin_create_grade_scale, name='admin_create_grade_scale'),
    path('admin/course-categories/create/', views.admin_create_course_category, name='admin_create_course_category'),
]
