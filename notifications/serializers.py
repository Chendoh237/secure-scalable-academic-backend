from rest_framework import serializers
from .models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model"""
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'message', 'description', 'notification_type',
            'is_read', 'created_at', 'read_at', 'icon', 'link'
        ]
        read_only_fields = ['created_at', 'read_at']

class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications"""
    
    class Meta:
        model = Notification
        fields = ['title', 'message', 'description', 'notification_type', 'icon', 'link']