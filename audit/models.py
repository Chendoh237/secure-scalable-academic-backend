from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()

class AuditLog(models.Model):
    """Model for tracking all administrative actions"""
    
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
        ('SETTINGS_CHANGE', 'Settings Change'),
        ('PERMISSION_CHANGE', 'Permission Change'),
        ('PASSWORD_RESET', 'Password Reset'),
        ('OTHER', 'Other'),
    ]
    
    ENTITY_TYPES = [
        ('student', 'Student'),
        ('course', 'Course'),
        ('department', 'Department'),
        ('timetable', 'Timetable'),
        ('attendance', 'Attendance'),
        ('user', 'User'),
        ('settings', 'Settings'),
        ('session', 'Session'),
        ('registration', 'Registration'),
        ('other', 'Other'),
    ]
    
    # Actor information
    admin = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs_created')
    admin_username = models.CharField(max_length=255, blank=True)  # Backup if user is deleted
    
    # Action information
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=20, choices=ENTITY_TYPES)
    entity_id = models.CharField(max_length=255)  # ID of affected object
    entity_name = models.CharField(max_length=500, blank=True)  # Name of affected object
    
    # Details
    description = models.TextField(blank=True)
    old_values = models.JSONField(default=dict, blank=True)  # Previous values (for updates)
    new_values = models.JSONField(default=dict, blank=True)  # New values
    
    # Request information
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    
    # Status
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['admin', '-created_at']),
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['entity_type', '-created_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.get_entity_type_display()} ({self.entity_id}) by {self.admin_username or 'Unknown'}"


class EmailLog(models.Model):
    """Model for tracking sent emails"""
    
    EMAIL_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    ]
    
    recipient = models.EmailField()
    recipient_name = models.CharField(max_length=255, blank=True)
    sender = models.EmailField(default='noreply@university.local')
    
    subject = models.CharField(max_length=500)
    message_type = models.CharField(max_length=50)  # e.g., 'student_approval', 'low_attendance'
    body = models.TextField()
    
    status = models.CharField(max_length=20, choices=EMAIL_STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)
    
    initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='emails_initiated')
    
    related_entity_type = models.CharField(max_length=50, blank=True)
    related_entity_id = models.CharField(max_length=255, blank=True)
    
    sent_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['recipient', '-created_at']),
        ]
        verbose_name = "Email Log"
        verbose_name_plural = "Email Logs"
    
    def __str__(self):
        return f"{self.subject} - {self.recipient} ({self.get_status_display()})"


class EmailConfiguration(models.Model):
    """Store email configuration settings"""
    
    smtp_host = models.CharField(max_length=255, default='smtp.gmail.com')
    smtp_port = models.IntegerField(default=587)
    smtp_username = models.CharField(max_length=255)
    smtp_password = models.CharField(max_length=255)
    from_email = models.EmailField()
    from_name = models.CharField(max_length=255, default='System')
    use_ssl = models.BooleanField(default=False)
    use_tls = models.BooleanField(default=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Email Configuration"
        verbose_name_plural = "Email Configurations"
    
    def __str__(self):
        return f"Email Config - {self.from_email}"


class EmailTemplate(models.Model):
    """Email templates for notifications"""
    
    name = models.CharField(max_length=255, unique=True)
    subject = models.CharField(max_length=500)
    body_html = models.TextField()
    body_text = models.TextField(blank=True)
    variables = models.JSONField(default=list, blank=True)  # List of variables used in template
    
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Email Template"
        verbose_name_plural = "Email Templates"
    
    def __str__(self):
        return self.name


class EmailNotificationRule(models.Model):
    """Rules for triggering email notifications"""
    
    TRIGGER_CHOICES = [
        ('student_approved', 'Student Approved'),
        ('student_rejected', 'Student Rejected'),
        ('low_attendance', 'Low Attendance Alert'),
        ('course_registered', 'Course Registered'),
        ('exam_eligible', 'Exam Eligible'),
        ('exam_ineligible', 'Exam Ineligible'),
        ('course_updated', 'Course Updated'),
        ('session_scheduled', 'Session Scheduled'),
        ('custom', 'Custom'),
    ]
    
    name = models.CharField(max_length=255)
    trigger_event = models.CharField(max_length=50, choices=TRIGGER_CHOICES)
    email_template = models.ForeignKey(EmailTemplate, on_delete=models.SET_NULL, null=True)
    
    recipient_emails = models.JSONField(default=list)  # List of recipient emails
    recipient_type = models.CharField(
        max_length=50,
        choices=[
            ('custom', 'Custom Emails'),
            ('all_admins', 'All Admins'),
            ('student', 'Student'),
        ],
        default='custom'
    )
    
    is_enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = "Email Notification Rule"
        verbose_name_plural = "Email Notification Rules"
    
    def __str__(self):
        return f"{self.name} - {self.get_trigger_event_display()}"
