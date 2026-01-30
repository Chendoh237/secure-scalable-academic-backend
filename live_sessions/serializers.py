from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import LiveSession, LiveSessionParticipant, LiveSessionRecording, LiveSessionMessage

User = get_user_model()

class LiveSessionSerializer(serializers.ModelSerializer):
    instructor_name = serializers.CharField(source='instructor.get_full_name', read_only=True)
    instructor_email = serializers.CharField(source='instructor.email', read_only=True)
    course_name = serializers.CharField(source='course.name', read_only=True)
    is_scheduled = serializers.BooleanField(read_only=True)
    is_live_now = serializers.BooleanField(read_only=True)
    duration_minutes = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = LiveSession
        fields = '__all__'
        read_only_fields = ('id', 'meeting_id', 'created_at', 'updated_at', 'started_at', 'ended_at')

class LiveSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = LiveSession
        fields = ('title', 'description', 'session_type', 'course', 'start_time', 
                 'scheduled_duration', 'max_participants', 'allow_recording', 'require_password')

class LiveSessionParticipantSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    
    class Meta:
        model = LiveSessionParticipant
        fields = '__all__'
        read_only_fields = ('id', 'joined_at', 'left_at', 'total_duration')

class LiveSessionRecordingSerializer(serializers.ModelSerializer):
    session_title = serializers.CharField(source='session.title', read_only=True)
    
    class Meta:
        model = LiveSessionRecording
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'processed_at')

class LiveSessionMessageSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = LiveSessionMessage
        fields = '__all__'
        read_only_fields = ('id', 'created_at')