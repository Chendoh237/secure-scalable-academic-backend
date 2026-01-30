"""
Property-Based Tests for Error Resilience in Bulk Operations

**Property 10: Error Resilience in Bulk Operations**
**Validates: Requirements 4.3, 4.5, 8.5**

This module contains property-based tests that verify the email management system
maintains resilience during bulk operations, continuing processing even when
individual operations fail and providing comprehensive error reporting.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock, side_effect
import smtplib
import socket
import random

from students.email_service import EmailService, EmailServiceError
from students.email_models import EmailConfiguration, EmailTemplate, EmailHistory, EmailDelivery

User = get_user_model()


@composite
def bulk_email_strategy(draw):
    """Generate bulk email test data"""
    # Generate a mix of valid and potentially problematic emails
    valid_emails = draw(st.lists(st.emails(), min_size=1, max_size=20))
    
    # Add some emails that might cause issues (for testing resilience)
    problematic_emails = draw(st.lists(
        st.sampled_from([
            'fail@example.com',  # Will be configured to fail
            'timeout@example.com',  # Will timeout
            'reject@example.com',  # Will be rejected
            'bounce@example.com'   # Will bounce
        ]),
        min_size=0,
        max_size=5
    ))
    
    all_emails = valid_emails + problematic_emails
    draw(st.randoms()).shuffle(all_emails)
    
    return {
        'emails': all_emails,
        'subject': draw(st.text(min_size=5, max_size=100)),
        'message': draw(st.text(min_size=10, max_size=1000)),
        'batch_size': draw(st.integers(min_value=1, max_value=10)),
        'expected_failures': len(problematic_emails)
    }


@composite
def smtp_failure_strategy(draw):
    """Generate SMTP failure scenarios for testing"""
    failure_type = draw(st.sampled_from([
        'authentication_error',
        'connection_error', 
        'recipient_refused',
        'data_error',
        'server_disconnected',
        'timeout',
        'intermittent_failure'
    ]))
    
    failure_rate = draw(st.floats(min_value=0.1, max_value=0.8))  # 10-80% failure rate
    
    return {
        'type': failure_type,
        'rate': failure_rate
    }


class TestBulkErrorResilience(TestCase):
    """Property-based tests for bulk operation error resilience"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = EmailService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test SMTP configuration
        self.smtp_config = {
            'smtp_host': 'smtp.test.com',
            'smtp_port': 587,
            'smtp_username': 'test@test.com',
            'smtp_password': 'password',
            'use_tls': True,
            'use_ssl': False,
            'from_email': 'test@test.com',
            'from_name': 'Test System'
        }
    
    @given(bulk_email_strategy())
    @settings(max_examples=20, deadline=10000)
    def test_property_bulk_operations_continue_on_individual_failures(self, email_data):
        """
        **Property 10: Error Resilience in Bulk Operations**
        **Validates: Requirements 4.3, 4.5, 8.5**
        
        Property: Bulk email operations SHALL continue processing all recipients
        even when individual deliveries fail, and SHALL provide comprehensive
        error reporting without losing data or corrupting state.
        """
        emails = email_data['emails']
        subject = email_data['subject']
        message = email_data['message']
        batch_size = email_data['batch_size']
        expected_failures = email_data['expected_failures']
        
        assume(len(emails) > 1)  # Need multiple emails for meaningful test
        
        # Mock SMTP to simulate mixed success/failure
        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value = mock_smtp
            
            # Configure mock to simulate failures for specific emails
            def simulate_send_message(msg):
                recipient = msg['To']
                if any(fail_email in recipient for fail_email in ['fail@', 'timeout@', 'reject@', 'bounce@']):
                    if 'fail@' in recipient:
                        raise smtplib.SMTPRecipientsRefused({recipient: (550, 'User unknown')})
                    elif 'timeout@' in recipient:
                        raise socket.timeout('Connection timed out')
                    elif 'reject@' in recipient:
                        raise smtplib.SMTPDataError(554, 'Message rejected')
                    elif 'bounce@' in recipient:
                        raise smtplib.SMTPException('Bounce detected')
                return True
            
            mock_smtp.send_message.side_effect = simulate_send_message
            
            # Mock SMTP configuration
            with patch.object(self.service, '_get_smtp_config') as mock_config:
                mock_config.return_value = self.smtp_config
                
                try:
                    result = self.service.send_bulk_email(
                        to_emails=emails,
                        subject=subject,
                        message=message,
                        sender_user=self.user,
                        batch_size=batch_size
                    )
                    
                    # Should complete processing despite failures
                    assert result.get('success', False), f"Bulk operation should complete: {result}"
                    
                    # Should report accurate counts
                    assert 'sent_count' in result, "Should report sent count"
                    assert 'failed_count' in result, "Should report failed count"
                    assert 'total_count' in result, "Should report total count"
                    
                    sent_count = result['sent_count']
                    failed_count = result['failed_count']
                    total_count = result['total_count']
                    
                    # Counts should be consistent
                    assert sent_count + failed_count == total_count, f"Counts should add up: {sent_count} + {failed_count} != {total_count}"
                    assert total_count == len(emails), f"Total should match input: {total_count} != {len(emails)}"
                    
                    # Should have processed all emails
                    assert total_count > 0, "Should have processed emails"
                    
                    # Should provide batch results
                    if 'batch_results' in result:
                        batch_results = result['batch_results']
                        assert isinstance(batch_results, list), "Batch results should be list"
                        assert len(batch_results) > 0, "Should have batch results"
                        
                        # Verify batch consistency
                        total_batch_sent = sum(br.get('sent', 0) for br in batch_results)
                        total_batch_failed = sum(br.get('failed', 0) for br in batch_results)
                        
                        assert total_batch_sent == sent_count, f"Batch sent count mismatch: {total_batch_sent} != {sent_count}"
                        assert total_batch_failed == failed_count, f"Batch failed count mismatch: {total_batch_failed} != {failed_count}"
                    
                    # Should provide failure details if there were failures
                    if failed_count > 0:
                        assert 'failed_recipients' in result, "Should provide failed recipients details"
                        failed_recipients = result['failed_recipients']
                        assert len(failed_recipients) == failed_count, f"Failed recipients count mismatch: {len(failed_recipients)} != {failed_count}"
                        
                        # Each failed recipient should have error details
                        for failed_recipient in failed_recipients:
                            assert 'email' in failed_recipient, "Failed recipient should have email"
                            assert 'error' in failed_recipient, "Failed recipient should have error message"
                            assert isinstance(failed_recipient['error'], str), "Error should be string"
                            assert len(failed_recipient['error']) > 0, "Error message should not be empty"
                    
                    # Should calculate success rate
                    if 'success_rate' in result:
                        expected_rate = (sent_count / total_count) * 100 if total_count > 0 else 0
                        actual_rate = result['success_rate']
                        assert abs(actual_rate - expected_rate) < 0.1, f"Success rate calculation error: {actual_rate} != {expected_rate}"
                    
                except Exception as e:
                    pytest.fail(f"Bulk operation should not raise unhandled exceptions: {str(e)}")
    
    @given(st.lists(st.emails(), min_size=5, max_size=15), smtp_failure_strategy())
    @settings(max_examples=15, deadline=8000)
    def test_property_bulk_operations_handle_smtp_failures_gracefully(self, emails, failure_config):
        """
        Property: Bulk operations SHALL handle various SMTP failures gracefully,
        continuing to process remaining recipients and providing detailed error information.
        """
        failure_type = failure_config['type']
        failure_rate = failure_config['rate']
        
        # Mock SMTP to simulate specific failure types
        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value = mock_smtp
            
            # Configure failure simulation based on type
            def simulate_smtp_failure(msg):
                if random.random() < failure_rate:
                    if failure_type == 'authentication_error':
                        raise smtplib.SMTPAuthenticationError(535, 'Authentication failed')
                    elif failure_type == 'connection_error':
                        raise smtplib.SMTPConnectError(421, 'Service not available')
                    elif failure_type == 'recipient_refused':
                        raise smtplib.SMTPRecipientsRefused({msg['To']: (550, 'User unknown')})
                    elif failure_type == 'data_error':
                        raise smtplib.SMTPDataError(554, 'Message rejected')
                    elif failure_type == 'server_disconnected':
                        raise smtplib.SMTPServerDisconnected('Connection lost')
                    elif failure_type == 'timeout':
                        raise socket.timeout('Operation timed out')
                    elif failure_type == 'intermittent_failure':
                        raise smtplib.SMTPException('Temporary failure')
                return True
            
            mock_smtp.send_message.side_effect = simulate_smtp_failure
            
            # Mock SMTP configuration
            with patch.object(self.service, '_get_smtp_config') as mock_config:
                mock_config.return_value = self.smtp_config
                
                try:
                    result = self.service.send_bulk_email(
                        to_emails=emails,
                        subject="Test Subject",
                        message="Test Message",
                        sender_user=self.user,
                        batch_size=3,
                        max_retries=2
                    )
                    
                    # Should complete processing
                    assert result.get('success', False), f"Should complete despite SMTP failures: {result}"
                    
                    # Should provide comprehensive results
                    assert 'sent_count' in result, "Should report sent count"
                    assert 'failed_count' in result, "Should report failed count"
                    assert 'total_count' in result, "Should report total count"
                    
                    # Should handle retries appropriately
                    if 'batch_results' in result:
                        batch_results = result['batch_results']
                        for batch_result in batch_results:
                            if 'attempts' in batch_result:
                                attempts = batch_result['attempts']
                                assert 1 <= attempts <= 3, f"Attempts should be reasonable: {attempts}"
                    
                    # Should provide error categorization
                    if result.get('failed_count', 0) > 0 and 'failed_recipients' in result:
                        failed_recipients = result['failed_recipients']
                        for failed_recipient in failed_recipients:
                            assert 'error_type' in failed_recipient or 'error' in failed_recipient, "Should categorize errors"
                    
                except Exception as e:
                    pytest.fail(f"Should handle SMTP failures gracefully: {str(e)}")
    
    @given(st.lists(st.emails(), min_size=3, max_size=10))
    @settings(max_examples=10, deadline=5000)
    def test_property_bulk_operations_maintain_data_integrity(self, emails):
        """
        Property: Bulk operations SHALL maintain data integrity, ensuring that
        email history and delivery records accurately reflect the actual sending results.
        """
        assume(len(emails) >= 3)
        
        # Mock SMTP with predictable failures
        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value = mock_smtp
            
            # Make every third email fail
            def predictable_failure(msg):
                recipient = msg['To']
                email_index = emails.index(recipient) if recipient in emails else 0
                if email_index % 3 == 0:  # Every third email fails
                    raise smtplib.SMTPRecipientsRefused({recipient: (550, 'User unknown')})
                return True
            
            mock_smtp.send_message.side_effect = predictable_failure
            
            # Mock SMTP configuration
            with patch.object(self.service, '_get_smtp_config') as mock_config:
                mock_config.return_value = self.smtp_config
                
                try:
                    result = self.service.send_bulk_email(
                        to_emails=emails,
                        subject="Data Integrity Test",
                        message="Testing data integrity",
                        sender_user=self.user,
                        batch_size=2
                    )
                    
                    # Calculate expected results
                    expected_failures = len([i for i, _ in enumerate(emails) if i % 3 == 0])
                    expected_successes = len(emails) - expected_failures
                    
                    # Verify result accuracy
                    assert result['sent_count'] == expected_successes, f"Sent count mismatch: {result['sent_count']} != {expected_successes}"
                    assert result['failed_count'] == expected_failures, f"Failed count mismatch: {result['failed_count']} != {expected_failures}"
                    assert result['total_count'] == len(emails), f"Total count mismatch: {result['total_count']} != {len(emails)}"
                    
                    # Verify email history was created
                    history_records = EmailHistory.objects.filter(sender=self.user, subject="Data Integrity Test")
                    assert history_records.exists(), "Email history should be created"
                    
                    history = history_records.first()
                    assert history.success_count == expected_successes, f"History success count mismatch: {history.success_count} != {expected_successes}"
                    assert history.failure_count == expected_failures, f"History failure count mismatch: {history.failure_count} != {expected_failures}"
                    
                    # Verify delivery records
                    delivery_records = EmailDelivery.objects.filter(email_history=history)
                    assert delivery_records.count() == len(emails), f"Should have delivery record for each email: {delivery_records.count()} != {len(emails)}"
                    
                    sent_deliveries = delivery_records.filter(delivery_status='sent')
                    failed_deliveries = delivery_records.filter(delivery_status='failed')
                    
                    assert sent_deliveries.count() == expected_successes, f"Sent delivery records mismatch: {sent_deliveries.count()} != {expected_successes}"
                    assert failed_deliveries.count() == expected_failures, f"Failed delivery records mismatch: {failed_deliveries.count()} != {expected_failures}"
                    
                    # Verify failed deliveries have error messages
                    for failed_delivery in failed_deliveries:
                        assert failed_delivery.error_message, "Failed deliveries should have error messages"
                        assert len(failed_delivery.error_message) > 0, "Error message should not be empty"
                    
                except Exception as e:
                    pytest.fail(f"Data integrity test should not fail: {str(e)}")
    
    def test_property_bulk_operations_handle_concurrent_access(self):
        """
        Property: Bulk operations SHALL handle concurrent access safely,
        preventing data corruption when multiple bulk operations run simultaneously.
        """
        emails1 = ['user1@example.com', 'user2@example.com']
        emails2 = ['user3@example.com', 'user4@example.com']
        
        # Mock SMTP
        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value = mock_smtp
            mock_smtp.send_message.return_value = True
            
            # Mock SMTP configuration
            with patch.object(self.service, '_get_smtp_config') as mock_config:
                mock_config.return_value = self.smtp_config
                
                try:
                    # Simulate concurrent operations
                    result1 = self.service.send_bulk_email(
                        to_emails=emails1,
                        subject="Concurrent Test 1",
                        message="Testing concurrent access 1",
                        sender_user=self.user
                    )
                    
                    result2 = self.service.send_bulk_email(
                        to_emails=emails2,
                        subject="Concurrent Test 2", 
                        message="Testing concurrent access 2",
                        sender_user=self.user
                    )
                    
                    # Both operations should succeed
                    assert result1.get('success', False), "First operation should succeed"
                    assert result2.get('success', False), "Second operation should succeed"
                    
                    # Should have separate history records
                    history1 = EmailHistory.objects.filter(sender=self.user, subject="Concurrent Test 1")
                    history2 = EmailHistory.objects.filter(sender=self.user, subject="Concurrent Test 2")
                    
                    assert history1.exists(), "Should have history for first operation"
                    assert history2.exists(), "Should have history for second operation"
                    assert history1.first().id != history2.first().id, "Should have separate history records"
                    
                    # Should have correct delivery records for each
                    deliveries1 = EmailDelivery.objects.filter(email_history=history1.first())
                    deliveries2 = EmailDelivery.objects.filter(email_history=history2.first())
                    
                    assert deliveries1.count() == len(emails1), "Should have correct deliveries for first operation"
                    assert deliveries2.count() == len(emails2), "Should have correct deliveries for second operation"
                    
                except Exception as e:
                    pytest.fail(f"Concurrent access test should not fail: {str(e)}")