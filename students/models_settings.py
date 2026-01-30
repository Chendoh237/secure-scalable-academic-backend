#!/usr/bin/env python3
"""
System Settings Models
Stores admin configuration that affects both admin and student portals
"""

from django.db import models
from django.core.cache import cache
import json

class SystemSettings(models.Model):
    """
    System-wide settings that affect both admin and student portals
    """
    
    # General Settings
    institution_name = models.CharField(max_length=200, default='University of Technology')
    institution_code = models.CharField(max_length=20, default='UOT')
    academic_year = models.CharField(max_length=20, default='2023-2024')
    semester = models.CharField(max_length=50, default='Fall 2024')
    timezone = models.CharField(max_length=50, default='UTC+0')
    language = models.CharField(max_length=10, default='en')
    
    # Attendance Settings (affects student portal)
    attendance_threshold = models.IntegerField(default=75, help_text='Minimum attendance % for exam eligibility')
    late_threshold = models.IntegerField(default=15, help_text='Minutes after class start considered late')
    auto_mark_absent = models.BooleanField(default=True)
    require_face_recognition = models.BooleanField(default=True)
    allow_manual_override = models.BooleanField(default=True)
    session_timeout = models.IntegerField(default=30, help_text='Session timeout in minutes')
    
    # Notification Settings (affects student notifications)
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    push_notifications = models.BooleanField(default=True)
    low_attendance_alerts = models.BooleanField(default=True)
    session_reminders = models.BooleanField(default=True)
    weekly_reports = models.BooleanField(default=True)
    
    # Security Settings
    password_min_length = models.IntegerField(default=8)
    require_two_factor = models.BooleanField(default=False)
    security_session_timeout = models.IntegerField(default=60, help_text='Security session timeout in minutes')
    max_login_attempts = models.IntegerField(default=5)
    require_password_change = models.BooleanField(default=False)
    allow_student_registration = models.BooleanField(default=True)
    
    # System Settings
    maintenance_mode = models.BooleanField(default=False)
    debug_mode = models.BooleanField(default=False)
    data_retention_days = models.IntegerField(default=365)
    backup_frequency = models.CharField(max_length=20, default='daily')
    log_level = models.CharField(max_length=20, default='info')
    max_file_size = models.IntegerField(default=10, help_text='Max file size in MB')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'
    
    def __str__(self):
        return f"System Settings - {self.institution_name}"
    
    @classmethod
    def get_settings(cls):
        """Get current system settings with caching"""
        settings = cache.get('system_settings')
        if not settings:
            try:
                settings_obj = cls.objects.first()
                if not settings_obj:
                    # Create default settings
                    settings_obj = cls.objects.create()
                
                settings = {
                    'general': {
                        'institutionName': settings_obj.institution_name,
                        'institutionCode': settings_obj.institution_code,
                        'academicYear': settings_obj.academic_year,
                        'semester': settings_obj.semester,
                        'timezone': settings_obj.timezone,
                        'language': settings_obj.language,
                    },
                    'attendance': {
                        'attendanceThreshold': settings_obj.attendance_threshold,
                        'lateThreshold': settings_obj.late_threshold,
                        'autoMarkAbsent': settings_obj.auto_mark_absent,
                        'requireFaceRecognition': settings_obj.require_face_recognition,
                        'allowManualOverride': settings_obj.allow_manual_override,
                        'sessionTimeout': settings_obj.session_timeout,
                    },
                    'notifications': {
                        'emailNotifications': settings_obj.email_notifications,
                        'smsNotifications': settings_obj.sms_notifications,
                        'pushNotifications': settings_obj.push_notifications,
                        'lowAttendanceAlerts': settings_obj.low_attendance_alerts,
                        'sessionReminders': settings_obj.session_reminders,
                        'weeklyReports': settings_obj.weekly_reports,
                    },
                    'security': {
                        'passwordMinLength': settings_obj.password_min_length,
                        'requireTwoFactor': settings_obj.require_two_factor,
                        'sessionTimeout': settings_obj.security_session_timeout,
                        'maxLoginAttempts': settings_obj.max_login_attempts,
                        'requirePasswordChange': settings_obj.require_password_change,
                        'allowStudentRegistration': settings_obj.allow_student_registration,
                    },
                    'system': {
                        'maintenanceMode': settings_obj.maintenance_mode,
                        'debugMode': settings_obj.debug_mode,
                        'dataRetentionDays': settings_obj.data_retention_days,
                        'backupFrequency': settings_obj.backup_frequency,
                        'logLevel': settings_obj.log_level,
                        'maxFileSize': settings_obj.max_file_size,
                    }
                }
                
                # Cache for 5 minutes
                cache.set('system_settings', settings, 300)
                
            except Exception as e:
                # Return default settings if database error
                settings = cls._get_default_settings()
        
        return settings
    
    @classmethod
    def update_settings(cls, settings_data, updated_by=None):
        """Update system settings and clear cache"""
        try:
            settings_obj = cls.objects.first()
            if not settings_obj:
                settings_obj = cls.objects.create()
            
            # Update general settings
            if 'general' in settings_data:
                general = settings_data['general']
                settings_obj.institution_name = general.get('institutionName', settings_obj.institution_name)
                settings_obj.institution_code = general.get('institutionCode', settings_obj.institution_code)
                settings_obj.academic_year = general.get('academicYear', settings_obj.academic_year)
                settings_obj.semester = general.get('semester', settings_obj.semester)
                settings_obj.timezone = general.get('timezone', settings_obj.timezone)
                settings_obj.language = general.get('language', settings_obj.language)
            
            # Update attendance settings
            if 'attendance' in settings_data:
                attendance = settings_data['attendance']
                settings_obj.attendance_threshold = attendance.get('attendanceThreshold', settings_obj.attendance_threshold)
                settings_obj.late_threshold = attendance.get('lateThreshold', settings_obj.late_threshold)
                settings_obj.auto_mark_absent = attendance.get('autoMarkAbsent', settings_obj.auto_mark_absent)
                settings_obj.require_face_recognition = attendance.get('requireFaceRecognition', settings_obj.require_face_recognition)
                settings_obj.allow_manual_override = attendance.get('allowManualOverride', settings_obj.allow_manual_override)
                settings_obj.session_timeout = attendance.get('sessionTimeout', settings_obj.session_timeout)
            
            # Update notification settings
            if 'notifications' in settings_data:
                notifications = settings_data['notifications']
                settings_obj.email_notifications = notifications.get('emailNotifications', settings_obj.email_notifications)
                settings_obj.sms_notifications = notifications.get('smsNotifications', settings_obj.sms_notifications)
                settings_obj.push_notifications = notifications.get('pushNotifications', settings_obj.push_notifications)
                settings_obj.low_attendance_alerts = notifications.get('lowAttendanceAlerts', settings_obj.low_attendance_alerts)
                settings_obj.session_reminders = notifications.get('sessionReminders', settings_obj.session_reminders)
                settings_obj.weekly_reports = notifications.get('weeklyReports', settings_obj.weekly_reports)
            
            # Update security settings
            if 'security' in settings_data:
                security = settings_data['security']
                settings_obj.password_min_length = security.get('passwordMinLength', settings_obj.password_min_length)
                settings_obj.require_two_factor = security.get('requireTwoFactor', settings_obj.require_two_factor)
                settings_obj.security_session_timeout = security.get('sessionTimeout', settings_obj.security_session_timeout)
                settings_obj.max_login_attempts = security.get('maxLoginAttempts', settings_obj.max_login_attempts)
                settings_obj.require_password_change = security.get('requirePasswordChange', settings_obj.require_password_change)
                settings_obj.allow_student_registration = security.get('allowStudentRegistration', settings_obj.allow_student_registration)
            
            # Update system settings
            if 'system' in settings_data:
                system = settings_data['system']
                settings_obj.maintenance_mode = system.get('maintenanceMode', settings_obj.maintenance_mode)
                settings_obj.debug_mode = system.get('debugMode', settings_obj.debug_mode)
                settings_obj.data_retention_days = system.get('dataRetentionDays', settings_obj.data_retention_days)
                settings_obj.backup_frequency = system.get('backupFrequency', settings_obj.backup_frequency)
                settings_obj.log_level = system.get('logLevel', settings_obj.log_level)
                settings_obj.max_file_size = system.get('maxFileSize', settings_obj.max_file_size)
            
            # Set updated by
            if updated_by:
                settings_obj.updated_by = updated_by
            
            settings_obj.save()
            
            # Clear cache to force refresh
            cache.delete('system_settings')
            
            return True
            
        except Exception as e:
            print(f"Error updating settings: {e}")
            return False
    
    @classmethod
    def _get_default_settings(cls):
        """Get default settings structure"""
        return {
            'general': {
                'institutionName': 'University of Technology',
                'institutionCode': 'UOT',
                'academicYear': '2023-2024',
                'semester': 'Fall 2024',
                'timezone': 'UTC+0',
                'language': 'en'
            },
            'attendance': {
                'attendanceThreshold': 75,
                'lateThreshold': 15,
                'autoMarkAbsent': True,
                'requireFaceRecognition': True,
                'allowManualOverride': True,
                'sessionTimeout': 30
            },
            'notifications': {
                'emailNotifications': True,
                'smsNotifications': False,
                'pushNotifications': True,
                'lowAttendanceAlerts': True,
                'sessionReminders': True,
                'weeklyReports': True
            },
            'security': {
                'passwordMinLength': 8,
                'requireTwoFactor': False,
                'sessionTimeout': 60,
                'maxLoginAttempts': 5,
                'requirePasswordChange': False,
                'allowStudentRegistration': True
            },
            'system': {
                'maintenanceMode': False,
                'debugMode': False,
                'dataRetentionDays': 365,
                'backupFrequency': 'daily',
                'logLevel': 'info',
                'maxFileSize': 10
            }
        }
    
    @classmethod
    def get_attendance_threshold(cls):
        """Get current attendance threshold for student portal"""
        settings = cls.get_settings()
        return settings['attendance']['attendanceThreshold']
    
    @classmethod
    def get_institution_info(cls):
        """Get institution info for student portal branding"""
        settings = cls.get_settings()
        return {
            'name': settings['general']['institutionName'],
            'code': settings['general']['institutionCode'],
            'academic_year': settings['general']['academicYear'],
            'semester': settings['general']['semester']
        }
    
    @classmethod
    def get_notification_settings(cls):
        """Get notification settings for student portal"""
        settings = cls.get_settings()
        return settings['notifications']