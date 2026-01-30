"""
Email Management System Models

This module contains the data models for the email management system,
including email configuration, templates, history, and delivery tracking.
"""

from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.validators import EmailValidator
from django.utils import timezone
from django.core.exceptions import ValidationError
import json
import base64
import os
import logging

# Try to import cryptography, but make it optional for now
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

logger = logging.getLogger(__name__)


class EmailSecurityManager:
    """
    Manages encryption and security for email credentials.
    Implements secure password encryption with proper key management.
    """
    
    @staticmethod
    def _get_encryption_key():
        """
        Get or generate encryption key for password encryption.
        Uses Django SECRET_KEY as base for key derivation.
        """
        if not HAS_CRYPTOGRAPHY:
            logger.warning("Cryptography library not available. Passwords will not be encrypted.")
            return None
        
        try:
            # Use Django's SECRET_KEY as base for key derivation
            secret_key = settings.SECRET_KEY.encode()
            
            # Use a fixed salt for consistency (in production, consider using per-instance salt)
            salt = b'email_encryption_salt_v1'
            
            # Derive encryption key using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret_key))
            return key
            
        except Exception as e:
            logger.error(f"Failed to generate encryption key: {str(e)}")
            return None
    
    @staticmethod
    def encrypt_password(raw_password: str) -> str:
        """
        Encrypt password using Fernet symmetric encryption.
        
        Args:
            raw_password: Plain text password to encrypt
            
        Returns:
            Encrypted password as base64 string
        """
        if not raw_password:
            return ""
        
        if not HAS_CRYPTOGRAPHY:
            logger.warning("Password encryption not available. Storing password in plain text.")
            return raw_password
        
        try:
            key = EmailSecurityManager._get_encryption_key()
            if not key:
                logger.error("Could not generate encryption key")
                return raw_password
            
            cipher_suite = Fernet(key)
            encrypted_password = cipher_suite.encrypt(raw_password.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_password).decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to encrypt password: {str(e)}")
            return raw_password
    
    @staticmethod
    def decrypt_password(encrypted_password: str) -> str:
        """
        Decrypt password using Fernet symmetric encryption.
        
        Args:
            encrypted_password: Encrypted password as base64 string
            
        Returns:
            Decrypted plain text password
        """
        if not encrypted_password:
            return ""
        
        if not HAS_CRYPTOGRAPHY:
            # Return as-is if encryption not available
            return encrypted_password
        
        try:
            key = EmailSecurityManager._get_encryption_key()
            if not key:
                logger.error("Could not generate decryption key")
                return ""
            
            cipher_suite = Fernet(key)
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_password.encode('utf-8'))
            decrypted_password = cipher_suite.decrypt(encrypted_bytes)
            return decrypted_password.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Failed to decrypt password: {str(e)}")
            return ""
    
    @staticmethod
    def validate_ssl_tls_settings(use_tls: bool, use_ssl: bool, port: int) -> None:
        """
        Validate SSL/TLS encryption settings for security compliance.
        
        Args:
            use_tls: Whether TLS is enabled
            use_ssl: Whether SSL is enabled
            port: SMTP port number
            
        Raises:
            ValidationError: If settings are insecure or invalid
        """
        # Cannot use both TLS and SSL
        if use_tls and use_ssl:
            raise ValidationError(
                "Cannot enable both TLS and SSL simultaneously. "
                "Choose either TLS (recommended for port 587) or SSL (for port 465)."
            )
        
        # Warn about unencrypted connections
        if not use_tls and not use_ssl:
            if port in [25, 587]:
                raise ValidationError(
                    "Unencrypted SMTP connections are not secure. "
                    "Please enable TLS encryption for security."
                )
            logger.warning(f"Unencrypted SMTP connection on port {port} - security risk")
        
        # Validate port/encryption combinations
        if use_ssl and port != 465:
            logger.warning(f"SSL is typically used with port 465, but port {port} is configured")
        
        if use_tls and port not in [587, 25]:
            logger.warning(f"TLS is typically used with port 587, but port {port} is configured")
    
    @staticmethod
    def mask_sensitive_data(data: dict) -> dict:
        """
        Mask sensitive data in configuration for logging/display.
        
        Args:
            data: Dictionary containing configuration data
            
        Returns:
            Dictionary with sensitive fields masked
        """
        masked_data = data.copy()
        
        # Mask password fields
        password_fields = ['password', 'smtp_password', 'email_password']
        for field in password_fields:
            if field in masked_data and masked_data[field]:
                masked_data[field] = '***masked***'
        
        return masked_data


