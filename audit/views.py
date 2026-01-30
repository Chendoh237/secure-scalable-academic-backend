"""
API views for audit logging and email management
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count
from .models import AuditLog, EmailLog
from .services import AuditLogger, get_client_ip, get_user_agent
from .email_service import EmailNotificationService, BulkEmailService
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_audit_logs(request):
    """
    Get audit logs with filtering and pagination
    
    Query parameters:
    - action: Filter by action type
    - entity_type: Filter by entity type
    - admin_id: Filter by admin user
    - entity_id: Filter by entity ID
    - days: Number of days to look back (default: 30)
    - limit: Number of results to return (default: 100, max: 500)
    - offset: Pagination offset (default: 0)
    """
    try:
        # Get filter parameters
        action = request.query_params.get('action')
        entity_type = request.query_params.get('entity_type')
        admin_id = request.query_params.get('admin_id')
        entity_id = request.query_params.get('entity_id')
        search = request.query_params.get('search')
        days = int(request.query_params.get('days', 30))
        limit = min(int(request.query_params.get('limit', 100)), 500)
        offset = int(request.query_params.get('offset', 0))
        
        # Build query
        queryset = AuditLog.objects.all()
        
        # Date filter
        if days > 0:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=start_date)
        
        # Action filter
        if action:
            queryset = queryset.filter(action=action)
        
        # Entity type filter
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        # Admin filter
        if admin_id:
            queryset = queryset.filter(admin_id=admin_id)
        
        # Entity ID filter
        if entity_id:
            queryset = queryset.filter(entity_id=entity_id)
        
        # Search filter
        if search:
            queryset = queryset.filter(
                Q(entity_name__icontains=search) |
                Q(description__icontains=search) |
                Q(admin_username__icontains=search)
            )
        
        # Get total count
        total_count = queryset.count()
        
        # Get paginated results
        logs = queryset[offset:offset+limit]
        
        # Serialize data
        log_data = []
        for log in logs:
            log_data.append({
                'id': log.id,
                'admin': {
                    'id': log.admin.id if log.admin else None,
                    'username': log.admin_username
                },
                'action': log.action,
                'action_display': log.get_action_display(),
                'entity_type': log.entity_type,
                'entity_type_display': log.get_entity_type_display(),
                'entity_id': log.entity_id,
                'entity_name': log.entity_name,
                'description': log.description,
                'old_values': log.old_values,
                'new_values': log.new_values,
                'ip_address': log.ip_address,
                'success': log.success,
                'error_message': log.error_message,
                'created_at': log.created_at.isoformat()
            })
        
        return Response({
            'success': True,
            'data': log_data,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'returned': len(log_data)
            }
        })
    
    except Exception as e:
        logger.error(f"Error fetching audit logs: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_audit_summary(request):
    """Get summary of audit logs"""
    try:
        days = int(request.query_params.get('days', 30))
        start_date = timezone.now() - timedelta(days=days)
        
        # Get summary stats
        logs = AuditLog.objects.filter(created_at__gte=start_date)
        
        summary = {
            'total_actions': logs.count(),
            'by_action': dict(logs.values('action').annotate(count=Count('id')).values_list('action', 'count')),
            'by_entity_type': dict(logs.values('entity_type').annotate(count=Count('id')).values_list('entity_type', 'count')),
            'successful_actions': logs.filter(success=True).count(),
            'failed_actions': logs.filter(success=False).count(),
            'unique_admins': logs.values('admin').distinct().count(),
            'date_range': {
                'start': start_date.isoformat(),
                'end': timezone.now().isoformat()
            }
        }
        
        return Response({
            'success': True,
            'data': summary
        })
    
    except Exception as e:
        logger.error(f"Error fetching audit summary: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def export_audit_logs(request):
    """Export audit logs as CSV"""
    try:
        import csv
        from django.http import HttpResponse
        
        # Get filter parameters
        action = request.query_params.get('action')
        entity_type = request.query_params.get('entity_type')
        admin_id = request.query_params.get('admin_id')
        days = int(request.query_params.get('days', 30))
        
        # Build query
        queryset = AuditLog.objects.all()
        
        # Date filter
        if days > 0:
            start_date = timezone.now() - timedelta(days=days)
            queryset = queryset.filter(created_at__gte=start_date)
        
        # Action filter
        if action:
            queryset = queryset.filter(action=action)
        
        # Entity type filter
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        
        # Admin filter
        if admin_id:
            queryset = queryset.filter(admin_id=admin_id)
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Timestamp', 'Admin', 'Action', 'Entity Type', 'Entity ID',
            'Entity Name', 'Description', 'IP Address', 'Success', 'Error Message'
        ])
        
        for log in queryset:
            writer.writerow([
                log.created_at.isoformat(),
                log.admin_username,
                log.get_action_display(),
                log.get_entity_type_display(),
                log.entity_id,
                log.entity_name,
                log.description,
                log.ip_address,
                'Yes' if log.success else 'No',
                log.error_message
            ])
        
        return response
    
    except Exception as e:
        logger.error(f"Error exporting audit logs: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_email_logs(request):
    """
    Get email logs with filtering
    
    Query parameters:
    - status: Filter by email status (pending, sent, failed, bounced)
    - recipient: Filter by recipient email
    - message_type: Filter by message type
    - limit: Number of results
    - offset: Pagination offset
    """
    try:
        status_filter = request.query_params.get('status')
        recipient = request.query_params.get('recipient')
        message_type = request.query_params.get('message_type')
        limit = min(int(request.query_params.get('limit', 50)), 500)
        offset = int(request.query_params.get('offset', 0))
        
        queryset = EmailLog.objects.all()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if recipient:
            queryset = queryset.filter(recipient__icontains=recipient)
        
        if message_type:
            queryset = queryset.filter(message_type=message_type)
        
        total_count = queryset.count()
        emails = queryset[offset:offset+limit]
        
        email_data = []
        for email in emails:
            email_data.append({
                'id': email.id,
                'recipient': email.recipient,
                'recipient_name': email.recipient_name,
                'subject': email.subject,
                'message_type': email.message_type,
                'status': email.status,
                'status_display': email.get_status_display(),
                'initiated_by': email.initiated_by.username if email.initiated_by else 'System',
                'sent_at': email.sent_at.isoformat() if email.sent_at else None,
                'error_message': email.error_message,
                'created_at': email.created_at.isoformat()
            })
        
        return Response({
            'success': True,
            'data': email_data,
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'returned': len(email_data)
            }
        })
    
    except Exception as e:
        logger.error(f"Error fetching email logs: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def send_test_email(request):
    """Send a test email to verify email configuration"""
    try:
        recipient_email = request.data.get('email')
        
        if not recipient_email:
            return Response({
                'success': False,
                'error': 'Email address is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = EmailNotificationService.send_admin_alert(
            admin_email=recipient_email,
            admin_name=request.user.first_name or request.user.username,
            alert_title='Test Email',
            alert_message='This is a test email to verify your email configuration is working correctly.',
            severity='info',
            admin_user=request.user
        )
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'Test email sent successfully',
                'email_log_id': result['email_log_id']
            })
        else:
            return Response({
                'success': False,
                'error': result['error'],
                'email_log_id': result.get('email_log_id')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error sending test email: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def resend_email(request):
    """Resend a failed email"""
    try:
        email_log_id = request.data.get('email_log_id')
        
        if not email_log_id:
            return Response({
                'success': False,
                'error': 'Email log ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            email_log = EmailLog.objects.get(id=email_log_id)
        except EmailLog.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Email log not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check if max retries exceeded
        if email_log.retry_count >= email_log.max_retries:
            return Response({
                'success': False,
                'error': 'Maximum retries exceeded for this email'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Resend email
        try:
            from django.core.mail import send_mail
            send_mail(
                subject=email_log.subject,
                message=email_log.body,
                from_email=email_log.sender,
                recipient_list=[email_log.recipient],
                fail_silently=False
            )
            
            # Update log
            email_log.status = 'sent'
            email_log.sent_at = timezone.now()
            email_log.retry_count += 1
            email_log.error_message = ''
            email_log.save()
            
            return Response({
                'success': True,
                'message': 'Email resent successfully'
            })
        
        except Exception as e:
            email_log.retry_count += 1
            email_log.error_message = str(e)
            email_log.save()
            
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error resending email: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Email Configuration Endpoints

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def email_configuration(request):
    """Get or update email configuration"""
    from .models import EmailConfiguration
    
    try:
        if request.method == 'GET':
            try:
                config = EmailConfiguration.objects.first()
                if not config:
                    return Response({
                        'success': False,
                        'error': 'Email configuration not found'
                    }, status=status.HTTP_404_NOT_FOUND)
                
                return Response({
                    'success': True,
                    'data': {
                        'id': config.id,
                        'smtpHost': config.smtp_host,
                        'smtpPort': config.smtp_port,
                        'smtpUsername': config.smtp_username,
                        'fromEmail': config.from_email,
                        'fromName': config.from_name,
                        'useSSL': config.use_ssl,
                        'useTLS': config.use_tls,
                        'isActive': config.is_active,
                    }
                })
            except EmailConfiguration.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Email configuration not found'
                }, status=status.HTTP_404_NOT_FOUND)
        
        elif request.method == 'POST':
            # Update or create configuration
            config, created = EmailConfiguration.objects.get_or_create(pk=1)
            config.smtp_host = request.data.get('smtpHost', config.smtp_host)
            config.smtp_port = request.data.get('smtpPort', config.smtp_port)
            config.smtp_username = request.data.get('smtpUsername', config.smtp_username)
            if 'smtpPassword' in request.data:
                config.smtp_password = request.data.get('smtpPassword')
            config.from_email = request.data.get('fromEmail', config.from_email)
            config.from_name = request.data.get('fromName', config.from_name)
            config.use_ssl = request.data.get('useSSL', config.use_ssl)
            config.use_tls = request.data.get('useTLS', config.use_tls)
            config.is_active = request.data.get('isActive', config.is_active)
            config.save()
            
            # Log the change
            AuditLogger.log_settings_change(
                admin=request.user,
                setting_name='email_configuration',
                old_value='previous config',
                new_value=f"Updated SMTP settings for {config.from_email}",
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            
            return Response({
                'success': True,
                'message': 'Email configuration saved successfully'
            })
    
    except Exception as e:
        logger.error(f"Error managing email configuration: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def test_email_configuration(request):
    """Test email configuration by sending a test email"""
    from .models import EmailConfiguration
    
    try:
        to_email = request.data.get('toEmail')
        if not to_email:
            return Response({
                'success': False,
                'error': 'To email is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = EmailNotificationService.send_admin_alert(
            admin_email=to_email,
            admin_name=request.user.first_name or request.user.username,
            alert_title='Test Email',
            alert_message='This is a test email to verify your email configuration is working correctly.',
            severity='info',
            admin_user=request.user
        )
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'Test email sent successfully'
            })
        else:
            return Response({
                'success': False,
                'error': result['error']
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    except Exception as e:
        logger.error(f"Error testing email configuration: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Email Template Endpoints

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def email_templates(request):
    """Get all email templates or create a new template"""
    from .models import EmailTemplate
    
    try:
        if request.method == 'GET':
            templates = EmailTemplate.objects.all()
            template_data = []
            for template in templates:
                template_data.append({
                    'id': template.id,
                    'name': template.name,
                    'subject': template.subject,
                    'bodyHTML': template.body_html,
                    'bodyText': template.body_text,
                    'variables': template.variables,
                    'description': template.description,
                    'isActive': template.is_active,
                })
            
            return Response({
                'success': True,
                'data': template_data
            })
        
        elif request.method == 'POST':
            name = request.data.get('name')
            if not name:
                return Response({
                    'success': False,
                    'error': 'Template name is required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            template = EmailTemplate.objects.create(
                name=name,
                subject=request.data.get('subject', ''),
                body_html=request.data.get('bodyHTML', ''),
                body_text=request.data.get('bodyText', ''),
                variables=request.data.get('variables', []),
                description=request.data.get('description', ''),
                is_active=request.data.get('isActive', True)
            )
            
            AuditLogger.log_action(
                admin=request.user,
                action='CREATE',
                entity_type='settings',
                entity_id=str(template.id),
                entity_name=name,
                description=f"Created email template: {name}",
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            
            return Response({
                'success': True,
                'message': 'Email template created successfully',
                'data': {
                    'id': template.id,
                    'name': template.name,
                }
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Error managing email templates: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def email_template_detail(request, template_id):
    """Get, update, or delete a specific email template"""
    from .models import EmailTemplate
    
    try:
        try:
            template = EmailTemplate.objects.get(id=template_id)
        except EmailTemplate.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Email template not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            return Response({
                'success': True,
                'data': {
                    'id': template.id,
                    'name': template.name,
                    'subject': template.subject,
                    'bodyHTML': template.body_html,
                    'bodyText': template.body_text,
                    'variables': template.variables,
                    'description': template.description,
                    'isActive': template.is_active,
                }
            })
        
        elif request.method == 'PUT':
            template.name = request.data.get('name', template.name)
            template.subject = request.data.get('subject', template.subject)
            template.body_html = request.data.get('bodyHTML', template.body_html)
            template.body_text = request.data.get('bodyText', template.body_text)
            template.variables = request.data.get('variables', template.variables)
            template.description = request.data.get('description', template.description)
            template.is_active = request.data.get('isActive', template.is_active)
            template.save()
            
            AuditLogger.log_action(
                admin=request.user,
                action='UPDATE',
                entity_type='settings',
                entity_id=str(template.id),
                entity_name=template.name,
                description=f"Updated email template: {template.name}",
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            
            return Response({
                'success': True,
                'message': 'Email template updated successfully'
            })
        
        elif request.method == 'DELETE':
            template_name = template.name
            template.delete()
            
            AuditLogger.log_action(
                admin=request.user,
                action='DELETE',
                entity_type='settings',
                entity_id=str(template_id),
                entity_name=template_name,
                description=f"Deleted email template: {template_name}",
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            
            return Response({
                'success': True,
                'message': 'Email template deleted successfully'
            })
    
    except Exception as e:
        logger.error(f"Error managing email template: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Email Notification Rule Endpoints

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def email_rules(request):
    """Get all email notification rules or create a new rule"""
    from .models import EmailNotificationRule
    
    try:
        if request.method == 'GET':
            rules = EmailNotificationRule.objects.all()
            rule_data = []
            for rule in rules:
                rule_data.append({
                    'id': rule.id,
                    'name': rule.name,
                    'trigger': rule.trigger_event,
                    'templateId': rule.email_template_id,
                    'recipients': rule.recipient_emails,
                    'enabled': rule.is_enabled,
                })
            
            return Response({
                'success': True,
                'data': rule_data
            })
        
        elif request.method == 'POST':
            name = request.data.get('name')
            trigger = request.data.get('trigger')
            template_id = request.data.get('templateId')
            
            if not all([name, trigger, template_id]):
                return Response({
                    'success': False,
                    'error': 'Name, trigger, and template are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            try:
                from .models import EmailTemplate
                template = EmailTemplate.objects.get(id=template_id)
            except EmailTemplate.DoesNotExist:
                return Response({
                    'success': False,
                    'error': 'Email template not found'
                }, status=status.HTTP_404_NOT_FOUND)
            
            rule = EmailNotificationRule.objects.create(
                name=name,
                trigger_event=trigger,
                email_template=template,
                recipient_emails=request.data.get('recipients', []),
                recipient_type=request.data.get('recipientType', 'custom'),
                is_enabled=request.data.get('enabled', True)
            )
            
            AuditLogger.log_action(
                admin=request.user,
                action='CREATE',
                entity_type='settings',
                entity_id=str(rule.id),
                entity_name=name,
                description=f"Created email rule: {name}",
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            
            return Response({
                'success': True,
                'message': 'Email rule created successfully',
                'data': {
                    'id': rule.id,
                    'name': rule.name,
                }
            }, status=status.HTTP_201_CREATED)
    
    except Exception as e:
        logger.error(f"Error managing email rules: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def email_rule_detail(request, rule_id):
    """Get, update, or delete a specific email rule"""
    from .models import EmailNotificationRule, EmailTemplate
    
    try:
        try:
            rule = EmailNotificationRule.objects.get(id=rule_id)
        except EmailNotificationRule.DoesNotExist:
            return Response({
                'success': False,
                'error': 'Email rule not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        if request.method == 'GET':
            return Response({
                'success': True,
                'data': {
                    'id': rule.id,
                    'name': rule.name,
                    'trigger': rule.trigger_event,
                    'templateId': rule.email_template_id,
                    'recipients': rule.recipient_emails,
                    'enabled': rule.is_enabled,
                }
            })
        
        elif request.method == 'PUT':
            rule.name = request.data.get('name', rule.name)
            rule.trigger_event = request.data.get('trigger', rule.trigger_event)
            
            template_id = request.data.get('templateId')
            if template_id:
                try:
                    template = EmailTemplate.objects.get(id=template_id)
                    rule.email_template = template
                except EmailTemplate.DoesNotExist:
                    return Response({
                        'success': False,
                        'error': 'Email template not found'
                    }, status=status.HTTP_404_NOT_FOUND)
            
            rule.recipient_emails = request.data.get('recipients', rule.recipient_emails)
            rule.recipient_type = request.data.get('recipientType', rule.recipient_type)
            rule.is_enabled = request.data.get('enabled', rule.is_enabled)
            rule.save()
            
            AuditLogger.log_action(
                admin=request.user,
                action='UPDATE',
                entity_type='settings',
                entity_id=str(rule.id),
                entity_name=rule.name,
                description=f"Updated email rule: {rule.name}",
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            
            return Response({
                'success': True,
                'message': 'Email rule updated successfully'
            })
        
        elif request.method == 'DELETE':
            rule_name = rule.name
            rule.delete()
            
            AuditLogger.log_action(
                admin=request.user,
                action='DELETE',
                entity_type='settings',
                entity_id=str(rule_id),
                entity_name=rule_name,
                description=f"Deleted email rule: {rule_name}",
                ip_address=get_client_ip(request),
                user_agent=get_user_agent(request)
            )
            
            return Response({
                'success': True,
                'message': 'Email rule deleted successfully'
            })
    
    except Exception as e:
        logger.error(f"Error managing email rule: {str(e)}")
        return Response({
            'success': False,
            'error': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)