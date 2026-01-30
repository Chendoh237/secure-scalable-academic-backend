"""
Email Service for the Email Management System

This service handles SMTP configuration, connection testing, and email sending
with support for multiple email providers (Gmail, Outlook, Yahoo, custom).
Enhanced with comprehensive security measures and SSL/TLS validation.
"""

import smtplib
import ssl
import socket
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import List, Dict, Any, Optional, Tuple
import logging
import time
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction
from django.core.cache import cache
from .email_models import EmailConfiguration, EmailHistory, EmailDelivery, EmailSecurityManager
from .models_settings import SystemSettings

logger = logging.getLogger(__name__)


class EmailServiceError(Exception):
    """Base exception for email service errors"""
    pass


class SMTPConnectionError(EmailServiceError):
    """Raised when SMTP connection fails"""
    pass


class EmailSendError(EmailServiceError):
    """Raised when email sending fails"""
    pass


class EmailSecurityError(EmailServiceError):
    """Raised when security validation fails"""
    pass


class EmailRateLimiter:
    """
    Rate limiter for email sending to comply with SMTP server restrictions.
    Implements token bucket algorithm with per-provider limits.
    """
    
    def __init__(self):
        self.rate_limits = {
            'gmail': {'emails_per_minute': 100, 'emails_per_hour': 2000},
            'outlook': {'emails_per_minute': 30, 'emails_per_hour': 10000},
            'yahoo': {'emails_per_minute': 100, 'emails_per_hour': 500},
            'office365': {'emails_per_minute': 30, 'emails_per_hour': 10000},
            'custom': {'emails_per_minute': 60, 'emails_per_hour': 1000}  # Conservative default
        }
        self.counters = defaultdict(lambda: {'minute': [], 'hour': []})
        self.lock = threading.Lock()
    
    def can_send_email(self, provider: str, count: int = 1) -> Tuple[bool, str]:
        """
        Check if emails can be sent within rate limits.
        
        Args:
            provider: Email provider (gmail, outlook, etc.)
            count: Number of emails to send
            
        Returns:
            Tuple of (can_send, reason_if_not)
        """
        with self.lock:
            now = datetime.now()
            provider_limits = self.rate_limits.get(provider, self.rate_limits['custom'])
            
            # Clean old entries
            self._clean_old_entries(provider, now)
            
            # Check minute limit
            minute_count = len(self.counters[provider]['minute'])
            if minute_count + count > provider_limits['emails_per_minute']:
                return False, f"Rate limit exceeded: {minute_count + count} emails would exceed {provider_limits['emails_per_minute']} per minute limit"
            
            # Check hour limit
            hour_count = len(self.counters[provider]['hour'])
            if hour_count + count > provider_limits['emails_per_hour']:
                return False, f"Rate limit exceeded: {hour_count + count} emails would exceed {provider_limits['emails_per_hour']} per hour limit"
            
            return True, ""
    
    def record_sent_emails(self, provider: str, count: int = 1):
        """Record sent emails for rate limiting."""
        with self.lock:
            now = datetime.now()
            for _ in range(count):
                self.counters[provider]['minute'].append(now)
                self.counters[provider]['hour'].append(now)
    
    def _clean_old_entries(self, provider: str, now: datetime):
        """Remove entries older than the time window."""
        minute_ago = now - timedelta(minutes=1)
        hour_ago = now - timedelta(hours=1)
        
        self.counters[provider]['minute'] = [
            t for t in self.counters[provider]['minute'] if t > minute_ago
        ]
        self.counters[provider]['hour'] = [
            t for t in self.counters[provider]['hour'] if t > hour_ago
        ]
    
    def get_wait_time(self, provider: str) -> int:
        """Get recommended wait time in seconds before next send."""
        with self.lock:
            now = datetime.now()
            self._clean_old_entries(provider, now)
            
            provider_limits = self.rate_limits.get(provider, self.rate_limits['custom'])
            minute_count = len(self.counters[provider]['minute'])
            
            if minute_count >= provider_limits['emails_per_minute']:
                # Find oldest entry in current minute
                if self.counters[provider]['minute']:
                    oldest = min(self.counters[provider]['minute'])
                    wait_time = 60 - (now - oldest).seconds
                    return max(wait_time, 1)
            
            return 0


class EmailOperationManager:
    """
    Manages email operations with cancellation support and progress tracking.
    """
    
    def __init__(self):
        self.operations = {}
        self.lock = threading.Lock()
    
    def start_operation(self, operation_id: str, total_count: int) -> Dict[str, Any]:
        """Start a new email operation."""
        with self.lock:
            self.operations[operation_id] = {
                'status': 'running',
                'total_count': total_count,
                'processed_count': 0,
                'success_count': 0,
                'failed_count': 0,
                'start_time': datetime.now(),
                'cancelled': False,
                'progress_callback': None
            }
        return self.operations[operation_id]
    
    def update_progress(self, operation_id: str, processed: int, success: int, failed: int):
        """Update operation progress."""
        with self.lock:
            if operation_id in self.operations:
                op = self.operations[operation_id]
                op['processed_count'] = processed
                op['success_count'] = success
                op['failed_count'] = failed
                
                if op['progress_callback']:
                    op['progress_callback'](op)
    
    def cancel_operation(self, operation_id: str) -> bool:
        """Cancel an operation."""
        with self.lock:
            if operation_id in self.operations:
                self.operations[operation_id]['cancelled'] = True
                self.operations[operation_id]['status'] = 'cancelled'
                return True
        return False
    
    def is_cancelled(self, operation_id: str) -> bool:
        """Check if operation is cancelled."""
        with self.lock:
            return self.operations.get(operation_id, {}).get('cancelled', False)
    
    def complete_operation(self, operation_id: str):
        """Mark operation as completed."""
        with self.lock:
            if operation_id in self.operations:
                self.operations[operation_id]['status'] = 'completed'
                self.operations[operation_id]['end_time'] = datetime.now()
    
    def get_operation_status(self, operation_id: str) -> Optional[Dict[str, Any]]:
        """Get operation status."""
        with self.lock:
            return self.operations.get(operation_id)


