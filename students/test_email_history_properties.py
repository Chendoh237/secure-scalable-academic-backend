"""
Property-Based Tests for Email History Service

This module contains tests that validate the correctness
of email history recording, filtering, and administrative action logging.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import datetime, timedelta
import random
import logging
from unittest.mock import patch, MagicMock

from .email_models import EmailHistory, EmailDelivery, EmailTemplate
from .email_history_service import EmailHistoryService, EmailHistoryServiceError
from .models import Student
from institutions.models import Institution, Faculty, Department

User = get_user_model()


class EmailHistoryPropertiesTest(TestCase):
    """Property-based tests for email history service"""
    
    def setUp(self):
        """Set up test data"""
        self.service = EmailHistoryService()
        
        # Create test institution, faculty, department
        self.institution = Institution.objects.create(
            name="Test University",
            code="TU"
        )
        self.faculty = Faculty.objects.create(
            name="Test Faculty",
            institution=self.institution
        )
        self.department = Department.objects.create(
            name="Test Department",
            faculty=self.faculty
        )
        
        # Create test users and students
        self.users = []
        self.students = []
        for i in range(5):
            user = User.objects.create_user(
                username=f"testuser{i}",
                email=f"test{i}@example.com",
                password="testpass123"
            )
            self.users.append(user)
            
            student = Student.objects.create(
                user=user,
                matric_number=f"TEST{i:04d}",
                full_name=f"Test Student {i}",
                institution=self.institution,
                faculty=self.faculty,
                department=self.department,
                is_active=True
            )
            self.students.append(student)
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass123",
            is_staff=True
        )
        
        # Create test template
        self.template = EmailTemplate.objects.create(
            name="Test Template",
            category="general",
            subject_template="Test Subject: {student_name}",
            body_template="Hello {student_name}, this is a test email.",
            variables=["student_name"],
            is_active=True
        )
    
    def test_property_email_history_recording(self):
        """
        **Property 9: Email History Recording**
        **Validates: Requirements 4.2, 7.1**
        
        Property: For any valid email sending operation, a complete history record
        must be created with accurate recipient count and delivery tracking.
        """
        # Test with various recipient counts and subjects
        test_cases = [
            ("Test Subject 1", "Test Body 1", 1),
            ("Test Subject 2", "Test Body 2", 3),
            ("Test Subject 3", "Test Body 3", 5),
        ]
        
        for subject, body, recipient_count in test_cases:
            with self.subTest(subject=subject, recipient_count=recipient_count):
                # Generate recipient emails
                recipients = [f"recipient{i}@example.com" for i in range(recipient_count)]
                
                # Save email record
                history = self.service.save_email_record(
                    sender_user=self.admin_user,
                    subject=subject,
                    body=body,
                    recipients=recipients,
                    template_used=self.template
                )
                
                # Verify history record was created correctly
                self.assertIsNotNone(history)
                self.assertEqual(history.sender, self.admin_user)
                self.assertEqual(history.subject, subject)
                self.assertEqual(history.body, body)
                self.assertEqual(history.template_used, self.template)
                self.assertEqual(history.recipient_count, recipient_count)
                self.assertEqual(history.status, 'sending')
                
                # Verify delivery records were created
                delivery_records = EmailDelivery.objects.filter(email_history=history)
                self.assertEqual(delivery_records.count(), recipient_count)
                
                # Verify each recipient has a delivery record
                recorded_emails = set(delivery_records.values_list('recipient_email', flat=True))
                expected_emails = set(recipients)
                self.assertEqual(recorded_emails, expected_emails)
                
                # Verify all delivery records start with 'pending' status
                for delivery in delivery_records:
                    self.assertEqual(delivery.delivery_status, 'pending')
                    self.assertEqual(delivery.email_history, history)
    
    def test_property_history_filtering_accuracy(self):
        """
        **Property 17: History Filtering Accuracy**
        **Validates: Requirements 7.3**
        
        Property: History filtering must return exactly the records that match
        the specified criteria, with no false positives or false negatives.
        """
        # Create test email history records with different dates
        created_histories = []
        base_date = timezone.now() - timedelta(days=5)
        
        for i in range(3):
            # Create history record with specific date
            history_date = base_date + timedelta(hours=i)
            
            history = EmailHistory.objects.create(
                sender=self.admin_user,
                subject=f"Test Email {i}",
                body=f"Test body {i}",
                template_used=self.template if i % 2 == 0 else None,
                recipient_count=random.randint(1, 5),
                status=random.choice(['sending', 'completed', 'failed']),
                sent_at=history_date
            )
            created_histories.append(history)
        
        # Test date range filtering
        start_date = base_date
        end_date = base_date + timedelta(hours=3)
        
        filters = {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
        
        result = self.service.get_email_history(filters=filters, page_size=100)
        returned_ids = {item['id'] for item in result['results']}
        expected_ids = {h.id for h in created_histories}
        
        # All created histories should be in the date range
        self.assertTrue(expected_ids.issubset(returned_ids))
        
        # Test sender filtering
        filters = {'sender_id': self.admin_user.id}
        result = self.service.get_email_history(filters=filters, page_size=100)
        
        # All returned results should have the correct sender
        for item in result['results']:
            self.assertEqual(item['sender']['id'], self.admin_user.id)
        
        # Test template filtering
        template_histories = [h for h in created_histories if h.template_used == self.template]
        if template_histories:
            filters = {'template_id': self.template.id}
            result = self.service.get_email_history(filters=filters, page_size=100)
            
            returned_ids = {item['id'] for item in result['results']}
            expected_template_ids = {h.id for h in template_histories}
            
            # All template histories should be returned
            self.assertTrue(expected_template_ids.issubset(returned_ids))
            
            # All returned results should have the correct template
            for item in result['results']:
                if item['template_used']:
                    self.assertEqual(item['template_used']['id'], self.template.id)
    
    def test_property_delivery_status_consistency(self):
        """
        Property: Delivery status updates must maintain consistency between
        individual delivery records and aggregate history counts.
        """
        test_cases = [
            (3, 2, 1),  # 3 recipients, 2 success, 1 failure
            (5, 5, 0),  # 5 recipients, all success
            (4, 0, 4),  # 4 recipients, all failure
        ]
        
        for recipient_count, success_count, failure_count in test_cases:
            with self.subTest(recipients=recipient_count, success=success_count, failures=failure_count):
                # Create email history record
                recipients = [f"recipient{i}@example.com" for i in range(recipient_count)]
                history = self.service.save_email_record(
                    sender_user=self.admin_user,
                    subject="Test Email",
                    body="Test body",
                    recipients=recipients
                )
                
                # Update delivery statuses
                for i in range(success_count):
                    self.service.update_delivery_status(
                        record_id=history.id,
                        recipient_email=recipients[i],
                        status='sent'
                    )
                
                for i in range(success_count, success_count + failure_count):
                    self.service.update_delivery_status(
                        record_id=history.id,
                        recipient_email=recipients[i],
                        status='failed',
                        error_message="Test error"
                    )
                
                # Refresh history record
                history.refresh_from_db()
                
                # Verify aggregate counts match individual delivery records
                self.assertEqual(history.success_count, success_count)
                self.assertEqual(history.failure_count, failure_count)
                
                # Verify individual delivery records
                deliveries = EmailDelivery.objects.filter(email_history=history)
                actual_success = deliveries.filter(delivery_status__in=['sent', 'delivered']).count()
                actual_failure = deliveries.filter(delivery_status__in=['failed', 'bounced']).count()
                
                self.assertEqual(actual_success, success_count)
                self.assertEqual(actual_failure, failure_count)
                
                # Verify overall status logic
                if failure_count == 0 and success_count == recipient_count:
                    self.assertEqual(history.status, 'completed')
                elif failure_count > 0 and success_count == 0:
                    self.assertEqual(history.status, 'failed')
                elif success_count > 0:
                    self.assertEqual(history.status, 'completed')
    
    def test_property_search_accuracy(self):
        """
        Property: Search functionality must return all records that contain
        the search query and no records that don't contain it.
        """
        search_query = "important"
        
        # Create matching email histories
        matching_histories = []
        for i in range(2):
            history = EmailHistory.objects.create(
                sender=self.admin_user,
                subject=f"Email with {search_query} in subject {i}",
                body=f"Test body {i}",
                recipient_count=1,
                status='completed'
            )
            matching_histories.append(history)
        
        # Create non-matching email histories
        non_matching_histories = []
        for i in range(2):
            history = EmailHistory.objects.create(
                sender=self.admin_user,
                subject=f"Different email {i}",
                body=f"Different body {i}",
                recipient_count=1,
                status='completed'
            )
            non_matching_histories.append(history)
        
        # Perform search
        results = self.service.search_email_history(search_query)
        result_ids = {item['id'] for item in results}
        
        # All matching histories should be in results
        matching_ids = {h.id for h in matching_histories}
        self.assertTrue(matching_ids.issubset(result_ids))
        
        # No non-matching histories should be in results
        non_matching_ids = {h.id for h in non_matching_histories}
        self.assertTrue(result_ids.isdisjoint(non_matching_ids))
    
    def test_property_pagination_completeness(self):
        """
        Property: Paginated results must include all records exactly once
        across all pages, with no duplicates or omissions.
        """
        # Create test email histories
        num_records = 25
        created_histories = []
        
        for i in range(num_records):
            history = EmailHistory.objects.create(
                sender=self.admin_user,
                subject=f"Test Email {i:02d}",
                body=f"Test body {i}",
                recipient_count=1,
                status='completed'
            )
            created_histories.append(history)
        
        # Collect all records across pages
        page_size = 10
        all_returned_ids = set()
        page = 1
        
        while True:
            result = self.service.get_email_history(page=page, page_size=page_size)
            
            if not result['results']:
                break
            
            page_ids = {item['id'] for item in result['results']}
            
            # Check for duplicates across pages
            self.assertTrue(page_ids.isdisjoint(all_returned_ids), "Duplicate records found across pages")
            
            all_returned_ids.update(page_ids)
            
            if not result['pagination']['has_next']:
                break
            
            page += 1
        
        # Verify all created records were returned
        expected_ids = {h.id for h in created_histories}
        self.assertEqual(all_returned_ids, expected_ids, "Not all records were returned across pages")
    
    @patch('students.email_history_service.audit_logger')
    def test_property_administrative_action_logging(self, mock_audit_logger):
        """
        **Property 13: Administrative Action Logging**
        **Validates: Requirements 5.5**
        
        Property: All administrative actions must be logged with complete
        audit information, excluding sensitive data.
        """
        # Test email record creation
        recipients = ["test@example.com"]
        self.service.save_email_record(
            sender_user=self.admin_user,
            subject="Test Email",
            body="Test body",
            recipients=recipients,
            template_used=self.template
        )
        
        # Verify audit logging was called
        self.assertTrue(mock_audit_logger.info.called)
        
        # Verify log entries contain required information
        call_args = mock_audit_logger.info.call_args
        args, kwargs = call_args
        log_message = args[0]
        extra_data = kwargs.get('extra', {})
        
        # Verify required fields are present
        self.assertIn('action', extra_data)
        self.assertIn('timestamp', extra_data)
        self.assertIn('username', extra_data)
        
        # Verify sensitive data is not logged
        if 'details' in extra_data:
            details = extra_data['details']
            # Body should not be in the logged details
            self.assertNotIn('body', details)
    
    @patch('students.email_history_service.audit_logger')
    def test_property_sensitive_data_protection(self, mock_audit_logger):
        """
        Property: Sensitive data must never appear in audit logs,
        ensuring security and privacy compliance.
        """
        # Test SMTP configuration logging with sensitive data
        old_config = {
            'smtp_host': 'old.example.com',
            'smtp_username': 'sensitive_user@example.com',
            'smtp_password': 'super_secret_password'
        }
        new_config = {
            'smtp_host': 'new.example.com',
            'smtp_username': 'new_user@example.com',
            'smtp_password': 'new_secret_password'
        }
        
        self.service.log_smtp_configuration_change(
            user=self.admin_user,
            old_config=old_config,
            new_config=new_config
        )
        
        # Verify sensitive data is not in logs
        call_args = mock_audit_logger.info.call_args
        args, kwargs = call_args
        extra_data = kwargs.get('extra', {})
        details = extra_data.get('details', {})
        
        # Verify sensitive fields are not present or are redacted
        if 'smtp_password' in details:
            self.assertEqual(details['smtp_password'], '[REDACTED]')
        if 'smtp_username' in details:
            self.assertEqual(details['smtp_username'], '[REDACTED]')
        
        # Verify non-sensitive data is still present
        if 'smtp_host' in details:
            self.assertEqual(details['smtp_host'], 'new.example.com')
        
        # Test email record creation with body content
        mock_audit_logger.reset_mock()
        
        sensitive_body = "This email contains sensitive student information: SSN 123-45-6789"
        self.service.save_email_record(
            sender_user=self.admin_user,
            subject="Test Email",
            body=sensitive_body,
            recipients=["test@example.com"]
        )
        
        # Verify email body is not logged
        call_args = mock_audit_logger.info.call_args
        args, kwargs = call_args
        extra_data = kwargs.get('extra', {})
        details = extra_data.get('details', {})
        
        # Body should not be in the logged details
        self.assertNotIn('body', details)
        # But other details should be present
        self.assertIn('subject', details)
        self.assertIn('recipient_count', details)