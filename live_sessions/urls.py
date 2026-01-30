from django.urls import path
from . import views

app_name = 'live_sessions'

urlpatterns = [
    # Live session management
    path('', views.live_sessions_list, name='live_sessions_list'),
    path('create/', views.create_live_session, name='create_live_session'),
    path('<uuid:session_id>/start/', views.start_live_session, name='start_live_session'),
    path('<uuid:session_id>/end/', views.end_live_session, name='end_live_session'),
    path('<uuid:session_id>/participants/', views.live_session_participants, name='live_session_participants'),
    path('<uuid:session_id>/analytics/', views.live_session_analytics, name='live_session_analytics'),
]