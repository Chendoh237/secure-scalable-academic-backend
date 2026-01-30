"""
Email Management API Views

This module provides Django REST API endpoints for the email management system.
Includes SMTP configuration, email composition, sending, and history management.
"""

import logging
from typing import Dict, Any, List
from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status

from .email_models import EmailConfiguration, EmailTemplate, EmailHistory
from .email_service import EmailService, email_service
from .template_service import TemplateService, template_service
from .recipient_service import RecipientService, recipient_service
from .email_history_service import EmailHistoryService, email_history_service
from .student_data_integration_service import student_data_integration_service, StudentDataIntegrationError

logger = logging.getLogger(__name__)


# SMTP Configuration API Endpoints

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_smtp_configuration(request):
    """
    Get current SMTP configuration
    
    Returns the current SMTP settings (passwords are masked for security)
    """
    try:
        config = EmailConfiguration.get_current_config()
        if not config:
            return Response({
                'configured': False,
                'message': 'No SMTP configuration found'
            }, status=status.HTTP_200_OK)
        
        # Return configuration with masked password
        config_data = {
            'configured': True,
            'smtp_host': config.smtp_host,
            'smtp_port': config.smtp_port,
            'email_user': config.smtp_username,  # Use direct field instead of property
            'email_password': '***masked***' if config.smtp_password else '',
            'use_tls': config.use_tls,
            'use_ssl': config.use_ssl,
            'from_name': config.from_name,
            'provider': config.provider,
            'is_active': config.is_active,
            'created_at': config.created_at.isoformat() if config.created_at else None,
            'updated_at': config.updated_at.isoformat() if config.updated_at else None
        }
        
        return Response(config_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving SMTP configuration: {str(e)}")
        return Response({
            'error': 'Failed to retrieve SMTP configuration',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def save_smtp_configuration(request):
    """
    Save or update SMTP configuration
    
    Expected payload:
    {
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "email_user": "admin@example.com",
        "email_password": "password",
        "use_tls": true,
        "use_ssl": false,
        "from_name": "University System",
        "provider": "gmail"
    }
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['smtp_host', 'smtp_port', 'email_user', 'email_password']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return Response({
                'error': 'Missing required fields',
                'missing_fields': missing_fields
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create configuration
        config = EmailConfiguration.get_current_config()
        old_config = None
        
        if config:
            # Store old config for audit logging
            old_config = {
                'smtp_host': config.smtp_host,
                'smtp_port': config.smtp_port,
                'email_user': config.smtp_username,
                'provider': config.provider
            }
            
            # Update existing configuration
            config.smtp_host = data['smtp_host']
            config.smtp_port = int(data['smtp_port'])
            config.smtp_username = data['email_user']
            config.set_password(data['email_password'])  # Use set_password method
            config.use_tls = data.get('use_tls', True)
            config.use_ssl = data.get('use_ssl', False)
            config.from_name = data.get('from_name', 'University System')
            config.from_email = data['email_user']  # Use email_user as from_email
            config.is_active = True
            config.save()
        else:
            # Create new configuration
            config = EmailConfiguration.objects.create(
                smtp_host=data['smtp_host'],
                smtp_port=int(data['smtp_port']),
                smtp_username=data['email_user'],
                from_email=data['email_user'],
                use_tls=data.get('use_tls', True),
                use_ssl=data.get('use_ssl', False),
                from_name=data.get('from_name', 'University System'),
                is_active=True
            )
            config.set_password(data['email_password'])  # Set password after creation
            config.save()
        
        # Log administrative action
        new_config = {
            'smtp_host': config.smtp_host,
            'smtp_port': config.smtp_port,
            'email_user': config.smtp_username,
            'provider': config.provider
        }
        
        email_history_service.log_smtp_configuration_change(
            user=request.user,
            old_config=old_config,
            new_config=new_config
        )
        
        return Response({
            'success': True,
            'message': 'SMTP configuration saved successfully',
            'config_id': config.id
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': 'Invalid data format',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error saving SMTP configuration: {str(e)}")
        return Response({
            'error': 'Failed to save SMTP configuration',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def test_smtp_connection(request):
    """
    Test SMTP connection with provided or current configuration
    
    Can test with current saved config or with new config data
    """
    try:
        data = request.data
        
        if data:
            # Test with provided configuration
            test_config = {
                'smtpServer': data.get('smtp_host'),
                'smtpPort': int(data.get('smtp_port', 587)),
                'emailUser': data.get('email_user'),
                'emailPassword': data.get('email_password'),
                'useTLS': data.get('use_tls', True),
                'useSSL': data.get('use_ssl', False),
                'fromName': data.get('from_name', 'Test')
            }
        else:
            # Test with current saved configuration
            config = EmailConfiguration.get_current_config()
            if not config:
                return Response({
                    'success': False,
                    'error': 'No SMTP configuration found to test'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            test_config = {
                'smtpServer': config.smtp_host,
                'smtpPort': config.smtp_port,
                'emailUser': config.smtp_username,
                'emailPassword': config.get_decrypted_password(),
                'useTLS': config.use_tls,
                'useSSL': config.use_ssl,
                'fromName': config.from_name
            }
        
        # Test the connection
        result = email_service.test_connection(test_config)
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'SMTP connection test successful',
                'details': result.get('message', 'Connection established successfully'),
                'connection_info': result.get('details', {})
            }, status=status.HTTP_200_OK)
        else:
            # Use the improved error messages from the service
            return Response({
                'success': False,
                'error': 'SMTP connection test failed',
                'details': result.get('error', 'Unknown connection error'),
                'technical_details': result.get('technical_details'),
                'error_code': result.get('error_code'),
                'retry_suggested': result.get('retry_suggested', True)
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except ValueError as e:
        return Response({
            'success': False,
            'error': 'Invalid configuration data',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error testing SMTP connection: {str(e)}")
        return Response({
            'success': False,
            'error': 'Failed to test SMTP connection',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_smtp_providers(request):
    """
    Get list of supported SMTP providers with their default configurations
    """
    try:
        providers = email_service.get_supported_providers()
        provider_configs = {}
        
        for provider in providers:
            config = email_service.get_provider_config(provider)
            if config:
                provider_configs[provider] = {
                    'name': config.get('name', provider.title()),
                    'smtp_host': config['smtp_host'],
                    'smtp_port': config['smtp_port'],
                    'use_tls': config.get('use_tls', True),
                    'use_ssl': config.get('use_ssl', False),
                    'description': config.get('description', f'{provider.title()} SMTP configuration')
                }
        
        return Response({
            'providers': provider_configs
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving SMTP providers: {str(e)}")
        return Response({
            'error': 'Failed to retrieve SMTP providers',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminUser])
def delete_smtp_configuration(request):
    """
    Delete current SMTP configuration
    """
    try:
        config = EmailConfiguration.get_current_config()
        if not config:
            return Response({
                'error': 'No SMTP configuration found to delete'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Store config details for audit log
        old_config = {
            'smtp_host': config.smtp_host,
            'smtp_port': config.smtp_port,
            'email_user': config.smtp_username,
            'provider': config.provider
        }
        
        # Delete the configuration
        config.delete()
        
        # Log administrative action
        email_history_service.log_smtp_configuration_change(
            user=request.user,
            old_config=old_config,
            new_config=None
        )
        
        return Response({
            'success': True,
            'message': 'SMTP configuration deleted successfully'
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error deleting SMTP configuration: {str(e)}")
        return Response({
            'error': 'Failed to delete SMTP configuration',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Email Template and Composition API Endpoints

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_email_templates(request):
    """
    Get available email templates with optional category filtering
    """
    try:
        category = request.GET.get('category')
        templates = template_service.get_templates(category=category, active_only=True)
        
        template_data = []
        for template in templates:
            template_data.append({
                'id': template.id,
                'name': template.name,
                'category': template.category,
                'subject_template': template.subject_template,
                'body_template': template.body_template,
                'variables': template.get_variables(),
                'description': template.description,
                'created_at': template.created_at.isoformat(),
                'updated_at': template.updated_at.isoformat()
            })
        
        return Response({
            'templates': template_data,
            'categories': template_service.get_template_categories()
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving email templates: {str(e)}")
        return Response({
            'error': 'Failed to retrieve email templates',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def render_email_template(request):
    """
    Render an email template with provided context variables
    
    Expected payload:
    {
        "template_id": 1,
        "context": {
            "student_name": "John Doe",
            "course_name": "Mathematics"
        }
    }
    """
    try:
        data = request.data
        template_id = data.get('template_id')
        context = data.get('context', {})
        
        if not template_id:
            return Response({
                'error': 'Missing required field: template_id'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get template
        template = template_service.get_template(template_id)
        if not template:
            return Response({
                'error': 'Template not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Render template
        rendered = template_service.render_template(template, context)
        
        return Response({
            'rendered': rendered,
            'template_name': template.name,
            'variables_used': template.get_variables()
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': 'Invalid data format',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error rendering email template: {str(e)}")
        return Response({
            'error': 'Failed to render email template',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_recipient_options(request):
    """
    Get available recipient selection options and statistics
    """
    try:
        # Get recipient statistics
        stats = recipient_service.get_recipient_statistics()
        
        # Get departments with student counts
        departments = recipient_service.get_departments_with_student_counts()
        
        return Response({
            'statistics': stats,
            'departments': departments,
            'selection_types': [
                {'value': 'all', 'label': 'All Students', 'description': 'Send to all active students'},
                {'value': 'department', 'label': 'By Department', 'description': 'Send to students in specific departments'},
                {'value': 'level', 'label': 'By Level', 'description': 'Send to students in specific academic levels'},
                {'value': 'specific', 'label': 'Specific Students', 'description': 'Send to individually selected students'},
                {'value': 'custom', 'label': 'Custom Email List', 'description': 'Send to custom email addresses'}
            ]
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving recipient options: {str(e)}")
        return Response({
            'error': 'Failed to retrieve recipient options',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def validate_recipients(request):
    """
    Validate and build recipient list based on selection criteria
    
    Expected payload:
    {
        "type": "department",
        "department_ids": [1, 2],
        "level_ids": ["100", "200"],
        "student_ids": [1, 2, 3],
        "emails": ["custom@example.com"]
    }
    """
    try:
        data = request.data
        
        # Validate recipient configuration
        if not data or not isinstance(data, dict):
            return Response({
                'error': 'Invalid recipient configuration',
                'details': 'Request body must be a valid JSON object'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        recipient_type = data.get('type')
        if not recipient_type:
            return Response({
                'error': 'Missing required field: type',
                'details': 'Recipient type must be specified (all, department, level, specific, custom)'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build recipient list
        recipients, metadata = recipient_service.build_recipient_list(data)
        
        # Validate email addresses
        validation = recipient_service.validate_email_addresses(recipients)
        
        return Response({
            'recipients': recipients[:10],  # Return first 10 for preview
            'total_count': len(recipients),
            'metadata': metadata,
            'validation': validation,
            'preview_truncated': len(recipients) > 10
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': 'Invalid recipient configuration',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error validating recipients: {str(e)}")
        return Response({
            'error': 'Failed to validate recipients',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def send_bulk_email(request):
    """
    Send bulk email to selected recipients
    
    Expected payload:
    {
        "subject": "Email Subject",
        "body": "Email body content",
        "template_id": 1,
        "recipient_config": {
            "type": "department",
            "department_ids": [1, 2]
        },
        "send_immediately": true
    }
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['subject', 'body', 'recipient_config']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return Response({
                'error': 'Missing required fields',
                'missing_fields': missing_fields
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Build recipient list
        recipients, metadata = recipient_service.build_recipient_list(data['recipient_config'])
        
        if not recipients:
            return Response({
                'error': 'No valid recipients found'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get template if specified
        template_used = None
        if data.get('template_id'):
            template_used = template_service.get_template(data['template_id'])
        
        # Create email history record
        history = email_history_service.save_email_record(
            sender_user=request.user,
            subject=data['subject'],
            body=data['body'],
            recipients=recipients,
            template_used=template_used
        )
        
        # Send emails if requested
        if data.get('send_immediately', False):
            try:
                # Check SMTP configuration
                smtp_config = EmailConfiguration.get_current_config()
                if not smtp_config:
                    return Response({
                        'error': 'No SMTP configuration found. Please configure SMTP settings first.'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Prepare email data for sending
                email_data = {
                    'subject': data['subject'],
                    'body': data['body'],
                    'from_name': smtp_config.from_name,
                    'from_email': smtp_config.from_email
                }
                
                # Send bulk email
                result = email_service.send_bulk_email(
                    to_emails=recipients,
                    subject=data['subject'],
                    message=data['body'],
                    sender_user=request.user,
                    template_used=template_used
                )
                
                # Create in-app notifications for students
                from .notification_integration import email_notification_integration
                notification_result = email_notification_integration.create_email_notifications(
                    sender_user=request.user,
                    subject=data['subject'],
                    body=data['body'],
                    recipients=recipients,
                    email_history_id=history.id
                )
                
                # Update history with results
                if result.get('success'):
                    history.status = 'completed' if result.get('failed_count', 0) == 0 else 'partial_failure'
                    history.success_count = result.get('sent_count', 0)
                    history.failure_count = result.get('failed_count', 0)
                else:
                    history.status = 'failed'
                    history.error_message = result.get('error', 'Unknown error')
                
                history.save()
                
                # Log bulk email operation
                email_history_service.log_bulk_email_operation(
                    user=request.user,
                    operation='completed',
                    recipient_count=len(recipients)
                )
                
                # Prepare response based on result
                if result.get('success'):
                    response_data = {
                        'success': True,
                        'message': result.get('message', 'Bulk email sent successfully'),
                        'history_id': history.id,
                        'total_recipients': len(recipients),
                        'sent_count': result.get('sent_count', 0),
                        'failed_count': result.get('failed_count', 0),
                        'success_rate': result.get('success_rate', 0),
                        'notifications_created': notification_result.get('notifications_created', 0)
                    }
                    
                    # Include failure details if any
                    if result.get('failed_recipients'):
                        response_data['failed_recipients'] = result['failed_recipients']
                        response_data['retry_suggested'] = result.get('retry_suggested', False)
                    
                    # Include batch results if available
                    if result.get('batch_results'):
                        response_data['batch_results'] = result['batch_results']
                    
                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    # Handle service-level errors
                    error_type = result.get('error_type', 'unknown')
                    status_code = status.HTTP_400_BAD_REQUEST if error_type == 'validation' else status.HTTP_500_INTERNAL_SERVER_ERROR
                    
                    return Response({
                        'success': False,
                        'error': result.get('error', 'Failed to send bulk email'),
                        'error_type': error_type,
                        'history_id': history.id,
                        'sent_count': result.get('sent_count', 0),
                        'failed_count': result.get('failed_count', 0),
                        'retry_suggested': result.get('retry_suggested', True)
                    }, status=status_code)
                
            except Exception as send_error:
                # Update history with error
                history.status = 'failed'
                history.error_message = str(send_error)
                history.save()
                
                logger.error(f"Error sending bulk email: {str(send_error)}")
                return Response({
                    'error': 'Failed to send bulk email',
                    'details': str(send_error),
                    'history_id': history.id
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            # Email queued for later sending
            return Response({
                'success': True,
                'message': 'Email queued successfully',
                'history_id': history.id,
                'total_recipients': len(recipients),
                'status': 'queued'
            }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': 'Invalid data format',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error processing bulk email: {str(e)}")
        return Response({
            'error': 'Failed to process bulk email',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Email History API Endpoints

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_email_history(request):
    """
    Get email history with optional filtering and pagination
    
    Query parameters:
    - page: Page number (default: 1)
    - page_size: Items per page (default: 20)
    - search: Search term for subject/sender
    - status: Filter by status
    - date_from: Start date filter (YYYY-MM-DD)
    - date_to: End date filter (YYYY-MM-DD)
    """
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        # Build filters
        filters = {}
        if status_filter:
            filters['status'] = status_filter
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        
        # Get email history
        if search:
            # Use search functionality
            search_results = email_history_service.search_email_history(search)
            # Apply additional filters if needed
            if filters:
                # Simple filtering for search results
                filtered_results = []
                for result in search_results:
                    if status_filter and result.get('status') != status_filter:
                        continue
                    filtered_results.append(result)
                search_results = filtered_results
            
            # Manual pagination for search results
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_results = search_results[start_idx:end_idx]
            
            history_data = {
                'results': [],
                'pagination': {
                    'page': page,
                    'page_size': page_size,
                    'total_count': len(search_results),
                    'total_pages': (len(search_results) + page_size - 1) // page_size
                }
            }
            
            # Search results are already dictionaries with different field names
            for record in paginated_results:
                history_data['results'].append({
                    'id': record['id'],
                    'sender': record['sender_name'],
                    'subject': record['subject'],
                    'recipient_count': record['recipient_count'],
                    'status': record['status'],
                    'success_count': 0,  # Not available in search results
                    'failure_count': 0,  # Not available in search results
                    'success_rate': record['success_rate'],
                    'sent_at': record['sent_at'],
                    'template_name': None  # Not available in search results
                })
        else:
            # Use regular history retrieval with filters
            history_data = email_history_service.get_email_history(
                page=page,
                page_size=page_size,
                filters=filters
            )
            
            # Convert sender objects to strings for frontend compatibility
            if history_data and 'results' in history_data:
                for record in history_data['results']:
                    sender = record.get('sender')
                    if isinstance(sender, dict):
                        # Convert sender object to string
                        record['sender'] = sender.get('username', 'Unknown')
                    elif hasattr(sender, 'username'):
                        # Handle User model objects
                        record['sender'] = sender.username
                    elif not isinstance(sender, str):
                        # Fallback for any other object type
                        record['sender'] = str(sender) if sender else 'Unknown'
                    
                    # Also fix template_name field
                    template_used = record.get('template_used')
                    if isinstance(template_used, dict):
                        record['template_name'] = template_used.get('name')
                    elif hasattr(template_used, 'name'):
                        record['template_name'] = template_used.name
                    else:
                        record['template_name'] = None
        
        return Response(history_data, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': 'Invalid query parameters',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error retrieving email history: {str(e)}")
        return Response({
            'error': 'Failed to retrieve email history',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_email_delivery_details(request, history_id):
    """
    Get detailed delivery information for a specific email
    """
    try:
        # Get delivery details
        details = email_history_service.get_delivery_details(history_id)
        
        if not details:
            return Response({
                'error': 'Email history record not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Details are already dictionaries from the service
        delivery_data = []
        for delivery in details:
            delivery_data.append({
                'recipient_email': delivery['recipient_email'],
                'recipient_name': delivery['recipient_name'],
                'delivery_status': delivery['delivery_status'],
                'error_message': delivery['error_message'],
                'sent_at': delivery['sent_at'],
                'delivered_at': delivery['delivered_at'],
                'student_name': delivery['student']['full_name'] if delivery['student'] else None
            })
        
        return Response({
            'history_id': history_id,
            'deliveries': delivery_data,
            'total_count': len(delivery_data)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error retrieving delivery details: {str(e)}")
        return Response({
            'error': 'Failed to retrieve delivery details',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_email_statistics(request):
    """
    Get email statistics and analytics
    
    Query parameters:
    - days: Number of days to include (default: 30)
    """
    try:
        days = int(request.GET.get('days', 30))
        
        # Get email statistics
        stats = email_history_service.get_email_statistics(days=days)
        
        return Response({
            'statistics': stats,
            'period_days': days
        }, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response({
            'error': 'Invalid query parameters',
            'details': str(e)
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error retrieving email statistics: {str(e)}")
        return Response({
            'error': 'Failed to retrieve email statistics',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Notification Integration API Endpoints

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def create_system_announcement(request):
    """
    Create system-wide announcement as notifications
    
    Expected payload:
    {
        "title": "System Maintenance",
        "message": "System will be down for maintenance...",
        "recipient_type": "all",
        "department_ids": [1, 2],
        "level_ids": ["100", "200"],
        "student_ids": [1, 2, 3]
    }
    """
    try:
        from .notification_integration import email_notification_integration
        
        data = request.data
        
        # Validate required fields
        required_fields = ['title', 'message']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return Response({
                'error': 'Missing required fields',
                'missing_fields': missing_fields
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create system announcement
        result = email_notification_integration.create_system_announcement(
            sender_user=request.user,
            title=data['title'],
            message=data['message'],
            recipient_type=data.get('recipient_type', 'all'),
            department_ids=data.get('department_ids', []),
            level_ids=data.get('level_ids', []),
            student_ids=data.get('student_ids', [])
        )
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'System announcement created successfully',
                'notifications_created': result['notifications_created'],
                'failed_notifications': result['failed_notifications'],
                'total_recipients': result['total_recipients'],
                'metadata': result.get('metadata', {})
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Failed to create system announcement',
                'details': result.get('error', 'Unknown error')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error creating system announcement: {str(e)}")
        return Response({
            'error': 'Failed to create system announcement',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def create_course_notification(request):
    """
    Create course-specific notification for enrolled students
    
    Expected payload:
    {
        "title": "Course Update",
        "message": "Important course announcement...",
        "course_id": 1,
        "department_id": 1
    }
    """
    try:
        from .notification_integration import email_notification_integration
        
        data = request.data
        
        # Validate required fields
        required_fields = ['title', 'message', 'course_id']
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return Response({
                'error': 'Missing required fields',
                'missing_fields': missing_fields
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create course notification
        result = email_notification_integration.create_course_notification(
            sender_user=request.user,
            title=data['title'],
            message=data['message'],
            course_id=data['course_id'],
            department_id=data.get('department_id')
        )
        
        if result['success']:
            return Response({
                'success': True,
                'message': 'Course notification created successfully',
                'notifications_created': result['notifications_created'],
                'failed_notifications': result['failed_notifications'],
                'total_recipients': result['total_recipients']
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': 'Failed to create course notification',
                'details': result.get('error', 'Unknown error')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error creating course notification: {str(e)}")
        return Response({
            'error': 'Failed to create course notification',
            'details': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Student Data Integration API Endpoints

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_integration_health_report(request):
    """
    Get comprehensive health report for student data integration
    
    Returns detailed metrics about data quality and integration status
    """
    try:
        report = student_data_integration_service.get_integration_health_report()
        
        return Response({
            'success': True,
            'report': report
        }, status=status.HTTP_200_OK)
        
    except StudentDataIntegrationError as e:
        logger.error(f"Failed to get integration health report: {str(e)}")
        return Response({
            'error': f'Failed to get integration health report: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Unexpected error getting integration health report: {str(e)}")
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def validate_student_emails(request):
    """
    Validate email addresses for all students
    
    Returns comprehensive validation results including missing and invalid emails
    """
    try:
        # Get optional student IDs from query parameters
        student_ids = request.GET.getlist('student_ids')
        if student_ids:
            try:
                student_ids = [int(id) for id in student_ids]
                students = student_data_integration_service.get_real_time_student_data(student_ids)
            except ValueError:
                return Response({
                    'error': 'Invalid student IDs provided'
                }, status=status.HTTP_400_BAD_REQUEST)
        else:
            students = None
        
        validation_result = student_data_integration_service.validate_student_email_addresses(students)
        
        return Response({
            'success': True,
            'validation': validation_result.to_dict()
        }, status=status.HTTP_200_OK)
        
    except StudentDataIntegrationError as e:
        logger.error(f"Failed to validate student emails: {str(e)}")
        return Response({
            'error': f'Failed to validate student emails: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Unexpected error validating student emails: {str(e)}")
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_students_with_missing_data(request):
    """
    Get students with missing or incomplete data
    
    Returns categorized list of students with data issues
    """
    try:
        missing_data = student_data_integration_service.get_students_with_missing_data()
        
        # Convert student objects to serializable format
        serialized_data = {}
        for category, students in missing_data.items():
            serialized_data[category] = [
                {
                    'id': student.id,
                    'full_name': student.full_name,
                    'matric_number': student.matric_number,
                    'department': student.department.name if student.department else None,
                    'email': getattr(student.user, 'email', None) if hasattr(student, 'user') and student.user else None,
                    'is_active': student.is_active
                }
                for student in students
            ]
        
        return Response({
            'success': True,
            'missing_data': serialized_data,
            'summary': {
                category: len(students) for category, students in missing_data.items()
            }
        }, status=status.HTTP_200_OK)
        
    except StudentDataIntegrationError as e:
        logger.error(f"Failed to get students with missing data: {str(e)}")
        return Response({
            'error': f'Failed to get students with missing data: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Unexpected error getting students with missing data: {str(e)}")
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def refresh_student_data_cache(request):
    """
    Refresh cached student data for real-time accuracy
    
    Optional body parameters:
    - student_ids: List of specific student IDs to refresh
    """
    try:
        student_ids = request.data.get('student_ids')
        if student_ids and not isinstance(student_ids, list):
            return Response({
                'error': 'student_ids must be a list'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = student_data_integration_service.refresh_student_data_cache(student_ids)
        
        return Response({
            'success': True,
            'result': result
        }, status=status.HTTP_200_OK)
        
    except StudentDataIntegrationError as e:
        logger.error(f"Failed to refresh student data cache: {str(e)}")
        return Response({
            'error': f'Failed to refresh student data cache: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Unexpected error refreshing student data cache: {str(e)}")
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def assess_delivery_readiness(request):
    """
    Assess readiness for email delivery based on recipient configuration
    
    Body parameters:
    - recipient_config: Recipient selection configuration
    """
    try:
        recipient_config = request.data.get('recipient_config')
        if not recipient_config:
            return Response({
                'error': 'recipient_config is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        readiness = student_data_integration_service.get_student_email_delivery_readiness(recipient_config)
        
        return Response({
            'success': True,
            'readiness': readiness
        }, status=status.HTTP_200_OK)
        
    except StudentDataIntegrationError as e:
        logger.error(f"Failed to assess delivery readiness: {str(e)}")
        return Response({
            'error': f'Failed to assess delivery readiness: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Unexpected error assessing delivery readiness: {str(e)}")
        return Response({
            'error': f'Unexpected error: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)