from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import uuid

User = get_user_model()

class LiveSession(models.Model):
    """Live session model for virtual classes and meetings"""
    
    SESSION_TYPES = [
        ('lecture', 'Lecture'),
        ('tutorial', 'Tutorial'),
        ('meeting', 'Meeting'),
        ('webinar', 'Webinar'),
        ('office_hours', 'Office Hours'),
    ]
    
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('ended', 'Ended'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    session_type = models.CharField(max_length=20, choices=SESSION_TYPES, default='lecture')
    
    # Relationships
    instructor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='instructed_sessions')
    course_offering = models.ForeignKey('academics.CourseOffering', on_delete=models.CASCADE, related_name='live_sessions', null=True, blank=True)
    
    # Add state field for compatibility
    state = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    
    def save(self, *args, **kwargs):
        # Keep state and status in sync
        self.state = self.status
        super().save(*args, **kwargs)
    
    # Timing
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    scheduled_duration = models.IntegerField(help_text="Duration in minutes", default=60)
    
    # Session Control
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    is_active = models.BooleanField(default=False)
    is_recorded = models.BooleanField(default=False)
    recording_url = models.URLField(blank=True)
    
    # Meeting Configuration
    meeting_id = models.CharField(max_length=100, unique=True)
    meeting_password = models.CharField(max_length=20, blank=True)
    max_participants = models.IntegerField(default=100)
    allow_recording = models.BooleanField(default=True)
    require_password = models.BooleanField(default=False)
    
    # Statistics
    total_participants = models.IntegerField(default=0)
    peak_participants = models.IntegerField(default=0)
    session_duration = models.IntegerField(default=0, help_text="Actual duration in minutes")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Live Session"
        verbose_name_plural = "Live Sessions"
    
    def __str__(self):
        return f"{self.title} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def is_scheduled(self):
        """Check if session is scheduled and not started"""
        return self.status == 'scheduled' and self.start_time > timezone.now()
    
    @property
    def is_live_now(self):
        """Check if session is currently live"""
        return self.status == 'live' and self.is_active
    
    @property
    def duration_minutes(self):
        """Calculate actual session duration"""
        if self.started_at and self.ended_at:
            return int((self.ended_at - self.started_at).total_seconds() / 60)
        return 0
    
    def start_session(self):
        """Start the live session"""
        self.status = 'live'
        self.is_active = True
        self.started_at = timezone.now()
        self.save()
    
    def end_session(self):
        """End the live session"""
        self.status = 'ended'
        self.is_active = False
        self.ended_at = timezone.now()
        if self.started_at:
            self.session_duration = self.duration_minutes
        self.save()

class LiveSessionParticipant(models.Model):
    """Participant tracking for live sessions"""
    
    CONNECTION_QUALITY = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='participants')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='live_session_participations')
    
    # Participation Timing
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    total_duration = models.IntegerField(default=0, help_text="Participation duration in minutes")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_speaking = models.BooleanField(default=False)
    is_screen_sharing = models.BooleanField(default=False)
    has_video = models.BooleanField(default=False)
    has_audio = models.BooleanField(default=True)
    
    # Connection Info
    connection_quality = models.CharField(max_length=20, choices=CONNECTION_QUALITY, default='good')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # Statistics
    messages_sent = models.IntegerField(default=0)
    screen_shares = models.IntegerField(default=0)
    hand_raises = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-joined_at']
        verbose_name = "Live Session Participant"
        verbose_name_plural = "Live Session Participants"
        unique_together = ['session', 'user']
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.session.title}"
    
    def leave_session(self):
        """Mark participant as left"""
        self.is_active = False
        self.left_at = timezone.now()
        if self.joined_at:
            self.total_duration = int((self.left_at - self.joined_at).total_seconds() / 60)
        self.save()

class LiveSessionRecording(models.Model):
    """Recordings for live sessions"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='recordings')
    
    # Recording Info
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file_url = models.URLField()
    file_size = models.BigIntegerField(default=0)  # in bytes
    duration = models.IntegerField(default=0)  # in seconds
    
    # Recording Status
    is_processing = models.BooleanField(default=True)
    is_available = models.BooleanField(default=False)
    thumbnail_url = models.URLField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Live Session Recording"
        verbose_name_plural = "Live Session Recordings"
    
    def __str__(self):
        return f"Recording of {self.session.title}"

class LiveSessionMessage(models.Model):
    """Chat messages during live sessions"""
    
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('system', 'System'),
        ('hand_raise', 'Hand Raise'),
        ('poll', 'Poll'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(LiveSession, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='live_session_messages')
    
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    
    # Message metadata
    is_private = models.BooleanField(default=False)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
        verbose_name = "Live Session Message"
        verbose_name_plural = "Live Session Messages"
    
    def __str__(self):
        return f"{self.user.get_full_name()}: {self.content[:50]}..."