class EmailConfiguration(models.Model):
    """
    Stores SMTP server configuration for email sending.
    Passwords are encrypted using secure encryption with proper key management.
    """
    smtp_host = models.CharField(max_length=255, help_text="SMTP server hostname")
    smtp_port = models.IntegerField(default=587, help_text="SMTP server port")
    smtp_username = models.CharField(max_length=255, help_text="SMTP username/email")
    smtp_password = models.TextField(help_text="Encrypted SMTP password")  # Encrypted
    use_tls = models.BooleanField(default=True, help_text="Use TLS encryption")
    use_ssl = models.BooleanField(default=False, help_text="Use SSL encryption")
    from_email = models.EmailField(help_text="From email address")
    from_name = models.CharField(max_length=255, default="Student Management System", help_text="From name")
    is_active = models.BooleanField(default=True, help_text="Is this configuration active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_configuration'
        verbose_name = 'Email Configuration'
        verbose_name_plural = 'Email Configurations'

    def __str__(self):
        return f"{self.smtp_host}:{self.smtp_port} ({self.from_email})"

    def clean(self):
        """
        Validate model data including security settings.
        """
        super().clean()
        
        # Validate SSL/TLS settings
        try:
            EmailSecurityManager.validate_ssl_tls_settings(
                self.use_tls, 
                self.use_ssl, 
                self.smtp_port
            )
        except ValidationError as e:
            raise ValidationError({'__all__': e.message})
        
        # Validate email format
        if self.from_email:
            try:
                EmailValidator()(self.from_email)
            except ValidationError:
                raise ValidationError({'from_email': 'Invalid email address format'})
        
        # Validate SMTP host
        if not self.smtp_host or not self.smtp_host.strip():
            raise ValidationError({'smtp_host': 'SMTP host is required'})
        
        # Validate port range
        if not (1 <= self.smtp_port <= 65535):
            raise ValidationError({'smtp_port': 'Port must be between 1 and 65535'})

    def set_password(self, raw_password: str):
        """
        Encrypt and store the password using secure encryption.
        
        Args:
            raw_password: Plain text password to encrypt
        """
        if not raw_password:
            self.smtp_password = ""
            return
        
        self.smtp_password = EmailSecurityManager.encrypt_password(raw_password)
        
        # Log security event (without exposing password)
        logger.info(f"SMTP password updated for configuration {self.smtp_host}:{self.smtp_port}")

    def get_password(self) -> str:
        """
        Decrypt and return the password.
        
        Returns:
            Decrypted plain text password
        """
        if not self.smtp_password:
            return ""
        
        return EmailSecurityManager.decrypt_password(self.smtp_password)

    def get_decrypted_password(self) -> str:
        """
        Get the decrypted password (alias for get_password).
        
        Returns:
            Decrypted plain text password
        """
        return self.get_password()

    def get_masked_config(self) -> dict:
        """
        Get configuration with sensitive data masked for logging/display.
        
        Returns:
            Dictionary with masked sensitive fields
        """
        config_data = {
            'smtp_host': self.smtp_host,
            'smtp_port': self.smtp_port,
            'smtp_username': self.smtp_username,
            'smtp_password': self.smtp_password,
            'use_tls': self.use_tls,
            'use_ssl': self.use_ssl,
            'from_email': self.from_email,
            'from_name': self.from_name,
            'is_active': self.is_active
        }
        
        return EmailSecurityManager.mask_sensitive_data(config_data)

    def validate_security_settings(self) -> list:
        """
        Validate security settings and return list of warnings/recommendations.
        
        Returns:
            List of security warnings or recommendations
        """
        warnings = []
        
        # Check encryption settings
        if not self.use_tls and not self.use_ssl:
            warnings.append("No encryption enabled - connection will be insecure")
        
        # Check port/encryption alignment
        if self.use_ssl and self.smtp_port != 465:
            warnings.append(f"SSL typically uses port 465, but port {self.smtp_port} is configured")
        
        if self.use_tls and self.smtp_port not in [587, 25]:
            warnings.append(f"TLS typically uses port 587, but port {self.smtp_port} is configured")
        
        # Check for weak configurations
        if self.smtp_port == 25 and not self.use_tls:
            warnings.append("Port 25 without TLS is highly insecure and may be blocked")
        
        return warnings

    @classmethod
    def get_current_config(cls):
        """Get the current active email configuration"""
        return cls.objects.filter(is_active=True).first()
    
    @property
    def email_user(self):
        """Alias for smtp_username for backward compatibility"""
        return self.smtp_username
    
    @property
    def provider(self):
        """Detect email provider based on SMTP host"""
        host_lower = self.smtp_host.lower()
        if 'gmail' in host_lower:
            return 'gmail'
        elif 'outlook' in host_lower or 'office365' in host_lower:
            return 'outlook'
        elif 'yahoo' in host_lower:
            return 'yahoo'
        else:
            return 'custom'
    
    @property
    def email_password(self):
        """Alias for smtp_password for backward compatibility"""
        return self.smtp_password
    
    @property
    def provider(self):
        """Determine provider based on SMTP host"""
        if 'gmail' in self.smtp_host.lower():
            return 'gmail'
        elif 'outlook' in self.smtp_host.lower() or 'hotmail' in self.smtp_host.lower():
            return 'outlook'
        elif 'yahoo' in self.smtp_host.lower():
            return 'yahoo'
        elif 'office365' in self.smtp_host.lower():
            return 'office365'
        else:
            return 'custom'


class EmailTemplate(models.Model):
    """
    Pre-defined email templates for common communication scenarios.
    """
    CATEGORY_CHOICES = [
        ('attendance', 'Attendance'),
        ('course', 'Course Updates'),
        ('exam', 'Exam Notifications'),
        ('general', 'General Announcements'),
    ]

    name = models.CharField(max_length=255, help_text="Template name")
    category = models.CharField(max_length=100, choices=CATEGORY_CHOICES, help_text="Template category")
    subject_template = models.CharField(max_length=500, help_text="Email subject template")
    body_template = models.TextField(help_text="Email body template")
    variables = models.JSONField(default=list, help_text="Available template variables")
    description = models.TextField(blank=True, help_text="Template description")
    is_active = models.BooleanField(default=True, help_text="Is this template active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_template'
        verbose_name = 'Email Template'
        verbose_name_plural = 'Email Templates'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.category})"

    def get_variables(self):
        """Return template variables as a list"""
        if isinstance(self.variables, list):
            return self.variables
        elif isinstance(self.variables, str):
            try:
                return json.loads(self.variables)
            except json.JSONDecodeError:
                return []
        return []


