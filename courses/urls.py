from django.urls import path, include
from .views import CourseListView, CourseDetailView, CourseTimetableView
from . import timetable_urls

urlpatterns = [
    path('all/', CourseListView.as_view(), name='course_list'),
    path('<int:course_id>/', CourseDetailView.as_view(), name='course_detail'),
    path('timetable/', CourseTimetableView.as_view(), name='course_timetable'),
    path('timetable-management/', include(timetable_urls)),
]