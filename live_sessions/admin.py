from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import LiveSession, LiveSessionParticipant, LiveSessionRecording, LiveSessionMessage

@admin.register(LiveSession)
class LiveSessionAdmin(admin.ModelAdmin):
    list_display = ('title', 'instructor', 'course_offering', 'session_type', 'status', 'start_time', 'total_participants')
    list_filter = ('status', 'session_type', 'is_recorded', 'created_at')
    search_fields = ('title', 'instructor__email', 'course_offering__course__title')
    readonly_fields = ('id', 'meeting_id', 'created_at', 'updated_at', 'started_at', 'ended_at')
    
    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'description', 'session_type', 'instructor', 'course_offering')
        }),
        ('Timing', {
            'fields': ('start_time', 'end_time', 'scheduled_duration')
        }),
        ('Session Control', {
            'fields': ('status', 'is_active', 'is_recorded')
        }),
        ('Meeting Configuration', {
            'fields': ('meeting_id', 'meeting_password', 'max_participants', 'allow_recording', 'require_password')
        }),
        ('Statistics', {
            'fields': ('total_participants', 'peak_participants', 'session_duration')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at', 'started_at', 'ended_at')
        })
    )

@admin.register(LiveSessionParticipant)
class LiveSessionParticipantAdmin(admin.ModelAdmin):
    list_display = ('user', 'session', 'joined_at', 'left_at', 'is_active', 'connection_quality')
    list_filter = ('is_active', 'connection_quality', 'joined_at')
    search_fields = ('user__email', 'session__title')
    readonly_fields = ('id', 'joined_at', 'left_at', 'total_duration')

@admin.register(LiveSessionRecording)
class LiveSessionRecordingAdmin(admin.ModelAdmin):
    list_display = ('session', 'title', 'duration', 'is_available', 'created_at')
    list_filter = ('is_available', 'is_processing', 'created_at')
    search_fields = ('session__title', 'title')
    readonly_fields = ('id', 'created_at', 'processed_at')

@admin.register(LiveSessionMessage)
class LiveSessionMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'session', 'message_type', 'content_preview', 'created_at')
    list_filter = ('message_type', 'is_private', 'created_at')
    search_fields = ('user__email', 'session__title', 'content')
    readonly_fields = ('id', 'created_at')
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content Preview'