"""
Email History Service for the Email Management System

This service handles email history tracking, delivery status updates, and audit trail management.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from .email_models import EmailHistory, EmailDelivery, EmailTemplate
from .models import Student

logger = logging.getLogger(__name__)

# Audit logger for administrative actions
audit_logger = logging.getLogger('email_audit')

User = get_user_model()


class EmailHistoryServiceError(Exception):
    """Base exception for email history service errors"""
    pass


class EmailHistoryService:
    """
    Service for managing email history, delivery tracking, and audit trails.
    """
    
    def __init__(self):
        """Initialize the email history service"""
        pass
    
    def _log_admin_action(self, action: str, user, details: Dict[str, Any] = None, 
                         sensitive_data: List[str] = None) -> None:
        """
        Log administrative actions for audit trail.
        
        Args:
            action: Action being performed
            user: User performing the action
            details: Additional details about the action
            sensitive_data: List of sensitive field names to exclude from logs
        """
        try:
            # Prepare log data
            log_data = {
                'action': action,
                'user_id': user.id if user else None,
                'username': user.username if user else 'system',
                'timestamp': timezone.now().isoformat(),
            }
            
            # Add details, excluding sensitive data
            if details:
                filtered_details = details.copy()
                if sensitive_data:
                    for field in sensitive_data:
                        if field in filtered_details:
                            filtered_details[field] = '[REDACTED]'
                log_data['details'] = filtered_details
            
            # Log the action
            audit_logger.info(f"Email Admin Action: {action}", extra=log_data)
            
        except Exception as e:
            logger.error(f"Failed to log admin action: {str(e)}")
    
    def save_email_record(self, sender_user, subject: str, body: str, 
                         recipients: List[str], template_used: Optional[EmailTemplate] = None) -> EmailHistory:
        """
        Create a new email history record.
        
        Args:
            sender_user: User who sent the email
            subject: Email subject
            body: Email body content
            recipients: List of recipient email addresses
            template_used: Optional EmailTemplate instance
            
        Returns:
            Created EmailHistory object
        """
        try:
            history = EmailHistory.objects.create(
                sender=sender_user,
                subject=subject,
                body=body,
                template_used=template_used,
                recipient_count=len(recipients),
                status='sending'
            )
            
            # Create delivery records for each recipient
            delivery_records = []
            for email in recipients:
                # Try to find associated student
                student = None
                try:
                    student = Student.objects.filter(user__email=email).first()
                except:
                    pass
                
                delivery_records.append(EmailDelivery(
                    email_history=history,
                    recipient_email=email,
                    recipient_name=student.full_name if student else '',
                    student=student,
                    delivery_status='pending'
                ))
            
            # Bulk create delivery records
            EmailDelivery.objects.bulk_create(delivery_records)
            
            # Log administrative action
            self._log_admin_action(
                action='email_record_created',
                user=sender_user,
                details={
                    'email_id': history.id,
                    'subject': subject,
                    'recipient_count': len(recipients),
                    'template_used': template_used.name if template_used else None
                },
                sensitive_data=['body']  # Don't log email body content
            )
            
            logger.info(f"Created email history record {history.id} with {len(recipients)} recipients")
            return history
            
        except Exception as e:
            logger.error(f"Failed to save email record: {str(e)}")
            raise EmailHistoryServiceError(f"Failed to save email record: {str(e)}")
    
    def update_delivery_status(self, record_id: int, recipient_email: str, 
                             status: str, error_message: str = "") -> bool:
        """
        Update delivery status for a specific recipient.
        
        Args:
            record_id: EmailHistory record ID
            recipient_email: Recipient email address
            status: New delivery status
            error_message: Optional error message
            
        Returns:
            True if successful
        """
        try:
            delivery = EmailDelivery.objects.get(
                email_history_id=record_id,
                recipient_email=recipient_email
            )
            
            old_status = delivery.delivery_status
            delivery.delivery_status = status
            delivery.error_message = error_message
            
            if status == 'sent':
                delivery.sent_at = timezone.now()
            elif status == 'delivered':
                delivery.delivered_at = timezone.now()
                if not delivery.sent_at:
                    delivery.sent_at = timezone.now()
            
            delivery.save()
            
            # Update parent history record counts
            self._update_history_counts(record_id)
            
            # Log delivery status update
            self._log_admin_action(
                action='delivery_status_updated',
                user=None,  # System action
                details={
                    'email_id': record_id,
                    'recipient_email': recipient_email,
                    'old_status': old_status,
                    'new_status': status,
                    'has_error': bool(error_message)
                }
            )
            
            logger.info(f"Updated delivery status for {recipient_email}: {old_status} -> {status}")
            return True
            
        except EmailDelivery.DoesNotExist:
            logger.error(f"Delivery record not found: {record_id}, {recipient_email}")
            return False
        except Exception as e:
            logger.error(f"Failed to update delivery status: {str(e)}")
            raise EmailHistoryServiceError(f"Failed to update delivery status: {str(e)}")
    
    def _update_history_counts(self, record_id: int) -> None:
        """
        Update success and failure counts for an email history record.
        
        Args:
            record_id: EmailHistory record ID
        """
        try:
            history = EmailHistory.objects.get(id=record_id)
            
            # Count successful and failed deliveries
            deliveries = EmailDelivery.objects.filter(email_history=history)
            success_count = deliveries.filter(
                delivery_status__in=['sent', 'delivered']
            ).count()
            failure_count = deliveries.filter(
                delivery_status__in=['failed', 'bounced']
            ).count()
            
            # Update history record
            history.success_count = success_count
            history.failure_count = failure_count
            
            # Update overall status
            if failure_count == 0 and success_count == history.recipient_count:
                history.status = 'completed'
            elif failure_count > 0 and success_count == 0:
                history.status = 'failed'
            elif success_count > 0:
                history.status = 'completed'  # Partial success is still completed
            
            history.save()
            
        except Exception as e:
            logger.error(f"Failed to update history counts: {str(e)}")
    
    def get_email_history(self, filters: Optional[Dict[str, Any]] = None, 
                         page: int = 1, page_size: int = 20, 
                         requesting_user=None) -> Dict[str, Any]:
        """
        Retrieve email history with optional filtering and pagination.
        
        Args:
            filters: Optional filtering criteria
            page: Page number (1-based)
            page_size: Number of records per page
            requesting_user: User requesting the history (for audit logging)
            
        Returns:
            Dictionary with paginated history results
        """
        try:
            # Log administrative action
            if requesting_user:
                self._log_admin_action(
                    action='email_history_accessed',
                    user=requesting_user,
                    details={
                        'filters': filters,
                        'page': page,
                        'page_size': page_size
                    }
                )
            queryset = EmailHistory.objects.select_related('sender', 'template_used').order_by('-sent_at')
            
            # Apply filters
            if filters:
                # Date range filter
                if filters.get('start_date'):
                    start_date = datetime.fromisoformat(filters['start_date'].replace('Z', '+00:00'))
                    queryset = queryset.filter(sent_at__gte=start_date)
                
                if filters.get('end_date'):
                    end_date = datetime.fromisoformat(filters['end_date'].replace('Z', '+00:00'))
                    queryset = queryset.filter(sent_at__lte=end_date)
                
                # Sender filter
                if filters.get('sender_id'):
                    queryset = queryset.filter(sender_id=filters['sender_id'])
                
                # Status filter
                if filters.get('status'):
                    queryset = queryset.filter(status=filters['status'])
                
                # Template filter
                if filters.get('template_id'):
                    queryset = queryset.filter(template_used_id=filters['template_id'])
                
                # Subject search
                if filters.get('subject_search'):
                    queryset = queryset.filter(subject__icontains=filters['subject_search'])
            
            # Paginate results
            paginator = Paginator(queryset, page_size)
            page_obj = paginator.get_page(page)
            
            # Serialize results
            history_list = []
            for history in page_obj:
                history_list.append({
                    'id': history.id,
                    'sender': {
                        'id': history.sender.id,
                        'username': history.sender.username,
                        'email': getattr(history.sender, 'email', ''),
                        'full_name': getattr(history.sender, 'get_full_name', lambda: '')()
                    },
                    'subject': history.subject,
                    'template_used': {
                        'id': history.template_used.id,
                        'name': history.template_used.name,
                        'category': history.template_used.category
                    } if history.template_used else None,
                    'recipient_count': history.recipient_count,
                    'success_count': history.success_count,
                    'failure_count': history.failure_count,
                    'success_rate': history.success_rate,
                    'status': history.status,
                    'sent_at': history.sent_at.isoformat() if history.sent_at else None,
                    'error_message': history.error_message
                })
            
            return {
                'results': history_list,
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_pages': paginator.num_pages,
                    'total_count': paginator.count,
                    'has_next': page_obj.has_next(),
                    'has_previous': page_obj.has_previous()
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get email history: {str(e)}")
            raise EmailHistoryServiceError(f"Failed to get email history: {str(e)}")
    
    def get_delivery_details(self, record_id: int, requesting_user=None) -> List[Dict[str, Any]]:
        """
        Get detailed delivery information for a specific email.
        
        Args:
            record_id: EmailHistory record ID
            requesting_user: User requesting the details (for audit logging)
            
        Returns:
            List of delivery detail dictionaries
        """
        try:
            # Log administrative action
            if requesting_user:
                self._log_admin_action(
                    action='delivery_details_accessed',
                    user=requesting_user,
                    details={'email_id': record_id}
                )
            deliveries = EmailDelivery.objects.filter(
                email_history_id=record_id
            ).select_related('student').order_by('recipient_email')
            
            delivery_list = []
            for delivery in deliveries:
                delivery_list.append({
                    'id': delivery.id,
                    'recipient_email': delivery.recipient_email,
                    'recipient_name': delivery.recipient_name,
                    'student': {
                        'id': delivery.student.id,
                        'full_name': delivery.student.full_name,
                        'matric_number': delivery.student.matric_number,
                        'department': delivery.student.department.name
                    } if delivery.student else None,
                    'delivery_status': delivery.delivery_status,
                    'error_message': delivery.error_message,
                    'sent_at': delivery.sent_at.isoformat() if delivery.sent_at else None,
                    'delivered_at': delivery.delivered_at.isoformat() if delivery.delivered_at else None,
                    'created_at': delivery.created_at.isoformat()
                })
            
            return delivery_list
            
        except Exception as e:
            logger.error(f"Failed to get delivery details: {str(e)}")
            raise EmailHistoryServiceError(f"Failed to get delivery details: {str(e)}")
    
    def get_email_statistics(self, days: int = 30) -> Dict[str, Any]:
        """
        Get email statistics for the specified number of days.
        
        Args:
            days: Number of days to include in statistics
            
        Returns:
            Dictionary with email statistics
        """
        try:
            start_date = timezone.now() - timedelta(days=days)
            
            # Basic counts
            total_emails = EmailHistory.objects.filter(sent_at__gte=start_date).count()
            total_recipients = EmailHistory.objects.filter(
                sent_at__gte=start_date
            ).aggregate(
                total=Count('recipient_count')
            )['total'] or 0
            
            # Success/failure statistics
            success_stats = EmailHistory.objects.filter(
                sent_at__gte=start_date
            ).aggregate(
                total_success=Count('success_count'),
                total_failure=Count('failure_count'),
                avg_success_rate=Avg('success_count')
            )
            
            # Status breakdown
            status_breakdown = EmailHistory.objects.filter(
                sent_at__gte=start_date
            ).values('status').annotate(count=Count('id'))
            
            # Template usage
            template_usage = EmailHistory.objects.filter(
                sent_at__gte=start_date,
                template_used__isnull=False
            ).values(
                'template_used__name',
                'template_used__category'
            ).annotate(count=Count('id')).order_by('-count')
            
            # Top senders
            top_senders = EmailHistory.objects.filter(
                sent_at__gte=start_date
            ).values(
                'sender__username',
                'sender__email'
            ).annotate(
                email_count=Count('id'),
                recipient_count=Count('recipient_count')
            ).order_by('-email_count')[:10]
            
            return {
                'period_days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat(),
                'total_emails': total_emails,
                'total_recipients': total_recipients,
                'success_stats': success_stats,
                'status_breakdown': list(status_breakdown),
                'template_usage': list(template_usage),
                'top_senders': list(top_senders)
            }
            
        except Exception as e:
            logger.error(f"Failed to get email statistics: {str(e)}")
            raise EmailHistoryServiceError(f"Failed to get email statistics: {str(e)}")
    
    def delete_old_records(self, days: int = 365, requesting_user=None) -> int:
        """
        Delete email history records older than specified days.
        
        Args:
            days: Number of days to keep records
            requesting_user: User requesting the deletion (for audit logging)
            
        Returns:
            Number of deleted records
        """
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Count records to be deleted for logging
            records_to_delete = EmailHistory.objects.filter(sent_at__lt=cutoff_date).count()
            
            # Log administrative action before deletion
            if requesting_user:
                self._log_admin_action(
                    action='old_records_deleted',
                    user=requesting_user,
                    details={
                        'cutoff_days': days,
                        'cutoff_date': cutoff_date.isoformat(),
                        'records_to_delete': records_to_delete
                    }
                )
            
            # Delete old records (this will cascade to delivery records)
            deleted_count, _ = EmailHistory.objects.filter(
                sent_at__lt=cutoff_date
            ).delete()
            
            logger.info(f"Deleted {deleted_count} email history records older than {days} days")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete old records: {str(e)}")
            raise EmailHistoryServiceError(f"Failed to delete old records: {str(e)}")
    
    def get_delivery_status_summary(self, record_id: int) -> Dict[str, Any]:
        """
        Get a summary of delivery statuses for a specific email.
        
        Args:
            record_id: EmailHistory record ID
            
        Returns:
            Dictionary with delivery status summary
        """
        try:
            history = EmailHistory.objects.get(id=record_id)
            
            # Count by status
            status_counts = EmailDelivery.objects.filter(
                email_history=history
            ).values('delivery_status').annotate(count=Count('id'))
            
            # Convert to dictionary
            status_dict = {item['delivery_status']: item['count'] for item in status_counts}
            
            return {
                'email_id': record_id,
                'total_recipients': history.recipient_count,
                'status_counts': status_dict,
                'success_rate': history.success_rate,
                'overall_status': history.status
            }
            
        except EmailHistory.DoesNotExist:
            raise EmailHistoryServiceError("Email history record not found")
        except Exception as e:
            logger.error(f"Failed to get delivery status summary: {str(e)}")
            raise EmailHistoryServiceError(f"Failed to get delivery status summary: {str(e)}")
    
    def search_email_history(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search email history by subject, sender, or content.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching email history records
        """
        try:
            if not query or len(query.strip()) < 2:
                return []
            
            query = query.strip()
            
            # Search in multiple fields
            search_filter = (
                Q(subject__icontains=query) |
                Q(body__icontains=query) |
                Q(sender__username__icontains=query) |
                Q(sender__email__icontains=query)
            )
            
            results = EmailHistory.objects.filter(
                search_filter
            ).select_related('sender', 'template_used').order_by('-sent_at')[:limit]
            
            # Serialize results
            history_list = []
            for history in results:
                history_list.append({
                    'id': history.id,
                    'subject': history.subject,
                    'sender_name': history.sender.username,
                    'recipient_count': history.recipient_count,
                    'success_rate': history.success_rate,
                    'status': history.status,
                    'sent_at': history.sent_at.isoformat() if history.sent_at else None
                })
            
            return history_list
            
        except Exception as e:
            logger.error(f"Failed to search email history: {str(e)}")
            raise EmailHistoryServiceError(f"Failed to search email history: {str(e)}")
    
    def log_smtp_configuration_change(self, user, old_config: Dict[str, Any], 
                                    new_config: Dict[str, Any]) -> None:
        """
        Log SMTP configuration changes for audit trail.
        
        Args:
            user: User making the configuration change
            old_config: Previous configuration
            new_config: New configuration
        """
        try:
            # Identify changed fields
            changed_fields = []
            for key in new_config:
                if key in old_config and old_config[key] != new_config[key]:
                    changed_fields.append(key)
            
            self._log_admin_action(
                action='smtp_configuration_changed',
                user=user,
                details={
                    'changed_fields': changed_fields,
                    'smtp_host': new_config.get('smtp_host'),
                    'smtp_port': new_config.get('smtp_port'),
                    'use_tls': new_config.get('use_tls'),
                    'use_ssl': new_config.get('use_ssl'),
                    'from_email': new_config.get('from_email')
                },
                sensitive_data=['smtp_password', 'smtp_username']
            )
            
        except Exception as e:
            logger.error(f"Failed to log SMTP configuration change: {str(e)}")
    
    def log_template_action(self, action: str, user, template_id: int, 
                          template_name: str, details: Dict[str, Any] = None) -> None:
        """
        Log email template actions for audit trail.
        
        Args:
            action: Action performed (created, updated, deleted)
            user: User performing the action
            template_id: Template ID
            template_name: Template name
            details: Additional details
        """
        try:
            log_details = {
                'template_id': template_id,
                'template_name': template_name
            }
            
            if details:
                log_details.update(details)
            
            self._log_admin_action(
                action=f'template_{action}',
                user=user,
                details=log_details
            )
            
        except Exception as e:
            logger.error(f"Failed to log template action: {str(e)}")
    
    def log_bulk_email_operation(self, user, operation: str, recipient_count: int,
                               template_used: str = None, success_count: int = None,
                               failure_count: int = None) -> None:
        """
        Log bulk email operations for audit trail.
        
        Args:
            user: User performing the operation
            operation: Operation type (initiated, completed, cancelled)
            recipient_count: Number of recipients
            template_used: Template name if used
            success_count: Number of successful sends
            failure_count: Number of failed sends
        """
        try:
            details = {
                'operation': operation,
                'recipient_count': recipient_count,
                'template_used': template_used
            }
            
            if success_count is not None:
                details['success_count'] = success_count
            if failure_count is not None:
                details['failure_count'] = failure_count
                details['success_rate'] = (success_count / recipient_count * 100) if recipient_count > 0 else 0
            
            self._log_admin_action(
                action='bulk_email_operation',
                user=user,
                details=details
            )
            
        except Exception as e:
            logger.error(f"Failed to log bulk email operation: {str(e)}")
    
    def log_system_maintenance(self, user, action: str, details: Dict[str, Any] = None) -> None:
        """
        Log system maintenance actions for audit trail.
        
        Args:
            user: User performing the maintenance
            action: Maintenance action
            details: Additional details
        """
        try:
            self._log_admin_action(
                action=f'system_maintenance_{action}',
                user=user,
                details=details or {}
            )
            
        except Exception as e:
            logger.error(f"Failed to log system maintenance: {str(e)}")
    
    def get_audit_log_summary(self, days: int = 30) -> Dict[str, Any]:
        """
        Get a summary of audit log activities for the specified period.
        
        Args:
            days: Number of days to include in summary
            
        Returns:
            Dictionary with audit log summary
        """
        try:
            # This would typically read from audit logs
            # For now, return a basic summary based on email history
            start_date = timezone.now() - timedelta(days=days)
            
            # Count email-related activities
            email_activities = EmailHistory.objects.filter(sent_at__gte=start_date)
            
            summary = {
                'period_days': days,
                'start_date': start_date.isoformat(),
                'end_date': timezone.now().isoformat(),
                'total_emails_sent': email_activities.count(),
                'unique_senders': email_activities.values('sender').distinct().count(),
                'total_recipients': sum(email_activities.values_list('recipient_count', flat=True)),
                'activities': {
                    'email_records_created': email_activities.count(),
                    'delivery_status_updates': EmailDelivery.objects.filter(
                        email_history__sent_at__gte=start_date
                    ).count()
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Failed to get audit log summary: {str(e)}")
            raise EmailHistoryServiceError(f"Failed to get audit log summary: {str(e)}")


# Global email history service instance
email_history_service = EmailHistoryService()