class EmailBatchProcessor:
    """
    Optimized batch processor for large email operations.
    """
    
    def __init__(self, rate_limiter: EmailRateLimiter, operation_manager: EmailOperationManager):
        self.rate_limiter = rate_limiter
        self.operation_manager = operation_manager
    
    def calculate_optimal_batch_size(self, total_recipients: int, provider: str) -> int:
        """
        Calculate optimal batch size based on recipient count and provider limits.
        
        Args:
            total_recipients: Total number of recipients
            provider: Email provider
            
        Returns:
            Optimal batch size
        """
        provider_limits = self.rate_limiter.rate_limits.get(provider, self.rate_limiter.rate_limits['custom'])
        max_per_minute = provider_limits['emails_per_minute']
        
        # For small lists, use smaller batches
        if total_recipients <= 50:
            return min(10, total_recipients)
        elif total_recipients <= 200:
            return min(25, max_per_minute // 4)
        elif total_recipients <= 1000:
            return min(50, max_per_minute // 3)
        else:
            # For large lists, use larger batches but respect rate limits
            return min(100, max_per_minute // 2)
    
    def calculate_batch_delay(self, batch_size: int, provider: str) -> float:
        """
        Calculate delay between batches to respect rate limits.
        
        Args:
            batch_size: Size of each batch
            provider: Email provider
            
        Returns:
            Delay in seconds
        """
        provider_limits = self.rate_limiter.rate_limits.get(provider, self.rate_limiter.rate_limits['custom'])
        max_per_minute = provider_limits['emails_per_minute']
        
        # Calculate delay to stay within rate limits
        if batch_size >= max_per_minute:
            return 60.0  # Wait full minute if batch is at limit
        else:
            # Calculate proportional delay
            delay = (batch_size / max_per_minute) * 60.0
            return max(delay, 1.0)  # Minimum 1 second delay


class EmailSecurityError(EmailServiceError):
    """Raised when security validation fails"""
    pass


class EmailService:
    """
    Core email service for SMTP connection management and email sending.
    Supports Gmail, Outlook, Yahoo, and custom SMTP servers with enhanced security.
    """
    
    # Predefined SMTP configurations for popular providers with security settings
    PROVIDER_CONFIGS = {
        'gmail': {
            'smtp_host': 'smtp.gmail.com',
            'smtp_port': 587,
            'use_tls': True,
            'use_ssl': False,
            'security_level': 'high',
            'requires_app_password': True
        },
        'outlook': {
            'smtp_host': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'use_tls': True,
            'use_ssl': False,
            'security_level': 'high',
            'requires_app_password': False
        },
        'yahoo': {
            'smtp_host': 'smtp.mail.yahoo.com',
            'smtp_port': 587,
            'use_tls': True,
            'use_ssl': False,
            'security_level': 'medium',
            'requires_app_password': True
        },
        'office365': {
            'smtp_host': 'smtp.office365.com',
            'smtp_port': 587,
            'use_tls': True,
            'use_ssl': False,
            'security_level': 'high',
            'requires_app_password': False
        }
    }
    
    def __init__(self):
        """Initialize the email service with security enhancements and performance optimizations"""
        self.smtp_connection = None
        self.current_config = None
        self.security_manager = EmailSecurityManager()
        self.rate_limiter = EmailRateLimiter()
        self.operation_manager = EmailOperationManager()
        self.batch_processor = EmailBatchProcessor(self.rate_limiter, self.operation_manager)
        self._connection_pool = {}
        self._connection_pool_lock = threading.Lock()
    
    def _validate_security_requirements(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate security requirements for SMTP configuration.
        
        Args:
            config: SMTP configuration dictionary
            
        Returns:
            Dictionary with validation results and security warnings
        """
        validation_result = {
            'is_secure': True,
            'warnings': [],
            'recommendations': [],
            'security_level': 'unknown'
        }
        
        try:
            # Validate SSL/TLS settings
            EmailSecurityManager.validate_ssl_tls_settings(
                config.get('use_tls', False),
                config.get('use_ssl', False),
                config.get('smtp_port', 587)
            )
            
            # Determine security level
            if config.get('use_ssl') or config.get('use_tls'):
                validation_result['security_level'] = 'high'
            else:
                validation_result['security_level'] = 'low'
                validation_result['is_secure'] = False
                validation_result['warnings'].append('No encryption enabled - connection is insecure')
            
            # Check for secure ports
            port = config.get('smtp_port', 587)
            if port == 25 and not config.get('use_tls'):
                validation_result['warnings'].append('Port 25 without TLS is highly insecure')
                validation_result['is_secure'] = False
            
            # Provider-specific security checks
            host = config.get('smtp_host', '').lower()
            if 'gmail' in host:
                validation_result['recommendations'].append('Use App Password instead of regular password for Gmail')
            elif 'yahoo' in host:
                validation_result['recommendations'].append('Enable 2FA and use App Password for Yahoo')
            
            # Check for weak configurations
            if not config.get('use_tls') and not config.get('use_ssl'):
                validation_result['recommendations'].append('Enable TLS or SSL encryption for secure communication')
            
        except ValidationError as e:
            validation_result['is_secure'] = False
            validation_result['warnings'].append(str(e))
        
        return validation_result
    
    def _create_secure_ssl_context(self, verify_mode: bool = True) -> ssl.SSLContext:
        """
        Create a secure SSL context with proper security settings.
        
        Args:
            verify_mode: Whether to verify SSL certificates
            
        Returns:
            Configured SSL context
        """
        # Create secure SSL context
        context = ssl.create_default_context()
        
        # Configure security settings
        context.check_hostname = verify_mode
        context.verify_mode = ssl.CERT_REQUIRED if verify_mode else ssl.CERT_NONE
        
        # Disable weak protocols and ciphers
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1
        
        # Set minimum TLS version to 1.2
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        
        return context
    
    def _get_or_create_smtp_connection(self, config: Dict[str, Any], timeout: int = 30) -> smtplib.SMTP:
        """
        Get or create SMTP connection with connection pooling for performance.
        
        Args:
            config: SMTP configuration
            timeout: Connection timeout
            
        Returns:
            SMTP connection object
        """
        connection_key = f"{config['smtp_host']}:{config['smtp_port']}:{config['smtp_username']}"
        
        with self._connection_pool_lock:
            # Check if we have a valid connection in pool
            if connection_key in self._connection_pool:
                smtp_server = self._connection_pool[connection_key]
                try:
                    # Test if connection is still alive
                    smtp_server.noop()
                    return smtp_server
                except:
                    # Connection is dead, remove from pool
                    del self._connection_pool[connection_key]
            
            # Create new connection
            smtp_server = None
            try:
                if config['use_ssl']:
                    context = self._create_secure_ssl_context(verify_mode=True)
                    smtp_server = smtplib.SMTP_SSL(
                        config['smtp_host'], 
                        config['smtp_port'], 
                        context=context,
                        timeout=timeout
                    )
                else:
                    smtp_server = smtplib.SMTP(
                        config['smtp_host'], 
                        config['smtp_port'],
                        timeout=timeout
                    )
                    
                    if config['use_tls']:
                        context = self._create_secure_ssl_context(verify_mode=True)
                        smtp_server.starttls(context=context)
                
                # Authenticate
                smtp_server.login(config['smtp_username'], config['smtp_password'])
                
                # Add to connection pool
                self._connection_pool[connection_key] = smtp_server
                
                return smtp_server
                
            except Exception as e:
                if smtp_server:
                    try:
                        smtp_server.quit()
                    except:
                        pass
                raise e
    
    def _close_smtp_connections(self):
        """Close all SMTP connections in the pool."""
        with self._connection_pool_lock:
            for smtp_server in self._connection_pool.values():
                try:
                    smtp_server.quit()
                except:
                    pass
            self._connection_pool.clear()
    
    def _optimize_recipient_queries(self, recipient_filters: Dict[str, Any]) -> List[str]:
        """
        Optimize database queries for recipient selection with caching and efficient queries.
        
        Args:
            recipient_filters: Filters for recipient selection
            
        Returns:
            List of optimized recipient email addresses
        """
        cache_key = f"recipients_{hash(str(sorted(recipient_filters.items())))}"
        
        # Try to get from cache first
        cached_recipients = cache.get(cache_key)
        if cached_recipients:
            logger.info(f"Retrieved {len(cached_recipients)} recipients from cache")
            return cached_recipients
        
        # Import here to avoid circular imports
        from .models import Student
        
        recipients = []
        
        try:
            # Use select_related and prefetch_related for efficient queries
            queryset = Student.objects.select_related('department', 'level').filter(
                email__isnull=False,
                email__gt='',
                is_active=True
            )
            
            # Apply filters efficiently
            if recipient_filters.get('department_ids'):
                queryset = queryset.filter(department_id__in=recipient_filters['department_ids'])
            
            if recipient_filters.get('level_ids'):
                queryset = queryset.filter(level_id__in=recipient_filters['level_ids'])
            
            if recipient_filters.get('student_ids'):
                queryset = queryset.filter(id__in=recipient_filters['student_ids'])
            
            # Use values_list for memory efficiency
            recipients = list(queryset.values_list('email', flat=True).distinct())
            
            # Cache results for 5 minutes
            cache.set(cache_key, recipients, 300)
            
            logger.info(f"Retrieved {len(recipients)} recipients from database with optimized query")
            
        except Exception as e:
            logger.error(f"Error optimizing recipient queries: {str(e)}")
            # Fallback to basic query
            from .models import Student
            recipients = list(Student.objects.filter(
                email__isnull=False,
                email__gt='',
                is_active=True
            ).values_list('email', flat=True))
        
        return recipients
    
    def _log_security_event(self, event_type: str, details: Dict[str, Any], user=None):
        """
        Log security-related events without exposing sensitive data.
        
        Args:
            event_type: Type of security event
            details: Event details (will be masked)
            user: User associated with the event
        """
        # Mask sensitive data
        masked_details = EmailSecurityManager.mask_sensitive_data(details)
        
        # Log security event
        logger.info(f"Security Event: {event_type} - User: {user} - Details: {masked_details}")
    
    def validate_smtp_security(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate SMTP configuration security and provide recommendations.
        
        Args:
            config_data: SMTP configuration to validate
            
        Returns:
            Dictionary with security validation results
        """
        try:
            # Get SMTP configuration
            config = self._get_smtp_config(config_data)
            
            # Validate security requirements
            security_result = self._validate_security_requirements(config)
            
            # Log security validation
            self._log_security_event('smtp_security_validation', {
                'host': config.get('smtp_host'),
                'port': config.get('smtp_port'),
                'encryption': 'TLS' if config.get('use_tls') else ('SSL' if config.get('use_ssl') else 'None'),
                'security_level': security_result['security_level']
            })
            
            return {
                'success': True,
                'security_validation': security_result
            }
            
        except Exception as e:
            logger.error(f"Security validation failed: {str(e)}")
            return {
                'success': False,
                'error': f'Security validation failed: {str(e)}'
            }
    
    def _load_email_settings(self) -> Dict[str, Any]:
        """Load email settings from EmailConfiguration model"""
        try:
            email_config = EmailConfiguration.get_current_config()
            if not email_config:
                raise EmailServiceError("No SMTP configuration found. Please configure SMTP settings first.")
            
            return {
                'smtpServer': email_config.smtp_host,
                'smtpPort': email_config.smtp_port,
                'emailUser': email_config.smtp_username,
                'emailPassword': email_config.get_decrypted_password(),
                'useTLS': email_config.use_tls,
                'useSSL': email_config.use_ssl,
                'fromName': email_config.from_name,
                'enableEmailNotifications': True
            }
        except Exception as e:
            logger.error(f"Failed to load email settings: {str(e)}")
            raise EmailServiceError(f"Failed to load email settings: {str(e)}")
    
    def _get_smtp_config(self, config_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get SMTP configuration from provided data or EmailConfiguration model.
        
        Args:
            config_data: Optional configuration data to use instead of database config
            
        Returns:
            Dictionary containing SMTP configuration
        """
        if config_data:
            return {
                'smtp_host': config_data.get('smtpServer', ''),
                'smtp_port': config_data.get('smtpPort', 587),
                'smtp_username': config_data.get('emailUser', ''),
                'smtp_password': config_data.get('emailPassword', ''),
                'use_tls': config_data.get('useTLS', True),
                'use_ssl': config_data.get('useSSL', False),
                'from_email': config_data.get('emailUser', ''),
                'from_name': config_data.get('fromName', 'Student Management System'),
            }
        else:
            # Get configuration from EmailConfiguration model
            email_config = EmailConfiguration.get_current_config()
            if not email_config:
                raise EmailServiceError("No SMTP configuration found. Please configure SMTP settings first.")
            
            return {
                'smtp_host': email_config.smtp_host,
                'smtp_port': email_config.smtp_port,
                'smtp_username': email_config.smtp_username,
                'smtp_password': email_config.get_decrypted_password(),
                'use_tls': email_config.use_tls,
                'use_ssl': email_config.use_ssl,
                'from_email': email_config.from_email,
                'from_name': email_config.from_name,
            }
    
    def _validate_smtp_config(self, config: Dict[str, Any]) -> None:
        """
        Validate SMTP configuration with comprehensive error messages.
        
        Args:
            config: SMTP configuration dictionary
            
        Raises:
            EmailServiceError: If configuration is invalid
        """
        required_fields = {
            'smtp_host': 'SMTP server host (e.g., smtp.gmail.com)',
            'smtp_port': 'SMTP server port (e.g., 587 for TLS, 465 for SSL)',
            'smtp_username': 'SMTP username (usually your email address)',
            'smtp_password': 'SMTP password (use App Password for Gmail)',
            'from_email': 'From email address'
        }
        
        # Check for missing required fields
        missing_fields = []
        for field, description in required_fields.items():
            if not config.get(field):
                missing_fields.append(f"{description}")
        
        if missing_fields:
            raise EmailServiceError(
                f"Missing required SMTP configuration fields: {', '.join(missing_fields)}. "
                "Please ensure all fields are filled in correctly."
            )
        
        # Validate port number with specific error messages
        try:
            port = int(config['smtp_port'])
            if not (1 <= port <= 65535):
                raise EmailServiceError(
                    f"SMTP port {port} is invalid. Port must be between 1 and 65535. "
                    "Common ports: 587 (TLS), 465 (SSL), 25 (unencrypted - not recommended)"
                )
        except (ValueError, TypeError):
            raise EmailServiceError(
                f"SMTP port '{config['smtp_port']}' is not a valid number. "
                "Please enter a numeric port (e.g., 587 for TLS or 465 for SSL)"
            )
        
        # Validate email format with helpful message
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        
        try:
            validate_email(config['from_email'])
        except ValidationError:
            raise EmailServiceError(
                f"Invalid from_email format: '{config['from_email']}'. "
                "Please enter a valid email address (e.g., admin@university.edu)"
            )
        
        # Validate host format
        host = config['smtp_host'].strip()
        if not host:
            raise EmailServiceError("SMTP host cannot be empty")
        
        # Check for common host format issues
        if host.startswith('http://') or host.startswith('https://'):
            raise EmailServiceError(
                f"SMTP host should not include protocol. Use '{host.replace('https://', '').replace('http://', '')}' instead of '{host}'"
            )
        
        # Validate encryption settings
        use_tls = config.get('use_tls', False)
        use_ssl = config.get('use_ssl', False)
        
        if use_tls and use_ssl:
            raise EmailServiceError(
                "Cannot use both TLS and SSL simultaneously. Choose either TLS (port 587) or SSL (port 465)"
            )
        
        # Provide port/encryption guidance
        port = int(config['smtp_port'])
        if port == 465 and not use_ssl:
            logger.warning("Port 465 typically requires SSL encryption")
        elif port == 587 and not use_tls:
            logger.warning("Port 587 typically requires TLS encryption")
    
    def configure_smtp(self, settings_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Configure SMTP settings and store them in EmailConfiguration model.
        
        Args:
            settings_dict: Dictionary containing SMTP configuration
            
        Returns:
            Dictionary with success status and message
        """
        try:
            # Validate configuration
            smtp_config = self._get_smtp_config(settings_dict)
            self._validate_smtp_config(smtp_config)
            
            # Get or create EmailConfiguration
            config = EmailConfiguration.get_current_config()
            
            if config:
                # Update existing configuration
                config.smtp_host = settings_dict.get('smtpServer', '')
                config.smtp_port = int(settings_dict.get('smtpPort', 587))
                config.smtp_username = settings_dict.get('emailUser', '')
                config.set_password(settings_dict.get('emailPassword', ''))
                config.use_tls = settings_dict.get('useTLS', True)
                config.use_ssl = settings_dict.get('useSSL', False)
                config.from_name = settings_dict.get('fromName', 'Student Management System')
                config.from_email = settings_dict.get('emailUser', '')
                config.is_active = True
                config.save()
            else:
                # Create new configuration
                config = EmailConfiguration.objects.create(
                    smtp_host=settings_dict.get('smtpServer', ''),
                    smtp_port=int(settings_dict.get('smtpPort', 587)),
                    smtp_username=settings_dict.get('emailUser', ''),
                    from_email=settings_dict.get('emailUser', ''),
                    use_tls=settings_dict.get('useTLS', True),
                    use_ssl=settings_dict.get('useSSL', False),
                    from_name=settings_dict.get('fromName', 'Student Management System'),
                    is_active=True
                )
                config.set_password(settings_dict.get('emailPassword', ''))
                config.save()
            
            logger.info("SMTP configuration updated successfully")
            return {
                'success': True,
                'message': 'SMTP configuration saved successfully'
            }
            
        except Exception as e:
            logger.error(f"Failed to configure SMTP: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def test_connection(self, config_data: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Dict[str, Any]:
        """
        Test SMTP server connection and authentication with enhanced security validation.
        
        Args:
            config_data: Optional configuration data to test instead of system settings
            timeout: Connection timeout in seconds
            
        Returns:
            Dictionary with test results, security validation, and detailed error information
        """
        try:
            # Get SMTP configuration
            config = self._get_smtp_config(config_data)
            self._validate_smtp_config(config)
            
            # Validate security settings
            security_validation = self._validate_security_requirements(config)
            
            # Log security validation
            self._log_security_event('smtp_connection_test', {
                'host': config['smtp_host'],
                'port': config['smtp_port'],
                'encryption': 'TLS' if config['use_tls'] else ('SSL' if config['use_ssl'] else 'None')
            })
            
            # Create SMTP connection with timeout and enhanced security
            smtp_server = None
            try:
                if config['use_ssl']:
                    # Use SSL connection with secure context
                    context = self._create_secure_ssl_context(verify_mode=True)
                    smtp_server = smtplib.SMTP_SSL(
                        config['smtp_host'], 
                        config['smtp_port'], 
                        context=context,
                        timeout=timeout
                    )
                else:
                    # Use regular connection, potentially with TLS
                    smtp_server = smtplib.SMTP(
                        config['smtp_host'], 
                        config['smtp_port'],
                        timeout=timeout
                    )
                    
                    if config['use_tls']:
                        # Use secure TLS context
                        context = self._create_secure_ssl_context(verify_mode=True)
                        smtp_server.starttls(context=context)
                
                # Test authentication
                smtp_server.login(config['smtp_username'], config['smtp_password'])
                
                # If we get here, connection and authentication succeeded
                smtp_server.quit()
                
                logger.info(f"SMTP connection test successful for {config['smtp_host']}")
                return {
                    'success': True,
                    'message': f'Successfully connected to {config["smtp_host"]}:{config["smtp_port"]}',
                    'details': {
                        'host': config['smtp_host'],
                        'port': config['smtp_port'],
                        'encryption': 'SSL' if config['use_ssl'] else ('TLS' if config['use_tls'] else 'None'),
                        'username': config['smtp_username'],
                        'security_level': security_validation['security_level']
                    },
                    'security_validation': security_validation
                }
                
            except smtplib.SMTPAuthenticationError as e:
                error_code = getattr(e, 'smtp_code', None)
                error_msg = str(e)
                
                # Provide specific guidance based on error code
                if error_code == 535:
                    if 'gmail' in config['smtp_host'].lower():
                        user_msg = ("SMTP authentication failed. For Gmail accounts:\n"
                                  "1. Enable 2-factor authentication\n"
                                  "2. Generate an App Password (not your regular password)\n"
                                  "3. Use the App Password in the password field\n"
                                  "4. Ensure 'Less secure app access' is enabled if not using App Password")
                    else:
                        user_msg = ("SMTP authentication failed. Please check:\n"
                                  "1. Username and password are correct\n"
                                  "2. Account has SMTP access enabled\n"
                                  "3. Two-factor authentication settings if applicable")
                else:
                    user_msg = f"SMTP authentication failed: {error_msg}"
                
                logger.error(f"SMTP authentication error: {error_msg}")
                return {
                    'success': False,
                    'error': user_msg,
                    'technical_details': error_msg,
                    'error_code': error_code,
                    'retry_suggested': True
                }
                
            except smtplib.SMTPConnectError as e:
                error_msg = str(e)
                user_msg = (f"Could not connect to SMTP server {config['smtp_host']}:{config['smtp_port']}. "
                           "Please check:\n"
                           "1. Server address and port are correct\n"
                           "2. Internet connection is working\n"
                           "3. Firewall is not blocking the connection\n"
                           "4. Server is not temporarily unavailable")
                
                logger.error(f"SMTP connection error: {error_msg}")
                return {
                    'success': False,
                    'error': user_msg,
                    'technical_details': error_msg,
                    'retry_suggested': True
                }
                
            except smtplib.SMTPServerDisconnected as e:
                error_msg = str(e)
                user_msg = ("SMTP server disconnected unexpectedly. This may indicate:\n"
                           "1. Server is overloaded or temporarily unavailable\n"
                           "2. Connection timeout occurred\n"
                           "3. Network connectivity issues\n"
                           "Please try again in a few moments.")
                
                logger.error(f"SMTP server disconnected: {error_msg}")
                return {
                    'success': False,
                    'error': user_msg,
                    'technical_details': error_msg,
                    'retry_suggested': True
                }
                
            except socket.timeout as e:
                user_msg = (f"Connection timed out after {timeout} seconds. This may indicate:\n"
                           "1. Server is slow to respond\n"
                           "2. Network connectivity issues\n"
                           "3. Incorrect server address or port\n"
                           "Please check your settings and try again.")
                
                logger.error(f"SMTP connection timeout: {str(e)}")
                return {
                    'success': False,
                    'error': user_msg,
                    'technical_details': str(e),
                    'retry_suggested': True
                }
                
            except socket.gaierror as e:
                error_msg = str(e)
                user_msg = (f"Could not resolve server address '{config['smtp_host']}'. Please check:\n"
                           "1. Server address is spelled correctly\n"
                           "2. DNS resolution is working\n"
                           "3. Internet connection is active")
                
                logger.error(f"SMTP DNS resolution error: {error_msg}")
                return {
                    'success': False,
                    'error': user_msg,
                    'technical_details': error_msg,
                    'retry_suggested': False
                }
                
            except ssl.SSLError as e:
                error_msg = str(e)
                user_msg = ("SSL/TLS connection failed. Please check:\n"
                           "1. Encryption settings (TLS/SSL) match server requirements\n"
                           "2. Port number is correct for encryption type\n"
                           "3. Server supports the encryption method\n"
                           "Common settings: Port 587 with TLS, Port 465 with SSL")
                
                logger.error(f"SMTP SSL error: {error_msg}")
                return {
                    'success': False,
                    'error': user_msg,
                    'technical_details': error_msg,
                    'retry_suggested': False
                }
                
            except Exception as e:
                error_msg = str(e)
                user_msg = f"Unexpected error during connection test: {error_msg}"
                
                logger.error(f"SMTP test unexpected error: {error_msg}")
                return {
                    'success': False,
                    'error': user_msg,
                    'technical_details': error_msg,
                    'retry_suggested': True
                }
                
            finally:
                if smtp_server:
                    try:
                        smtp_server.quit()
                    except:
                        pass
        
        except EmailServiceError as e:
            return {
                'success': False,
                'error': str(e)
            }
        except Exception as e:
            logger.error(f"Unexpected error in connection test: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def _create_email_message(self, to_emails: List[str], subject: str, 
                            message: str, from_config: Dict[str, Any]) -> MIMEMultipart:
        """
        Create email message with proper headers.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            message: Email body content
            from_config: From email configuration
            
        Returns:
            MIMEMultipart email message
        """
        msg = MIMEMultipart()
        msg['From'] = formataddr((from_config['from_name'], from_config['from_email']))
        msg['To'] = ', '.join(to_emails)
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(message, 'plain', 'utf-8'))
        
        return msg
    
    def send_email(self, to_emails: List[str], subject: str, message: str,
                   sender_user=None, template_used=None, timeout: int = 30) -> Dict[str, Any]:
        """
        Send email to a list of recipients with comprehensive error handling.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            message: Email body content
            sender_user: User who is sending the email (for audit trail)
            template_used: EmailTemplate instance if template was used
            timeout: SMTP connection timeout in seconds
            
        Returns:
            Dictionary with sending results and detailed error information
        """
        if not to_emails:
            return {
                'success': False,
                'error': 'No recipients specified. Please select at least one recipient.',
                'error_type': 'validation'
            }
        
        # Validate email addresses before sending
        invalid_emails = []
        valid_emails = []
        
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        
        for email in to_emails:
            try:
                validate_email(email.strip())
                valid_emails.append(email.strip())
            except ValidationError:
                invalid_emails.append(email)
        
        if invalid_emails:
            return {
                'success': False,
                'error': f'Invalid email addresses found: {", ".join(invalid_emails)}. Please correct these addresses and try again.',
                'invalid_emails': invalid_emails,
                'error_type': 'validation'
            }
        
        if not valid_emails:
            return {
                'success': False,
                'error': 'No valid email addresses found after validation.',
                'error_type': 'validation'
            }
        
        # Validate subject and message
        if not subject or not subject.strip():
            return {
                'success': False,
                'error': 'Email subject is required. Please enter a subject line.',
                'error_type': 'validation'
            }
        
        if not message or not message.strip():
            return {
                'success': False,
                'error': 'Email message is required. Please enter email content.',
                'error_type': 'validation'
            }
        
        # Initialize history outside try block to avoid variable scope issues
        history = None
        
        try:
            # Get SMTP configuration
            config = self._get_smtp_config()
            self._validate_smtp_config(config)
            
            # Create email history record
            if sender_user:
                history = EmailHistory.objects.create(
                    sender=sender_user,
                    subject=subject.strip(),
                    body=message.strip(),
                    template_used=template_used,
                    recipient_count=len(valid_emails),
                    status='sending'
                )
            
            # Send emails
            sent_count = 0
            failed_count = 0
            failed_recipients = []
            
            smtp_server = None
            try:
                # Create SMTP connection with timeout
                if config['use_ssl']:
                    context = ssl.create_default_context()
                    smtp_server = smtplib.SMTP_SSL(
                        config['smtp_host'], 
                        config['smtp_port'], 
                        context=context,
                        timeout=timeout
                    )
                else:
                    smtp_server = smtplib.SMTP(
                        config['smtp_host'], 
                        config['smtp_port'],
                        timeout=timeout
                    )
                    if config['use_tls']:
                        smtp_server.starttls(context=ssl.create_default_context())
                
                # Authenticate
                smtp_server.login(config['smtp_username'], config['smtp_password'])
                
                # Send to each recipient
                for email in valid_emails:
                    try:
                        # Create individual message
                        msg = self._create_email_message([email], subject.strip(), message.strip(), config)
                        
                        # Send email
                        smtp_server.send_message(msg)
                        sent_count += 1
                        
                        # Create delivery record
                        if history:
                            EmailDelivery.objects.create(
                                email_history=history,
                                recipient_email=email,
                                delivery_status='sent',
                                sent_at=timezone.now()
                            )
                        
                        logger.info(f"Email sent successfully to {email}")
                        
                    except smtplib.SMTPRecipientsRefused as e:
                        error_msg = f"Recipient refused: {str(e)}"
                        failed_count += 1
                        failed_recipients.append({
                            'email': email, 
                            'error': error_msg,
                            'error_type': 'recipient_refused'
                        })
                        
                        # Create failed delivery record
                        if history:
                            EmailDelivery.objects.create(
                                email_history=history,
                                recipient_email=email,
                                delivery_status='failed',
                                error_message=error_msg
                            )
                        
                        logger.error(f"Recipient refused for {email}: {error_msg}")
                        
                    except smtplib.SMTPDataError as e:
                        error_msg = f"SMTP data error: {str(e)}"
                        failed_count += 1
                        failed_recipients.append({
                            'email': email, 
                            'error': error_msg,
                            'error_type': 'smtp_data_error'
                        })
                        
                        # Create failed delivery record
                        if history:
                            EmailDelivery.objects.create(
                                email_history=history,
                                recipient_email=email,
                                delivery_status='failed',
                                error_message=error_msg
                            )
                        
                        logger.error(f"SMTP data error for {email}: {error_msg}")
                        
                    except Exception as e:
                        error_msg = f"Delivery failed: {str(e)}"
                        failed_count += 1
                        failed_recipients.append({
                            'email': email, 
                            'error': error_msg,
                            'error_type': 'delivery_error'
                        })
                        
                        # Create failed delivery record
                        if history:
                            EmailDelivery.objects.create(
                                email_history=history,
                                recipient_email=email,
                                delivery_status='failed',
                                error_message=error_msg
                            )
                        
                        logger.error(f"Failed to send email to {email}: {error_msg}")
                
                smtp_server.quit()
                
            except smtplib.SMTPAuthenticationError as e:
                error_msg = "SMTP authentication failed during sending. Please check your credentials."
                if smtp_server:
                    try:
                        smtp_server.quit()
                    except:
                        pass
                raise EmailServiceError(error_msg)
                
            except socket.timeout as e:
                error_msg = f"Connection timed out after {timeout} seconds during email sending."
                if smtp_server:
                    try:
                        smtp_server.quit()
                    except:
                        pass
                raise EmailServiceError(error_msg)
                
            except Exception as e:
                if smtp_server:
                    try:
                        smtp_server.quit()
                    except:
                        pass
                raise e
            
            # Update history record
            if history:
                history.success_count = sent_count
                history.failure_count = failed_count
                history.status = 'completed' if failed_count == 0 else 'partial_failure'
                history.save()
            
            result = {
                'success': True,
                'sent_count': sent_count,
                'failed_count': failed_count,
                'total_count': len(valid_emails),
                'message': f'Email sending completed: {sent_count} sent, {failed_count} failed'
            }
            
            if failed_recipients:
                result['failed_recipients'] = failed_recipients
                result['retry_suggested'] = any(
                    fr.get('error_type') in ['delivery_error', 'smtp_data_error'] 
                    for fr in failed_recipients
                )
            
            logger.info(f"Email sending completed: {sent_count} sent, {failed_count} failed")
            return result
            
        except EmailServiceError as e:
            # Update history record on service error
            if history:
                history.status = 'failed'
                history.error_message = str(e)
                history.save()
            
            logger.error(f"Email service error: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'service_error',
                'retry_suggested': True
            }
            
        except Exception as e:
            # Update history record on unexpected error
            if history:
                history.status = 'failed'
                history.error_message = str(e)
                history.save()
            
            logger.error(f"Unexpected error in email sending: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error occurred: {str(e)}',
                'error_type': 'unexpected_error',
                'retry_suggested': True
            }
    
    def send_bulk_email(self, to_emails: List[str], subject: str, message: str,
                       sender_user=None, template_used=None, operation_id: str = None,
                       progress_callback=None) -> Dict[str, Any]:
        """
        Send email to a large list of recipients with performance optimizations.
        
        Features:
        - Automatic batch size optimization based on provider and recipient count
        - Rate limiting compliance with provider-specific limits
        - Connection pooling for improved performance
        - Operation cancellation support
        - Progress tracking and callbacks
        - Database transaction optimization
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            message: Email body content
            sender_user: User who is sending the email
            template_used: EmailTemplate instance if template was used
            operation_id: Unique operation ID for cancellation support
            progress_callback: Callback function for progress updates
            
        Returns:
            Dictionary with sending results and detailed error information
        """
        if not to_emails:
            return {
                'success': False,
                'error': 'No recipients specified. Please select at least one recipient.',
                'error_type': 'validation'
            }
        
        # Generate operation ID if not provided
        if not operation_id:
            operation_id = f"bulk_email_{int(time.time())}"
        
        # Validate email addresses first
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        
        invalid_emails = []
        valid_emails = []
        
        for email in to_emails:
            try:
                validate_email(email.strip())
                valid_emails.append(email.strip())
            except ValidationError:
                invalid_emails.append(email)
        
        if invalid_emails:
            return {
                'success': False,
                'error': f'Invalid email addresses found: {", ".join(invalid_emails[:10])}{"..." if len(invalid_emails) > 10 else ""}. Please correct these addresses and try again.',
                'invalid_emails': invalid_emails,
                'error_type': 'validation'
            }
        
        if not valid_emails:
            return {
                'success': False,
                'error': 'No valid email addresses found after validation.',
                'error_type': 'validation'
            }
        
        # Validate subject and message
        if not subject or not subject.strip():
            return {
                'success': False,
                'error': 'Email subject is required. Please enter a subject line.',
                'error_type': 'validation'
            }
        
        if not message or not message.strip():
            return {
                'success': False,
                'error': 'Email message is required. Please enter email content.',
                'error_type': 'validation'
            }
        
        try:
            # Get SMTP configuration and determine provider
            config = self._get_smtp_config()
            self._validate_smtp_config(config)
            
            # Determine provider for rate limiting
            provider = 'custom'
            host_lower = config['smtp_host'].lower()
            if 'gmail' in host_lower:
                provider = 'gmail'
            elif 'outlook' in host_lower or 'office365' in host_lower:
                provider = 'outlook'
            elif 'yahoo' in host_lower:
                provider = 'yahoo'
            
            # Calculate optimal batch size and delay
            batch_size = self.batch_processor.calculate_optimal_batch_size(len(valid_emails), provider)
            batch_delay = self.batch_processor.calculate_batch_delay(batch_size, provider)
            
            logger.info(f"Starting optimized bulk email sending to {len(valid_emails)} recipients")
            logger.info(f"Using batch size: {batch_size}, delay: {batch_delay}s, provider: {provider}")
            
            # Start operation tracking
            operation = self.operation_manager.start_operation(operation_id, len(valid_emails))
            if progress_callback:
                operation['progress_callback'] = progress_callback
            
            # Initialize counters
            total_sent = 0
            total_failed = 0
            all_failed_recipients = []
            batch_results = []
            
            # Calculate total batches
            total_batches = (len(valid_emails) + batch_size - 1) // batch_size
            
            # Create email history record with transaction optimization
            history = None
            if sender_user:
                with transaction.atomic():
                    history = EmailHistory.objects.create(
                        sender=sender_user,
                        subject=subject.strip(),
                        body=message.strip(),
                        template_used=template_used,
                        recipient_count=len(valid_emails),
                        status='sending'
                    )
            
            # Process emails in optimized batches
            smtp_server = None
            try:
                # Get pooled SMTP connection
                smtp_server = self._get_or_create_smtp_connection(config)
                
                for batch_num in range(total_batches):
                    # Check for cancellation
                    if self.operation_manager.is_cancelled(operation_id):
                        logger.info(f"Bulk email operation {operation_id} was cancelled")
                        break
                    
                    start_idx = batch_num * batch_size
                    end_idx = min(start_idx + batch_size, len(valid_emails))
                    batch = valid_emails[start_idx:end_idx]
                    
                    # Check rate limits before processing batch
                    can_send, rate_limit_reason = self.rate_limiter.can_send_email(provider, len(batch))
                    if not can_send:
                        wait_time = self.rate_limiter.get_wait_time(provider)
                        if wait_time > 0:
                            logger.info(f"Rate limit reached, waiting {wait_time}s: {rate_limit_reason}")
                            time.sleep(wait_time)
                            # Re-check after waiting
                            can_send, rate_limit_reason = self.rate_limiter.can_send_email(provider, len(batch))
                    
                    if not can_send:
                        # Skip this batch due to rate limits
                        logger.warning(f"Skipping batch {batch_num + 1} due to rate limits: {rate_limit_reason}")
                        total_failed += len(batch)
                        all_failed_recipients.extend([
                            {'email': email, 'error': rate_limit_reason, 'error_type': 'rate_limit'}
                            for email in batch
                        ])
                        continue
                    
                    logger.info(f"Processing batch {batch_num + 1}/{total_batches}: {len(batch)} recipients")
                    
                    # Process batch with optimized delivery record creation
                    batch_sent = 0
                    batch_failed = 0
                    batch_failed_recipients = []
                    delivery_records = []
                    
                    for email in batch:
                        try:
                            # Create individual message
                            msg = self._create_email_message([email], subject.strip(), message.strip(), config)
                            
                            # Send email
                            smtp_server.send_message(msg)
                            batch_sent += 1
                            
                            # Prepare delivery record for batch creation
                            if history:
                                delivery_records.append(EmailDelivery(
                                    email_history=history,
                                    recipient_email=email,
                                    delivery_status='sent',
                                    sent_at=timezone.now()
                                ))
                            
                        except Exception as e:
                            batch_failed += 1
                            error_msg = str(e)
                            batch_failed_recipients.append({
                                'email': email,
                                'error': error_msg,
                                'error_type': 'delivery_error'
                            })
                            
                            # Prepare failed delivery record
                            if history:
                                delivery_records.append(EmailDelivery(
                                    email_history=history,
                                    recipient_email=email,
                                    delivery_status='failed',
                                    error_message=error_msg,
                                    sent_at=timezone.now()
                                ))
                    
                    # Batch create delivery records for performance
                    if delivery_records:
                        with transaction.atomic():
                            EmailDelivery.objects.bulk_create(delivery_records, batch_size=100)
                    
                    # Record sent emails for rate limiting
                    self.rate_limiter.record_sent_emails(provider, batch_sent)
                    
                    # Update totals
                    total_sent += batch_sent
                    total_failed += batch_failed
                    all_failed_recipients.extend(batch_failed_recipients)
                    
                    # Record batch results
                    batch_results.append({
                        'batch_number': batch_num + 1,
                        'sent': batch_sent,
                        'failed': batch_failed,
                        'rate_limited': not can_send
                    })
                    
                    # Update operation progress
                    processed = total_sent + total_failed
                    self.operation_manager.update_progress(operation_id, processed, total_sent, total_failed)
                    
                    # Progress callback
                    if progress_callback:
                        progress_callback({
                            'processed': processed,
                            'total': len(valid_emails),
                            'sent': total_sent,
                            'failed': total_failed,
                            'progress_percent': (processed / len(valid_emails)) * 100
                        })
                    
                    # Delay between batches (except for the last batch)
                    if batch_num + 1 < total_batches and not self.operation_manager.is_cancelled(operation_id):
                        time.sleep(batch_delay)
                    
                    # Progress logging
                    progress_percent = ((batch_num + 1) / total_batches) * 100
                    logger.info(f"Bulk email progress: {progress_percent:.1f}% complete ({batch_num + 1}/{total_batches} batches)")
                
            except Exception as e:
                logger.error(f"Critical error in bulk email sending: {str(e)}")
                return {
                    'success': False,
                    'error': f'Critical error during bulk sending: {str(e)}',
                    'error_type': 'critical_error',
                    'sent_count': total_sent,
                    'failed_count': total_failed + (len(valid_emails) - total_sent - total_failed),
                    'total_count': len(valid_emails),
                    'batch_results': batch_results,
                    'operation_id': operation_id
                }
            
            finally:
                # Don't close connection here - let connection pool manage it
                pass
            
            # Update email history status
            if history:
                with transaction.atomic():
                    history.success_count = total_sent
                    history.failure_count = total_failed
                    history.status = 'completed' if total_failed == 0 else ('partial' if total_sent > 0 else 'failed')
                    history.save()
            
            # Complete operation
            self.operation_manager.complete_operation(operation_id)
            
            # Calculate success rate
            success_rate = (total_sent / len(valid_emails)) * 100 if valid_emails else 0
            
            result = {
                'success': True,
                'sent_count': total_sent,
                'failed_count': total_failed,
                'total_count': len(valid_emails),
                'success_rate': round(success_rate, 2),
                'batch_results': batch_results,
                'operation_id': operation_id,
                'performance_stats': {
                    'batch_size_used': batch_size,
                    'batch_delay_used': batch_delay,
                    'provider': provider,
                    'total_batches': total_batches,
                    'connection_pooled': True
                },
                'message': f'Optimized bulk email sending completed: {total_sent} sent, {total_failed} failed ({success_rate:.1f}% success rate)'
            }
            
            if all_failed_recipients:
                result['failed_recipients'] = all_failed_recipients
                result['retry_suggested'] = any(
                    fr.get('error_type') in ['delivery_error', 'smtp_data_error', 'service_error'] 
                    for fr in all_failed_recipients
                )
            
            logger.info(f"Optimized bulk email sending completed: {total_sent} sent, {total_failed} failed ({success_rate:.1f}% success rate)")
            return result
            
        except Exception as e:
            logger.error(f"Unexpected error in bulk email sending: {str(e)}")
            return {
                'success': False,
                'error': f'Unexpected error: {str(e)}',
                'error_type': 'unexpected_error',
                'operation_id': operation_id
            }
    
    def cancel_bulk_operation(self, operation_id: str) -> Dict[str, Any]:
        """
        Cancel a bulk email operation.
        
        Args:
            operation_id: Operation ID to cancel
            
        Returns:
            Dictionary with cancellation result
        """
        success = self.operation_manager.cancel_operation(operation_id)
        
        if success:
            logger.info(f"Bulk email operation {operation_id} cancelled successfully")
            return {
                'success': True,
                'message': f'Operation {operation_id} cancelled successfully'
            }
        else:
            return {
                'success': False,
                'error': f'Operation {operation_id} not found or already completed'
            }
    
    def get_operation_status(self, operation_id: str) -> Dict[str, Any]:
        """
        Get status of a bulk email operation.
        
        Args:
            operation_id: Operation ID to check
            
        Returns:
            Dictionary with operation status
        """
        status = self.operation_manager.get_operation_status(operation_id)
        
        if status:
            return {
                'success': True,
                'operation_status': status
            }
        else:
            return {
                'success': False,
                'error': f'Operation {operation_id} not found'
            }
        """
        Send email to a large list of recipients in batches with comprehensive error handling.
        
        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            message: Email body content
            sender_user: User who is sending the email
            template_used: EmailTemplate instance if template was used
            batch_size: Number of emails to send per batch (default: 50)
            delay_between_batches: Delay in seconds between batches (default: 1.0)
            max_retries: Maximum number of retries for failed batches (default: 3)
            
        Returns:
            Dictionary with sending results and detailed error information
        """
        if not to_emails:
            return {
                'success': False,
                'error': 'No recipients specified. Please select at least one recipient.',
                'error_type': 'validation'
            }
        
        # Validate inputs
        if batch_size <= 0:
            batch_size = 50
        if delay_between_batches < 0:
            delay_between_batches = 1.0
        if max_retries < 0:
            max_retries = 3
        
        # Validate email addresses first
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        
        invalid_emails = []
        valid_emails = []
        
        for email in to_emails:
            try:
                validate_email(email.strip())
                valid_emails.append(email.strip())
            except ValidationError:
                invalid_emails.append(email)
        
        if invalid_emails:
            return {
                'success': False,
                'error': f'Invalid email addresses found: {", ".join(invalid_emails[:10])}{"..." if len(invalid_emails) > 10 else ""}. Please correct these addresses and try again.',
                'invalid_emails': invalid_emails,
                'error_type': 'validation'
            }
        
        if not valid_emails:
            return {
                'success': False,
                'error': 'No valid email addresses found after validation.',
                'error_type': 'validation'
            }
        
        # Validate subject and message
        if not subject or not subject.strip():
            return {
                'success': False,
                'error': 'Email subject is required. Please enter a subject line.',
                'error_type': 'validation'
            }
        
        if not message or not message.strip():
            return {
                'success': False,
                'error': 'Email message is required. Please enter email content.',
                'error_type': 'validation'
            }
        
        logger.info(f"Starting bulk email sending to {len(valid_emails)} recipients in batches of {batch_size}")
        
        total_sent = 0
        total_failed = 0
        all_failed_recipients = []
        batch_results = []
        
        # Calculate total batches
        total_batches = (len(valid_emails) + batch_size - 1) // batch_size
        
        try:
            # Process emails in batches
            for batch_num in range(total_batches):
                start_idx = batch_num * batch_size
                end_idx = min(start_idx + batch_size, len(valid_emails))
                batch = valid_emails[start_idx:end_idx]
                
                logger.info(f"Processing batch {batch_num + 1}/{total_batches}: {len(batch)} recipients")
                
                # Retry logic for each batch
                batch_success = False
                batch_attempts = 0
                
                while not batch_success and batch_attempts < max_retries:
                    batch_attempts += 1
                    
                    try:
                        # Send batch
                        result = self.send_email(
                            to_emails=batch,
                            subject=subject.strip(),
                            message=message.strip(),
                            sender_user=sender_user,
                            template_used=template_used
                        )
                        
                        if result['success']:
                            batch_success = True
                            total_sent += result['sent_count']
                            total_failed += result['failed_count']
                            
                            batch_results.append({
                                'batch_number': batch_num + 1,
                                'sent': result['sent_count'],
                                'failed': result['failed_count'],
                                'attempts': batch_attempts
                            })
                            
                            if 'failed_recipients' in result:
                                all_failed_recipients.extend(result['failed_recipients'])
                                
                        else:
                            # Check if this is a retryable error
                            error_type = result.get('error_type', 'unknown')
                            if error_type in ['validation'] or batch_attempts >= max_retries:
                                # Don't retry validation errors or if max retries reached
                                batch_success = True  # Stop retrying
                                total_failed += len(batch)
                                
                                batch_results.append({
                                    'batch_number': batch_num + 1,
                                    'sent': 0,
                                    'failed': len(batch),
                                    'attempts': batch_attempts,
                                    'error': result.get('error', 'Batch failed')
                                })
                                
                                all_failed_recipients.extend([
                                    {
                                        'email': email, 
                                        'error': result.get('error', 'Batch failed'),
                                        'error_type': error_type
                                    }
                                    for email in batch
                                ])
                            else:
                                # Wait before retry
                                if batch_attempts < max_retries:
                                    retry_delay = delay_between_batches * batch_attempts
                                    logger.warning(f"Batch {batch_num + 1} failed (attempt {batch_attempts}), retrying in {retry_delay}s: {result.get('error', 'Unknown error')}")
                                    time.sleep(retry_delay)
                                
                    except Exception as e:
                        logger.error(f"Unexpected error in batch {batch_num + 1}, attempt {batch_attempts}: {str(e)}")
                        
                        if batch_attempts >= max_retries:
                            batch_success = True  # Stop retrying
                            total_failed += len(batch)
                            
                            batch_results.append({
                                'batch_number': batch_num + 1,
                                'sent': 0,
                                'failed': len(batch),
                                'attempts': batch_attempts,
                                'error': f'Unexpected error: {str(e)}'
                            })
                            
                            all_failed_recipients.extend([
                                {
                                    'email': email, 
                                    'error': f'Unexpected error: {str(e)}',
                                    'error_type': 'unexpected_error'
                                }
                                for email in batch
                            ])
                        else:
                            # Wait before retry
                            retry_delay = delay_between_batches * batch_attempts
                            time.sleep(retry_delay)
                
                # Delay between batches (except for the last batch)
                if batch_num + 1 < total_batches:
                    time.sleep(delay_between_batches)
                    
                # Progress logging
                progress_percent = ((batch_num + 1) / total_batches) * 100
                logger.info(f"Bulk email progress: {progress_percent:.1f}% complete ({batch_num + 1}/{total_batches} batches)")
        
        except Exception as e:
            logger.error(f"Critical error in bulk email sending: {str(e)}")
            return {
                'success': False,
                'error': f'Critical error during bulk sending: {str(e)}',
                'error_type': 'critical_error',
                'sent_count': total_sent,
                'failed_count': total_failed + (len(valid_emails) - total_sent - total_failed),
                'total_count': len(valid_emails),
                'batch_results': batch_results
            }
        
        # Calculate success rate
        success_rate = (total_sent / len(valid_emails)) * 100 if valid_emails else 0
        
        result = {
            'success': True,
            'sent_count': total_sent,
            'failed_count': total_failed,
            'total_count': len(valid_emails),
            'success_rate': round(success_rate, 2),
            'batch_results': batch_results,
            'message': f'Bulk email sending completed: {total_sent} sent, {total_failed} failed ({success_rate:.1f}% success rate)'
        }
        
        if all_failed_recipients:
            result['failed_recipients'] = all_failed_recipients
            result['retry_suggested'] = any(
                fr.get('error_type') in ['delivery_error', 'smtp_data_error', 'service_error'] 
                for fr in all_failed_recipients
            )
        
        logger.info(f"Bulk email sending completed: {total_sent} sent, {total_failed} failed ({success_rate:.1f}% success rate)")
        return result
    
    def get_provider_config(self, provider: str) -> Optional[Dict[str, Any]]:
        """
        Get predefined configuration for a specific email provider.
        
        Args:
            provider: Provider name (gmail, outlook, yahoo, office365)
            
        Returns:
            Configuration dictionary or None if provider not found
        """
        return self.PROVIDER_CONFIGS.get(provider.lower())
    
    def cleanup_connections(self):
        """
        Clean up SMTP connections and resources.
        Should be called when shutting down or periodically for maintenance.
        """
        self._close_smtp_connections()
        logger.info("Email service connections cleaned up")
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics for monitoring and optimization.
        
        Returns:
            Dictionary with performance metrics
        """
        with self._connection_pool_lock:
            active_connections = len(self._connection_pool)
        
        # Get rate limiter stats
        rate_stats = {}
        for provider in self.rate_limiter.rate_limits.keys():
            with self.rate_limiter.lock:
                minute_count = len(self.rate_limiter.counters[provider]['minute'])
                hour_count = len(self.rate_limiter.counters[provider]['hour'])
                rate_stats[provider] = {
                    'emails_sent_last_minute': minute_count,
                    'emails_sent_last_hour': hour_count,
                    'limit_per_minute': self.rate_limiter.rate_limits[provider]['emails_per_minute'],
                    'limit_per_hour': self.rate_limiter.rate_limits[provider]['emails_per_hour']
                }
        
        # Get operation stats
        with self.operation_manager.lock:
            active_operations = len([
                op for op in self.operation_manager.operations.values() 
                if op['status'] == 'running'
            ])
            total_operations = len(self.operation_manager.operations)
        
        return {
            'connection_pool': {
                'active_connections': active_connections,
                'max_pool_size': 10  # Could be configurable
            },
            'rate_limiting': rate_stats,
            'operations': {
                'active_operations': active_operations,
                'total_operations': total_operations
            },
            'performance_features': {
                'connection_pooling': True,
                'rate_limiting': True,
                'batch_optimization': True,
                'operation_cancellation': True,
                'database_optimization': True
            }
        }
    
    def get_supported_providers(self) -> List[str]:
        """
        Get list of supported email providers.
        
        Returns:
            List of provider names
        """
        return list(self.PROVIDER_CONFIGS.keys())


# Global email service instance
email_service = EmailService()