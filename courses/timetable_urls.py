from django.urls import path
from . import timetable_views

urlpatterns = [
    # Timetable management
    path('department/<int:department_id>/timetable/', timetable_views.get_department_timetable, name='department_timetable'),
    path('department/<int:department_id>/timetable/slots/', timetable_views.create_timetable_slot, name='create_timetable_slot'),
    path('department/<int:department_id>/timetable/slots/<int:slot_id>/', timetable_views.manage_timetable_slot, name='manage_timetable_slot'),
    path('department/<int:department_id>/timetable/check-conflicts/', timetable_views.check_timetable_conflicts_endpoint, name='check_timetable_conflicts'),

    # Level management
    path('department/<int:department_id>/levels/', timetable_views.get_department_levels, name='department_levels'),
    path('department/<int:department_id>/levels/create/', timetable_views.create_level, name='create_level'),

    # Lecturer management
    path('department/<int:department_id>/lecturers/', timetable_views.get_department_lecturers, name='department_lecturers'),
    path('department/<int:department_id>/lecturers/create/', timetable_views.create_lecturer, name='create_lecturer'),

    # Course management
    path('department/<int:department_id>/courses/', timetable_views.get_department_courses, name='department_courses'),
]