"""
Admin Configuration Panel for System Settings
Centralized management of attendance system configuration
"""

import json
import os
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import models, transaction
from django.core.exceptions import ValidationError
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

from users.models import User, AuditLog

logger = logging.getLogger(__name__)

class SystemConfiguration(models.Model):
    """
    System-wide configuration settings
    """
    SETTING_TYPES = [
        ('string', 'String'),
        ('integer', 'Integer'),
        ('float', 'Float'),
        ('boolean', 'Boolean'),
        ('json', 'JSON'),
    ]
    
    CATEGORIES = [
        ('attendance', 'Attendance Settings'),
        ('face_recognition', 'Face Recognition'),
        ('notifications', 'Notifications'),
        ('security', 'Security'),
        ('system', 'System'),
        ('ui', 'User Interface'),
    ]
    
    key = models.CharField(max_length=100, unique=True, db_index=True)
    value = models.TextField()
    value_type = models.CharField(max_length=20, choices=SETTING_TYPES, default='string')
    category = models.CharField(max_length=50, choices=CATEGORIES, default='system')
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False, help_text="Can be accessed by non-admin users")
    is_editable = models.BooleanField(default=True, help_text="Can be modified through admin panel")
    default_value = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "System Configuration"
        verbose_name_plural = "System Configurations"
        ordering = ['category', 'key']
    
    def __str__(self):
        return f"{self.category}.{self.key}"
    
    def get_typed_value(self):
        """Get value converted to appropriate type"""
        try:
            if self.value_type == 'integer':
                return int(self.value)
            elif self.value_type == 'float':
                return float(self.value)
            elif self.value_type == 'boolean':
                return self.value.lower() in ('true', '1', 'yes', 'on')
            elif self.value_type == 'json':
                return json.loads(self.value)
            else:
                return self.value
        except (ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error converting config value {self.key}: {e}")
            return self.default_value if self.default_value else None
    
    def set_typed_value(self, value):
        """Set value with type conversion"""
        try:
            if self.value_type == 'json':
                self.value = json.dumps(value)
            else:
                self.value = str(value)
        except Exception as e:
            logger.error(f"Error setting config value {self.key}: {e}")
            raise ValidationError(f"Invalid value for {self.value_type}: {value}")
    
    def save(self, *args, **kwargs):
        # Clear cache when configuration changes
        cache.delete(f"system_config:{self.key}")
        cache.delete("system_config:all")
        super().save(*args, **kwargs)


class SystemConfigurationService:
    """
    Service for managing system configuration
    """
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
        self._initialize_default_settings()
    
    def _initialize_default_settings(self):
        """Initialize default system settings"""
        default_settings = [
            # Attendance Settings
            {
                'key': 'attendance.presence_threshold_present',
                'value': '75.0',
                'value_type': 'float',
                'category': 'attendance',
                'description': 'Minimum presence percentage required to be marked as present',
                'is_public': True,
                'default_value': '75.0'
            },
            {
                'key': 'attendance.presence_threshold_partial',
                'value': '50.0',
                'value_type': 'float',
                'category': 'attendance',
                'description': 'Minimum presence percentage required to be marked as partial',
                'is_public': True,
                'default_value': '50.0'
            },
            {
                'key': 'attendance.presence_threshold_late',
                'value': '25.0',
                'value_type': 'float',
                'category': 'attendance',
                'description': 'Minimum presence percentage required to be marked as late',
                'is_public': True,
                'default_value': '25.0'
            },
            {
                'key': 'attendance.exam_eligibility_threshold',
                'value': '75.0',
                'value_type': 'float',
                'category': 'attendance',
                'description': 'Minimum attendance percentage required for exam eligibility',
                'is_public': True,
                'default_value': '75.0'
            },
            {
                'key': 'attendance.auto_finalize_sessions',
                'value': 'true',
                'value_type': 'boolean',
                'category': 'attendance',
                'description': 'Automatically finalize attendance when class sessions end',
                'is_public': False,
                'default_value': 'true'
            },
            
            # Face Recognition Settings
            {
                'key': 'face_recognition.confidence_threshold',
                'value': '0.6',
                'value_type': 'float',
                'category': 'face_recognition',
                'description': 'Minimum confidence score for face recognition',
                'is_public': False,
                'default_value': '0.6'
            },
            {
                'key': 'face_recognition.detection_interval',
                'value': '30',
                'value_type': 'integer',
                'category': 'face_recognition',
                'description': 'Face detection interval in seconds',
                'is_public': True,
                'default_value': '30'
            },
            {
                'key': 'face_recognition.max_faces_per_frame',
                'value': '10',
                'value_type': 'integer',
                'category': 'face_recognition',
                'description': 'Maximum number of faces to process per frame',
                'is_public': False,
                'default_value': '10'
            },
            {
                'key': 'face_recognition.require_face_consent',
                'value': 'true',
                'value_type': 'boolean',
                'category': 'face_recognition',
                'description': 'Require student consent for face recognition',
                'is_public': True,
                'default_value': 'true'
            },
            
            # Security Settings
            {
                'key': 'security.session_timeout_minutes',
                'value': '60',
                'value_type': 'integer',
                'category': 'security',
                'description': 'User session timeout in minutes',
                'is_public': False,
                'default_value': '60'
            },
            {
                'key': 'security.max_login_attempts',
                'value': '5',
                'value_type': 'integer',
                'category': 'security',
                'description': 'Maximum login attempts before account lockout',
                'is_public': False,
                'default_value': '5'
            },
            {
                'key': 'security.password_min_length',
                'value': '8',
                'value_type': 'integer',
                'category': 'security',
                'description': 'Minimum password length',
                'is_public': True,
                'default_value': '8'
            },
            
            # Notification Settings
            {
                'key': 'notifications.enable_email_notifications',
                'value': 'true',
                'value_type': 'boolean',
                'category': 'notifications',
                'description': 'Enable email notifications',
                'is_public': True,
                'default_value': 'true'
            },
            {
                'key': 'notifications.enable_whatsapp_notifications',
                'value': 'false',
                'value_type': 'boolean',
                'category': 'notifications',
                'description': 'Enable WhatsApp notifications (requires setup)',
                'is_public': True,
                'default_value': 'false'
            },
            {
                'key': 'notifications.low_attendance_warning_threshold',
                'value': '60.0',
                'value_type': 'float',
                'category': 'notifications',
                'description': 'Attendance percentage below which to send warnings',
                'is_public': True,
                'default_value': '60.0'
            },
            
            # System Settings
            {
                'key': 'system.institution_name',
                'value': 'University Name',
                'value_type': 'string',
                'category': 'system',
                'description': 'Institution name displayed in the system',
                'is_public': True,
                'default_value': 'University Name'
            },
            {
                'key': 'system.academic_year_format',
                'value': 'YYYY/YYYY',
                'value_type': 'string',
                'category': 'system',
                'description': 'Format for academic year display',
                'is_public': True,
                'default_value': 'YYYY/YYYY'
            },
            {
                'key': 'system.default_class_duration_minutes',
                'value': '90',
                'value_type': 'integer',
                'category': 'system',
                'description': 'Default class duration in minutes',
                'is_public': True,
                'default_value': '90'
            },
            
            # UI Settings
            {
                'key': 'ui.theme',
                'value': 'light',
                'value_type': 'string',
                'category': 'ui',
                'description': 'Default UI theme (light/dark)',
                'is_public': True,
                'default_value': 'light'
            },
            {
                'key': 'ui.items_per_page',
                'value': '20',
                'value_type': 'integer',
                'category': 'ui',
                'description': 'Default number of items per page in lists',
                'is_public': True,
                'default_value': '20'
            }
        ]
        
        # Create default settings if they don't exist
        for setting in default_settings:
            SystemConfiguration.objects.get_or_create(
                key=setting['key'],
                defaults=setting
            )
    
    def get_setting(self, key: str, default=None):
        """Get a configuration setting value"""
        try:
            # Try cache first
            cache_key = f"system_config:{key}"
            cached_value = cache.get(cache_key)
            
            if cached_value is not None:
                return cached_value
            
            # Get from database
            config = SystemConfiguration.objects.get(key=key)
            value = config.get_typed_value()
            
            # Cache the value
            cache.set(cache_key, value, self.cache_timeout)
            
            return value
            
        except SystemConfiguration.DoesNotExist:
            logger.warning(f"Configuration setting '{key}' not found")
            return default
        except Exception as e:
            logger.error(f"Error getting configuration setting '{key}': {e}")
            return default
    
    def set_setting(self, key: str, value: Any, user: Optional[User] = None) -> bool:
        """Set a configuration setting value"""
        try:
            with transaction.atomic():
                config, created = SystemConfiguration.objects.get_or_create(
                    key=key,
                    defaults={
                        'value': str(value),
                        'updated_by': user
                    }
                )
                
                if not created:
                    if not config.is_editable:
                        logger.warning(f"Attempted to modify non-editable setting: {key}")
                        return False
                    
                    old_value = config.value
                    config.set_typed_value(value)
                    config.updated_by = user
                    config.save()
                    
                    # Log the change
                    if user:
                        AuditLog.log_action(
                            user=user,
                            action='update',
                            model_name='SystemConfiguration',
                            object_id=str(config.id),
                            object_repr=str(config),
                            changes={
                                'key': key,
                                'old_value': old_value,
                                'new_value': config.value
                            }
                        )
                
                # Clear cache
                cache.delete(f"system_config:{key}")
                cache.delete("system_config:all")
                
                return True
                
        except Exception as e:
            logger.error(f"Error setting configuration '{key}': {e}")
            return False
    
    def get_all_settings(self, category: Optional[str] = None, public_only: bool = False) -> Dict[str, Any]:
        """Get all configuration settings"""
        try:
            # Try cache first
            cache_key = f"system_config:all:{category}:{public_only}"
            cached_settings = cache.get(cache_key)
            
            if cached_settings is not None:
                return cached_settings
            
            # Query database
            queryset = SystemConfiguration.objects.all()
            
            if category:
                queryset = queryset.filter(category=category)
            
            if public_only:
                queryset = queryset.filter(is_public=True)
            
            settings = {}
            for config in queryset:
                settings[config.key] = {
                    'value': config.get_typed_value(),
                    'type': config.value_type,
                    'category': config.category,
                    'description': config.description,
                    'is_public': config.is_public,
                    'is_editable': config.is_editable,
                    'updated_at': config.updated_at.isoformat()
                }
            
            # Cache the settings
            cache.set(cache_key, settings, self.cache_timeout)
            
            return settings
            
        except Exception as e:
            logger.error(f"Error getting all configuration settings: {e}")
            return {}
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all configuration categories with counts"""
        try:
            from django.db.models import Count
            
            categories = SystemConfiguration.objects.values('category').annotate(
                count=Count('id'),
                editable_count=Count('id', filter=models.Q(is_editable=True))
            ).order_by('category')
            
            return list(categories)
            
        except Exception as e:
            logger.error(f"Error getting configuration categories: {e}")
            return []
    
    def reset_to_defaults(self, category: Optional[str] = None, user: Optional[User] = None) -> int:
        """Reset settings to default values"""
        try:
            queryset = SystemConfiguration.objects.filter(is_editable=True)
            
            if category:
                queryset = queryset.filter(category=category)
            
            reset_count = 0
            
            with transaction.atomic():
                for config in queryset:
                    if config.default_value:
                        old_value = config.value
                        config.value = config.default_value
                        config.updated_by = user
                        config.save()
                        
                        reset_count += 1
                        
                        # Log the reset
                        if user:
                            AuditLog.log_action(
                                user=user,
                                action='update',
                                model_name='SystemConfiguration',
                                object_id=str(config.id),
                                object_repr=str(config),
                                changes={
                                    'key': config.key,
                                    'old_value': old_value,
                                    'new_value': config.value,
                                    'action': 'reset_to_default'
                                }
                            )
            
            # Clear all caches
            cache.delete_many([
                f"system_config:{config.key}" for config in queryset
            ])
            cache.delete("system_config:all")
            
            return reset_count
            
        except Exception as e:
            logger.error(f"Error resetting configuration to defaults: {e}")
            return 0


# Global configuration service instance
system_config_service = SystemConfigurationService()


# API Endpoints
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_system_configuration(request):
    """Get system configuration settings"""
    try:
        category = request.GET.get('category')
        public_only = not request.user.is_admin()
        
        settings = system_config_service.get_all_settings(category, public_only)
        
        return Response({
            'success': True,
            'data': {
                'settings': settings,
                'categories': system_config_service.get_categories() if request.user.is_admin() else []
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting system configuration: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get system configuration'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_system_configuration(request):
    """Update system configuration settings"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        settings = request.data.get('settings', {})
        
        if not settings:
            return Response({
                'success': False,
                'message': 'No settings provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        updated_count = 0
        failed_updates = []
        
        for key, value in settings.items():
            if system_config_service.set_setting(key, value, request.user):
                updated_count += 1
            else:
                failed_updates.append(key)
        
        return Response({
            'success': True,
            'message': f'Updated {updated_count} settings',
            'data': {
                'updated_count': updated_count,
                'failed_updates': failed_updates
            }
        })
        
    except Exception as e:
        logger.error(f"Error updating system configuration: {e}")
        return Response({
            'success': False,
            'message': 'Failed to update system configuration'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_configuration_to_defaults(request):
    """Reset configuration settings to default values"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        category = request.data.get('category')
        
        reset_count = system_config_service.reset_to_defaults(category, request.user)
        
        return Response({
            'success': True,
            'message': f'Reset {reset_count} settings to defaults',
            'data': {
                'reset_count': reset_count,
                'category': category
            }
        })
        
    except Exception as e:
        logger.error(f"Error resetting configuration: {e}")
        return Response({
            'success': False,
            'message': 'Failed to reset configuration'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attendance_thresholds(request):
    """Get current attendance threshold settings"""
    try:
        thresholds = {
            'present': system_config_service.get_setting('attendance.presence_threshold_present', 75.0),
            'partial': system_config_service.get_setting('attendance.presence_threshold_partial', 50.0),
            'late': system_config_service.get_setting('attendance.presence_threshold_late', 25.0),
            'exam_eligibility': system_config_service.get_setting('attendance.exam_eligibility_threshold', 75.0)
        }
        
        return Response({
            'success': True,
            'data': thresholds
        })
        
    except Exception as e:
        logger.error(f"Error getting attendance thresholds: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get attendance thresholds'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_attendance_thresholds(request):
    """Update attendance threshold settings"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        thresholds = request.data
        
        # Validate thresholds
        if not all(isinstance(v, (int, float)) and 0 <= v <= 100 for v in thresholds.values()):
            return Response({
                'success': False,
                'message': 'Thresholds must be numbers between 0 and 100'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update settings
        updated = {}
        for key, value in thresholds.items():
            setting_key = f'attendance.presence_threshold_{key}' if key != 'exam_eligibility' else 'attendance.exam_eligibility_threshold'
            if system_config_service.set_setting(setting_key, value, request.user):
                updated[key] = value
        
        return Response({
            'success': True,
            'message': 'Attendance thresholds updated successfully',
            'data': updated
        })
        
    except Exception as e:
        logger.error(f"Error updating attendance thresholds: {e}")
        return Response({
            'success': False,
            'message': 'Failed to update attendance thresholds'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)