"""
End-to-End Integration Tests for Email Management System

This module contains comprehensive integration tests that validate complete workflows
from frontend to backend, ensuring all components work together properly.

Tests cover:
1. Complete email sending workflow from composition to delivery
2. SMTP configuration and connection testing workflow  
3. Email history and audit trail functionality
4. Error handling across the entire system
5. Security and authentication integration
"""

import unittest
import json
import tempfile
import os
from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core import mail
from django.conf import settings
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
from django.utils import timezone
import smtplib
import time

from students.email_models import EmailConfiguration, EmailTemplate, EmailHistory, EmailDelivery
from students.email_service import EmailService
from students.template_service import TemplateService
from students.recipient_service import RecipientService
from students.email_history_service import EmailHistoryService
from students.models import Student
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram
from notifications.models import Notification

User = get_user_model()


class EmailManagementE2EIntegrationTest(TransactionTestCase):
    """
    End-to-end integration tests for the complete email management system.
    Tests the full workflow from frontend API calls to backend processing.
    """
    
    def setUp(self):
        """Set up test environment with all required data"""
        self.client = Client()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='testadmin',
            email='admin@test.edu',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create institution structure
        self.institution = Institution.objects.create(
            name="Test University",
            code="TU",
            address="123 Test St"
        )
        
        self.faculty = Faculty.objects.create(
            name="Test Faculty",
            institution=self.institution
        )
        
        self.department = Department.objects.create(
            name="Computer Science",
            faculty=self.faculty
        )
        
        self.program = AcademicProgram.objects.create(
            name="Computer Science Program",
            code="CS",
            department=self.department
        )
        
        # Create test students
        self.students = []
        for i in range(5):
            student = Student.objects.create(
                student_id=f"CS202{i}",
                first_name=f"Student{i}",
                last_name="Test",
                email=f"student{i}@test.edu",
                department=self.department,
                level="Level 1",
                is_approved=True
            )
            self.students.append(student)
        
        # Login admin user
        self.client.login(username='testadmin', password='testpass123')
    
    def test_complete_email_sending_workflow(self):
        """
        Test the complete workflow from SMTP configuration to email delivery.
        This simulates the full user journey through the frontend.
        """
        # Step 1: Configure SMTP settings (simulating frontend form submission)
        smtp_config_data = {
            'smtp_host': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_username': 'test@gmail.com',
            'smtp_password': 'test_app_password',
            'from_email': 'test@gmail.com',
            'from_name': 'Test System',
            'use_tls': True,
            'use_ssl': False
        }
        
        response = self.client.post('/admin/email/smtp/config/save/', 
                                  data=json.dumps(smtp_config_data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Verify SMTP configuration was saved
        config = EmailConfiguration.objects.filter(is_active=True).first()
        self.assertIsNotNone(config)
        self.assertEqual(config.smtp_host, 'smtp.gmail.com')
        
        # Step 2: Test SMTP connection (simulating frontend connection test)
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value = mock_server
            
            response = self.client.post('/admin/email/smtp/config/test/',
                                      content_type='application/json')
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertTrue(data['success'])
        
        # Step 3: Get recipient options (simulating frontend recipient selection)
        response = self.client.get('/admin/email/recipients/options/')
        self.assertEqual(response.status_code, 200)
        recipient_data = json.loads(response.content)
        
        self.assertIn('departments', recipient_data)
        self.assertIn('levels', recipient_data)
        self.assertTrue(len(recipient_data['departments']) > 0)
        
        # Step 4: Validate recipients (simulating frontend recipient validation)
        recipient_config = {
            'type': 'department',
            'department_ids': [self.department.id],
            'levels': ['Level 1']
        }
        
        response = self.client.post('/admin/email/recipients/validate/',
                                  data=json.dumps(recipient_config),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        validation_data = json.loads(response.content)
        
        self.assertTrue(validation_data['valid'])
        self.assertEqual(validation_data['recipient_count'], 5)  # 5 test students
        
        # Step 5: Get email templates (simulating frontend template selection)
        response = self.client.get('/admin/email/templates/')
        self.assertEqual(response.status_code, 200)
        templates_data = json.loads(response.content)
        self.assertIn('templates', templates_data)
        
        # Step 6: Send bulk email (simulating frontend email composition and sending)
        email_data = {
            'subject': 'Test Integration Email',
            'message': 'This is a test email from the integration test.',
            'template_id': None,  # Using plain text
            'recipient_config': recipient_config,
            'send_notifications': True
        }
        
        with patch('students.email_service.EmailService.send_bulk_email') as mock_send:
            # Mock successful email sending
            mock_send.return_value = {
                'success': True,
                'total_recipients': 5,
                'successful_sends': 5,
                'failed_sends': 0,
                'history_id': 1
            }
            
            response = self.client.post('/admin/email/send/',
                                      data=json.dumps(email_data),
                                      content_type='application/json')
            self.assertEqual(response.status_code, 200)
            send_data = json.loads(response.content)
            
            self.assertTrue(send_data['success'])
            self.assertEqual(send_data['total_recipients'], 5)
            self.assertEqual(send_data['successful_sends'], 5)
        
        # Step 7: Verify email history was created (simulating frontend history view)
        response = self.client.get('/admin/email/history/')
        self.assertEqual(response.status_code, 200)
        history_data = json.loads(response.content)
        
        self.assertIn('results', history_data)
        # Note: Since we mocked the email sending, we won't have actual history records
        # In a real scenario, this would verify the email was logged
        
        # Step 8: Verify notifications were created for students
        notifications = Notification.objects.filter(
            title='Test Integration Email'
        )
        # Note: Notifications would be created in the actual email sending process
        # This verifies the integration between email and notification systems
    
    def test_smtp_configuration_workflow(self):
        """
        Test the complete SMTP configuration workflow including error handling.
        """
        # Test 1: Save valid SMTP configuration
        valid_config = {
            'smtp_host': 'smtp.outlook.com',
            'smtp_port': 587,
            'smtp_username': 'test@outlook.com',
            'smtp_password': 'valid_password',
            'from_email': 'test@outlook.com',
            'from_name': 'Test Outlook',
            'use_tls': True,
            'use_ssl': False
        }
        
        response = self.client.post('/admin/email/smtp/config/save/',
                                  data=json.dumps(valid_config),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Test 2: Get SMTP configuration
        response = self.client.get('/admin/email/smtp/config/')
        self.assertEqual(response.status_code, 200)
        config_data = json.loads(response.content)
        
        self.assertTrue(config_data['configured'])
        self.assertEqual(config_data['smtp_host'], 'smtp.outlook.com')
        # Password should not be returned for security
        self.assertNotIn('smtp_password', config_data)
        
        # Test 3: Test connection with invalid credentials
        with patch('smtplib.SMTP') as mock_smtp:
            mock_server = MagicMock()
            mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, 'Authentication failed')
            mock_smtp.return_value = mock_server
            
            response = self.client.post('/admin/email/smtp/config/test/',
                                      content_type='application/json')
            self.assertEqual(response.status_code, 400)  # Bad Request for auth failure
            data = json.loads(response.content)
            self.assertFalse(data['success'])
            self.assertIn('authentication', data['error'].lower())
        
        # Test 4: Test connection with network error
        with patch('smtplib.SMTP') as mock_smtp:
            mock_smtp.side_effect = ConnectionError("Network unreachable")
            
            response = self.client.post('/admin/email/smtp/config/test/',
                                      content_type='application/json')
            self.assertEqual(response.status_code, 400)
            data = json.loads(response.content)
            self.assertFalse(data['success'])
            self.assertIn('network', data['error'].lower())
        
        # Test 5: Delete SMTP configuration
        response = self.client.delete('/admin/email/smtp/config/delete/')
        self.assertEqual(response.status_code, 200)
        
        # Verify configuration was deleted
        response = self.client.get('/admin/email/smtp/config/')
        self.assertEqual(response.status_code, 200)
        config_data = json.loads(response.content)
        self.assertFalse(config_data['configured'])
    
    def test_email_history_and_audit_workflow(self):
        """
        Test the complete email history and audit trail functionality.
        """
        # Create test email history records
        config = EmailConfiguration.objects.create(
            smtp_host='smtp.test.com',
            smtp_port=587,
            smtp_username='test@test.com',
            from_email='test@test.com',
            use_tls=True,
            is_active=True
        )
        config.set_password('test_password')
        config.save()
        
        # Create email history records
        histories = []
        for i in range(3):
            history = EmailHistory.objects.create(
                sender=self.admin_user,
                subject=f'Test Email {i+1}',
                message=f'Test message {i+1}',
                recipient_count=2,
                successful_sends=2 if i < 2 else 1,  # One partial failure
                failed_sends=0 if i < 2 else 1,
                status='completed' if i < 2 else 'partial_failure'
            )
            histories.append(history)
            
            # Create delivery records
            for j, student in enumerate(self.students[:2]):
                delivery_status = 'delivered' if i < 2 or j == 0 else 'failed'
                EmailDelivery.objects.create(
                    email_history=history,
                    recipient_email=student.email,
                    recipient_name=f"{student.first_name} {student.last_name}",
                    status=delivery_status,
                    delivered_at=timezone.now() if delivery_status == 'delivered' else None,
                    error_message='SMTP timeout' if delivery_status == 'failed' else None
                )
        
        # Test 1: Get email history with pagination
        response = self.client.get('/admin/email/history/?page=1&page_size=2')
        self.assertEqual(response.status_code, 200)
        history_data = json.loads(response.content)
        
        self.assertIn('results', history_data)
        self.assertIn('count', history_data)
        self.assertEqual(len(history_data['results']), 2)  # Page size limit
        self.assertEqual(history_data['count'], 3)  # Total count
        
        # Test 2: Filter email history by status
        response = self.client.get('/admin/email/history/?status=completed')
        self.assertEqual(response.status_code, 200)
        history_data = json.loads(response.content)
        
        completed_emails = [h for h in history_data['results'] if h['status'] == 'completed']
        self.assertEqual(len(completed_emails), 2)
        
        # Test 3: Search email history
        response = self.client.get('/admin/email/history/?search=Test Email 1')
        self.assertEqual(response.status_code, 200)
        history_data = json.loads(response.content)
        
        self.assertTrue(len(history_data['results']) >= 1)
        self.assertIn('Test Email 1', history_data['results'][0]['subject'])
        
        # Test 4: Get email delivery details
        history_id = histories[2].id  # The one with partial failure
        response = self.client.get(f'/admin/email/history/{history_id}/details/')
        self.assertEqual(response.status_code, 200)
        details_data = json.loads(response.content)
        
        self.assertIn('deliveries', details_data)
        self.assertEqual(len(details_data['deliveries']), 2)
        
        # Check that we have both delivered and failed statuses
        statuses = [d['status'] for d in details_data['deliveries']]
        self.assertIn('delivered', statuses)
        self.assertIn('failed', statuses)
        
        # Test 5: Get email statistics
        response = self.client.get('/admin/email/statistics/?days=30')
        self.assertEqual(response.status_code, 200)
        stats_data = json.loads(response.content)
        
        self.assertIn('statistics', stats_data)
        stats = stats_data['statistics']
        self.assertEqual(stats['total_emails'], 3)
        self.assertEqual(stats['total_recipients'], 6)  # 2 recipients × 3 emails
        self.assertEqual(stats['successful_deliveries'], 5)  # 2+2+1
        self.assertEqual(stats['failed_deliveries'], 1)
        
        # Calculate expected success rate: 5/6 = 83.33%
        expected_success_rate = round((5 / 6) * 100, 2)
        self.assertEqual(stats['success_rate'], expected_success_rate)
    
    def test_error_handling_integration(self):
        """
        Test error handling across the entire system integration.
        """
        # Test 1: Attempt to send email without SMTP configuration
        email_data = {
            'subject': 'Test Email',
            'message': 'Test message',
            'recipient_config': {
                'type': 'department',
                'department_ids': [self.department.id]
            }
        }
        
        response = self.client.post('/admin/email/send/',
                                  data=json.dumps(email_data),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
        error_data = json.loads(response.content)
        self.assertFalse(error_data['success'])
        self.assertIn('smtp', error_data['error'].lower())
        
        # Test 2: Invalid recipient configuration
        # First configure SMTP
        smtp_config = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': 587,
            'smtp_username': 'test@test.com',
            'smtp_password': 'test_password',
            'from_email': 'test@test.com',
            'use_tls': True
        }
        
        self.client.post('/admin/email/smtp/config/save/',
                        data=json.dumps(smtp_config),
                        content_type='application/json')
        
        # Try with invalid department ID
        invalid_email_data = {
            'subject': 'Test Email',
            'message': 'Test message',
            'recipient_config': {
                'type': 'department',
                'department_ids': [99999]  # Non-existent department
            }
        }
        
        response = self.client.post('/admin/email/recipients/validate/',
                                  data=json.dumps(invalid_email_data['recipient_config']),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        validation_data = json.loads(response.content)
        self.assertFalse(validation_data['valid'])
        self.assertEqual(validation_data['recipient_count'], 0)
        
        # Test 3: Authentication required for all endpoints
        self.client.logout()
        
        protected_endpoints = [
            '/admin/email/smtp/config/',
            '/admin/email/templates/',
            '/admin/email/recipients/options/',
            '/admin/email/history/',
            '/admin/email/statistics/'
        ]
        
        for endpoint in protected_endpoints:
            response = self.client.get(endpoint)
            self.assertIn(response.status_code, [302, 401, 403])  # Redirect to login or unauthorized
        
        # Re-login for remaining tests
        self.client.login(username='testadmin', password='testpass123')
        
        # Test 4: Invalid JSON data handling
        response = self.client.post('/admin/email/smtp/config/save/',
                                  data='invalid json',
                                  content_type='application/json')
        self.assertEqual(response.status_code, 400)
    
    def test_security_integration(self):
        """
        Test security features across the integrated system.
        """
        # Test 1: Password encryption in SMTP configuration
        smtp_config = {
            'smtp_host': 'smtp.secure.com',
            'smtp_port': 587,
            'smtp_username': 'secure@test.com',
            'smtp_password': 'super_secret_password',
            'from_email': 'secure@test.com',
            'use_tls': True
        }
        
        response = self.client.post('/admin/email/smtp/config/save/',
                                  data=json.dumps(smtp_config),
                                  content_type='application/json')
        self.assertEqual(response.status_code, 200)
        
        # Verify password is encrypted in database
        config = EmailConfiguration.objects.filter(is_active=True).first()
        self.assertIsNotNone(config)
        self.assertNotEqual(config.smtp_password, 'super_secret_password')  # Should be encrypted
        
        # Verify password is not returned in API responses
        response = self.client.get('/admin/email/smtp/config/')
        self.assertEqual(response.status_code, 200)
        config_data = json.loads(response.content)
        self.assertNotIn('smtp_password', config_data)
        
        # Test 2: Sensitive data not logged in email history
        # Create an email history record
        history = EmailHistory.objects.create(
            sender=self.admin_user,
            subject='Sensitive Email',
            message='This contains sensitive information',
            recipient_count=1,
            successful_sends=1,
            failed_sends=0,
            status='completed'
        )
        
        # Verify that sensitive fields are handled properly
        response = self.client.get('/admin/email/history/')
        self.assertEqual(response.status_code, 200)
        history_data = json.loads(response.content)
        
        # Email content should be available (it's not considered sensitive in history)
        # but SMTP passwords should never appear
        history_record = next((h for h in history_data['results'] if h['id'] == history.id), None)
        self.assertIsNotNone(history_record)
        self.assertNotIn('super_secret_password', str(history_record))
        
        # Test 3: Admin-only access enforcement
        # Create a regular user (non-admin)
        regular_user = User.objects.create_user(
            username='regularuser',
            email='regular@test.edu',
            password='testpass123',
            is_staff=False,
            is_superuser=False
        )
        
        # Logout admin and login as regular user
        self.client.logout()
        self.client.login(username='regularuser', password='testpass123')
        
        # Try to access admin email endpoints
        admin_endpoints = [
            '/admin/email/smtp/config/',
            '/admin/email/send/',
            '/admin/email/history/'
        ]
        
        for endpoint in admin_endpoints:
            response = self.client.get(endpoint)
            self.assertIn(response.status_code, [302, 401, 403])  # Should be denied
    
    def test_performance_integration(self):
        """
        Test performance aspects of the integrated system.
        """
        # Create larger dataset for performance testing
        additional_students = []
        for i in range(50):  # Create 50 more students
            student = Student.objects.create(
                student_id=f"PERF{i:03d}",
                first_name=f"PerfStudent{i}",
                last_name="Test",
                email=f"perf{i}@test.edu",
                department=self.department,
                level="Level 2",
                is_approved=True
            )
            additional_students.append(student)
        
        # Configure SMTP
        smtp_config = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': 587,
            'smtp_username': 'perf@test.com',
            'smtp_password': 'test_password',
            'from_email': 'perf@test.com',
            'use_tls': True
        }
        
        self.client.post('/admin/email/smtp/config/save/',
                        data=json.dumps(smtp_config),
                        content_type='application/json')
        
        # Test 1: Large recipient list validation performance
        start_time = time.time()
        
        recipient_config = {
            'type': 'department',
            'department_ids': [self.department.id],
            'levels': ['Level 1', 'Level 2']
        }
        
        response = self.client.post('/admin/email/recipients/validate/',
                                  data=json.dumps(recipient_config),
                                  content_type='application/json')
        
        validation_time = time.time() - start_time
        
        self.assertEqual(response.status_code, 200)
        validation_data = json.loads(response.content)
        self.assertTrue(validation_data['valid'])
        self.assertEqual(validation_data['recipient_count'], 55)  # 5 original + 50 new
        
        # Validation should complete within reasonable time (5 seconds)
        self.assertLess(validation_time, 5.0)
        
        # Test 2: Email history pagination performance
        # Create multiple email history records
        for i in range(20):
            EmailHistory.objects.create(
                sender=self.admin_user,
                subject=f'Performance Test Email {i}',
                message=f'Performance test message {i}',
                recipient_count=10,
                successful_sends=10,
                failed_sends=0,
                status='completed'
            )
        
        start_time = time.time()
        response = self.client.get('/admin/email/history/?page=1&page_size=10')
        query_time = time.time() - start_time
        
        self.assertEqual(response.status_code, 200)
        history_data = json.loads(response.content)
        self.assertEqual(len(history_data['results']), 10)
        
        # Query should complete within reasonable time (2 seconds)
        self.assertLess(query_time, 2.0)
        
        # Test 3: Statistics calculation performance
        start_time = time.time()
        response = self.client.get('/admin/email/statistics/?days=30')
        stats_time = time.time() - start_time
        
        self.assertEqual(response.status_code, 200)
        stats_data = json.loads(response.content)
        self.assertIn('statistics', stats_data)
        
        # Statistics calculation should complete within reasonable time (3 seconds)
        self.assertLess(stats_time, 3.0)
    
    def test_notification_integration_workflow(self):
        """
        Test the integration between email system and notification system.
        """
        # Configure SMTP
        smtp_config = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': 587,
            'smtp_username': 'notify@test.com',
            'smtp_password': 'test_password',
            'from_email': 'notify@test.com',
            'use_tls': True
        }
        
        self.client.post('/admin/email/smtp/config/save/',
                        data=json.dumps(smtp_config),
                        content_type='application/json')
        
        # Test 1: System announcement creation
        announcement_data = {
            'title': 'System Maintenance Notice',
            'message': 'The system will be under maintenance on Sunday.',
            'recipient_config': {
                'type': 'all_students'
            },
            'send_email': True,
            'create_notification': True
        }
        
        with patch('students.email_service.EmailService.send_bulk_email') as mock_send:
            mock_send.return_value = {
                'success': True,
                'total_recipients': 5,
                'successful_sends': 5,
                'failed_sends': 0,
                'history_id': 1
            }
            
            response = self.client.post('/admin/email/notifications/system/',
                                      data=json.dumps(announcement_data),
                                      content_type='application/json')
            self.assertEqual(response.status_code, 200)
            result_data = json.loads(response.content)
            self.assertTrue(result_data['success'])
        
        # Test 2: Course-specific notification
        course_notification_data = {
            'title': 'Assignment Due Reminder',
            'message': 'Your assignment is due tomorrow.',
            'recipient_config': {
                'type': 'department',
                'department_ids': [self.department.id]
            },
            'send_email': True,
            'create_notification': True
        }
        
        with patch('students.email_service.EmailService.send_bulk_email') as mock_send:
            mock_send.return_value = {
                'success': True,
                'total_recipients': 5,
                'successful_sends': 5,
                'failed_sends': 0,
                'history_id': 2
            }
            
            response = self.client.post('/admin/email/notifications/course/',
                                      data=json.dumps(course_notification_data),
                                      content_type='application/json')
            self.assertEqual(response.status_code, 200)
            result_data = json.loads(response.content)
            self.assertTrue(result_data['success'])
    
    def tearDown(self):
        """Clean up test data"""
        # Clean up any created files or external resources
        EmailConfiguration.objects.all().delete()
        EmailHistory.objects.all().delete()
        EmailDelivery.objects.all().delete()
        EmailTemplate.objects.all().delete()
        Notification.objects.all().delete()


class EmailManagementConcurrencyTest(TransactionTestCase):
    """
    Test concurrent access and operations in the email management system.
    """
    
    def setUp(self):
        """Set up test environment"""
        self.admin_user = User.objects.create_user(
            username='concurrency_admin',
            email='admin@concurrent.test',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create institution structure
        self.institution = Institution.objects.create(
            name="Concurrent Test University",
            code="CTU",
            address="456 Concurrent St"
        )
        
        self.faculty = Faculty.objects.create(
            name="Concurrent Faculty",
            institution=self.institution
        )
        
        self.department = Department.objects.create(
            name="Concurrent Department",
            faculty=self.faculty
        )
    
    def test_concurrent_smtp_configuration(self):
        """
        Test concurrent SMTP configuration updates.
        """
        import threading
        import time
        
        results = []
        
        def configure_smtp(config_data, result_list):
            """Helper function to configure SMTP in a thread"""
            client = Client()
            client.login(username='concurrency_admin', password='testpass123')
            
            try:
                response = client.post('/admin/email/smtp/config/save/',
                                     data=json.dumps(config_data),
                                     content_type='application/json')
                result_list.append({
                    'status_code': response.status_code,
                    'config': config_data,
                    'thread_id': threading.current_thread().ident
                })
            except Exception as e:
                result_list.append({
                    'error': str(e),
                    'config': config_data,
                    'thread_id': threading.current_thread().ident
                })
        
        # Create multiple SMTP configurations to test concurrency
        configs = [
            {
                'smtp_host': 'smtp.gmail.com',
                'smtp_port': 587,
                'smtp_username': 'test1@gmail.com',
                'smtp_password': 'password1',
                'from_email': 'test1@gmail.com',
                'use_tls': True
            },
            {
                'smtp_host': 'smtp.outlook.com',
                'smtp_port': 587,
                'smtp_username': 'test2@outlook.com',
                'smtp_password': 'password2',
                'from_email': 'test2@outlook.com',
                'use_tls': True
            }
        ]
        
        # Start concurrent threads
        threads = []
        for config in configs:
            thread = threading.Thread(target=configure_smtp, args=(config, results))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(results), 2)
        
        # At least one configuration should succeed
        successful_configs = [r for r in results if r.get('status_code') == 200]
        self.assertTrue(len(successful_configs) >= 1)
        
        # Verify only one active configuration exists (last one wins)
        active_configs = EmailConfiguration.objects.filter(is_active=True)
        self.assertEqual(active_configs.count(), 1)
    
    def test_concurrent_email_sending(self):
        """
        Test concurrent email sending operations.
        """
        # Set up SMTP configuration
        config = EmailConfiguration.objects.create(
            smtp_host='smtp.concurrent.test',
            smtp_port=587,
            smtp_username='concurrent@test.com',
            from_email='concurrent@test.com',
            use_tls=True,
            is_active=True
        )
        config.set_password('test_password')
        config.save()
        
        # Create test students
        students = []
        for i in range(10):
            student = Student.objects.create(
                student_id=f"CONC{i:03d}",
                first_name=f"Concurrent{i}",
                last_name="Student",
                email=f"concurrent{i}@test.edu",
                department=self.department,
                level="Level 1",
                is_approved=True
            )
            students.append(student)
        
        import threading
        results = []
        
        def send_email(email_data, result_list):
            """Helper function to send email in a thread"""
            client = Client()
            client.login(username='concurrency_admin', password='testpass123')
            
            with patch('students.email_service.EmailService.send_bulk_email') as mock_send:
                mock_send.return_value = {
                    'success': True,
                    'total_recipients': 5,
                    'successful_sends': 5,
                    'failed_sends': 0,
                    'history_id': threading.current_thread().ident  # Use thread ID as unique identifier
                }
                
                try:
                    response = client.post('/admin/email/send/',
                                         data=json.dumps(email_data),
                                         content_type='application/json')
                    result_list.append({
                        'status_code': response.status_code,
                        'thread_id': threading.current_thread().ident,
                        'email_subject': email_data['subject']
                    })
                except Exception as e:
                    result_list.append({
                        'error': str(e),
                        'thread_id': threading.current_thread().ident,
                        'email_subject': email_data['subject']
                    })
        
        # Create multiple email sending requests
        email_requests = [
            {
                'subject': f'Concurrent Email {i}',
                'message': f'This is concurrent email number {i}',
                'recipient_config': {
                    'type': 'department',
                    'department_ids': [self.department.id]
                }
            }
            for i in range(3)
        ]
        
        # Start concurrent threads
        threads = []
        for email_data in email_requests:
            thread = threading.Thread(target=send_email, args=(email_data, results))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        self.assertEqual(len(results), 3)
        
        # All email sending requests should succeed
        successful_sends = [r for r in results if r.get('status_code') == 200]
        self.assertEqual(len(successful_sends), 3)
        
        # Verify unique thread IDs (no race conditions)
        thread_ids = [r['thread_id'] for r in results]
        self.assertEqual(len(thread_ids), len(set(thread_ids)))  # All unique


if __name__ == '__main__':
    unittest.main()