class EmailHistory(models.Model):
    """
    Records of all sent emails for audit and tracking purposes.
    """
    STATUS_CHOICES = [
        ('sending', 'Sending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        help_text="User who sent the email"
    )
    subject = models.CharField(max_length=500, help_text="Email subject")
    body = models.TextField(help_text="Email body content")
    template_used = models.ForeignKey(
        EmailTemplate, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        help_text="Template used for this email"
    )
    recipient_count = models.IntegerField(default=0, help_text="Total number of recipients")
    sent_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='sending')
    success_count = models.IntegerField(default=0, help_text="Number of successful deliveries")
    failure_count = models.IntegerField(default=0, help_text="Number of failed deliveries")
    error_message = models.TextField(blank=True, help_text="Error message if sending failed")

    class Meta:
        db_table = 'email_history'
        verbose_name = 'Email History'
        verbose_name_plural = 'Email History'
        ordering = ['-sent_at']

    def __str__(self):
        return f"{self.subject} - {self.sent_at.strftime('%Y-%m-%d %H:%M')}"

    @property
    def success_rate(self):
        """Calculate success rate as percentage"""
        if self.recipient_count == 0:
            return 0
        return (self.success_count / self.recipient_count) * 100


class EmailDelivery(models.Model):
    """
    Individual delivery status for each recipient of an email.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('bounced', 'Bounced'),
    ]

    email_history = models.ForeignKey(
        EmailHistory, 
        on_delete=models.CASCADE, 
        related_name='deliveries',
        help_text="Associated email history record"
    )
    recipient_email = models.EmailField(help_text="Recipient email address")
    recipient_name = models.CharField(max_length=255, blank=True, help_text="Recipient name")
    student = models.ForeignKey(
        'Student', 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        help_text="Associated student record"
    )
    delivery_status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, help_text="Error message if delivery failed")
    sent_at = models.DateTimeField(null=True, blank=True, help_text="When email was sent")
    delivered_at = models.DateTimeField(null=True, blank=True, help_text="When email was delivered")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'email_delivery'
        verbose_name = 'Email Delivery'
        verbose_name_plural = 'Email Deliveries'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email_history', 'delivery_status']),
            models.Index(fields=['recipient_email']),
            models.Index(fields=['student']),
        ]

    def __str__(self):
        return f"{self.recipient_email} - {self.delivery_status}"

    def mark_sent(self):
        """Mark delivery as sent"""
        self.delivery_status = 'sent'
        self.sent_at = timezone.now()
        self.save()

    def mark_delivered(self):
        """Mark delivery as delivered"""
        self.delivery_status = 'delivered'
        self.delivered_at = timezone.now()
        self.save()

    def mark_failed(self, error_message=""):
        """Mark delivery as failed"""
        self.delivery_status = 'failed'
        self.error_message = error_message
        self.save()