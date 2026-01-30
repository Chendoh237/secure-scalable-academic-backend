from django.urls import path
from .views import (
    NotificationListView,
    mark_notification_read,
    mark_all_notifications_read,
    mark_notification_unread,
    delete_notification,
    delete_all_notifications
)
from .email_views import send_bulk_notifications, email_settings

app_name = 'notifications'

urlpatterns = [
    # Main notification endpoints
    path('', NotificationListView.as_view(), name='notification_list'),
    path('<int:notification_id>/read/', mark_notification_read, name='mark_notification_read'),
    path('<int:notification_id>/unread/', mark_notification_unread, name='mark_notification_unread'),
    path('<int:notification_id>/delete/', delete_notification, name='delete_notification'),
    path('mark-all-read/', mark_all_notifications_read, name='mark_all_notifications_read'),
    path('delete-all/', delete_all_notifications, name='delete_all_notifications'),
    
    # Admin email management endpoints
    path('bulk/', send_bulk_notifications, name='send_bulk_notifications'),
    path('email/settings/', email_settings, name='email_settings'),
]
