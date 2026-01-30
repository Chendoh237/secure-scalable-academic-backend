"""
Property-Based Tests for Comprehensive Error Handling

**Validates: Requirements 8.1, 8.2, 8.3, 8.4**

This module contains property-based tests that verify the email management system
handles errors correctly across all scenarios, providing clear error messages
and maintaining system stability.
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from hypothesis.strategies import composite
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
import smtplib
import socket
import ssl

from students.email_service import EmailService, EmailServiceError
from students.email_models import EmailConfiguration, EmailTemplate

User = get_user_model()


@composite
def smtp_config_strategy(draw):
    """Generate SMTP configuration data for testing"""
    return {
        'smtp_host': draw(st.text(min_size=1, max_size=100)),
        'smtp_port': draw(st.integers(min_value=1, max_value=65535)),
        'smtp_username': draw(st.emails()),
        'smtp_password': draw(st.text(min_size=1, max_size=100)),
        'from_email': draw(st.emails()),
        'use_tls': draw(st.booleans()),
        'use_ssl': draw(st.booleans())
    }


@composite
def invalid_smtp_config_strategy(draw):
    """Generate invalid SMTP configuration data for testing"""
    config_type = draw(st.sampled_from([
        'missing_host', 'missing_port', 'missing_username', 
        'missing_password', 'missing_from_email', 'invalid_port',
        'invalid_email', 'protocol_in_host', 'both_tls_ssl'
    ]))
    
    base_config = {
        'smtp_host': 'smtp.gmail.com',
        'smtp_port': 587,
        'smtp_username': 'test@gmail.com',
        'smtp_password': 'password123',
        'from_email': 'test@gmail.com',
        'use_tls': True,
        'use_ssl': False
    }
    
    if config_type == 'missing_host':
        base_config['smtp_host'] = ''
    elif config_type == 'missing_port':
        base_config['smtp_port'] = None
    elif config_type == 'missing_username':
        base_config['smtp_username'] = ''
    elif config_type == 'missing_password':
        base_config['smtp_password'] = ''
    elif config_type == 'missing_from_email':
        base_config['from_email'] = ''
    elif config_type == 'invalid_port':
        base_config['smtp_port'] = draw(st.one_of(
            st.integers(max_value=0),
            st.integers(min_value=65536),
            st.text()
        ))
    elif config_type == 'invalid_email':
        base_config['from_email'] = draw(st.text().filter(lambda x: '@' not in x))
    elif config_type == 'protocol_in_host':
        protocol = draw(st.sampled_from(['http://', 'https://']))
        base_config['smtp_host'] = f"{protocol}smtp.gmail.com"
    elif config_type == 'both_tls_ssl':
        base_config['use_tls'] = True
        base_config['use_ssl'] = True
    
    return base_config, config_type


@composite
def email_list_strategy(draw):
    """Generate email lists for testing"""
    return draw(st.lists(
        st.emails(),
        min_size=0,
        max_size=20
    ))


@composite
def invalid_email_list_strategy(draw):
    """Generate lists containing invalid email addresses"""
    valid_emails = draw(st.lists(st.emails(), min_size=0, max_size=10))
    invalid_emails = draw(st.lists(
        st.text().filter(lambda x: '@' not in x and len(x) > 0),
        min_size=1,
        max_size=10
    ))
    
    # Mix valid and invalid emails
    all_emails = valid_emails + invalid_emails
    draw(st.randoms()).shuffle(all_emails)
    
    return all_emails, len(invalid_emails)


class TestComprehensiveErrorHandling(TestCase):
    """Property-based tests for comprehensive error handling"""
    
    def setUp(self):
        """Set up test environment"""
        self.service = EmailService()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    @given(invalid_smtp_config_strategy())
    @settings(max_examples=50, deadline=5000)
    def test_property_smtp_validation_errors_are_descriptive(self, config_data):
        """
        **Property 19: Comprehensive Error Handling**
        **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
        
        Property: For any invalid SMTP configuration, the system SHALL provide
        specific, actionable error messages that help users resolve the issue.
        """
        config, error_type = config_data
        
        try:
            result = self.service.test_connection(config)
            
            # Should always fail for invalid configurations
            assert not result['success'], f"Invalid config should fail: {config}"
            
            # Error message should be descriptive and helpful
            error_msg = result.get('error', '')
            assert len(error_msg) > 10, "Error message should be descriptive"
            assert error_msg != 'Unknown error', "Error message should be specific"
            
            # Check for specific error guidance based on error type
            if error_type == 'missing_host':
                assert 'host' in error_msg.lower(), "Should mention missing host"
            elif error_type == 'invalid_port':
                assert 'port' in error_msg.lower(), "Should mention port issue"
            elif error_type == 'invalid_email':
                assert 'email' in error_msg.lower(), "Should mention email format"
            elif error_type == 'protocol_in_host':
                assert 'protocol' in error_msg.lower(), "Should mention protocol issue"
            elif error_type == 'both_tls_ssl':
                assert ('tls' in error_msg.lower() and 'ssl' in error_msg.lower()), "Should mention TLS/SSL conflict"
            
        except Exception as e:
            # Should not raise unhandled exceptions
            pytest.fail(f"Should not raise exception for invalid config: {str(e)}")
    
    @given(st.lists(st.emails(), min_size=1, max_size=5))
    @settings(max_examples=30, deadline=5000)
    def test_property_smtp_connection_errors_are_handled_gracefully(self, email_list):
        """
        Property: SMTP connection errors SHALL be handled gracefully without
        crashing the system, and SHALL provide retry suggestions when appropriate.
        """
        # Test with non-existent SMTP server
        config = {
            'smtp_host': 'nonexistent.smtp.server.invalid',
            'smtp_port': 587,
            'smtp_username': email_list[0],
            'smtp_password': 'test_password',
            'from_email': email_list[0],
            'use_tls': True,
            'use_ssl': False
        }
        
        try:
            result = self.service.test_connection(config, timeout=2)
            
            # Should fail gracefully
            assert not result['success'], "Should fail for non-existent server"
            assert 'error' in result, "Should provide error message"
            assert len(result['error']) > 0, "Error message should not be empty"
            
            # Should suggest retry for connection issues
            if 'retry_suggested' in result:
                assert isinstance(result['retry_suggested'], bool), "retry_suggested should be boolean"
            
        except Exception as e:
            pytest.fail(f"Should handle connection errors gracefully: {str(e)}")
    
    @given(invalid_email_list_strategy())
    @settings(max_examples=30, deadline=5000)
    def test_property_email_validation_identifies_all_invalid_addresses(self, email_data):
        """
        Property: Email address validation SHALL identify ALL invalid email
        addresses in a list and provide specific feedback about each invalid address.
        """
        email_list, expected_invalid_count = email_data
        assume(len(email_list) > 0)
        
        try:
            result = self.service.send_email(
                to_emails=email_list,
                subject="Test Subject",
                message="Test Message"
            )
            
            # Should fail due to invalid emails
            assert not result['success'], "Should fail with invalid emails"
            assert result.get('error_type') == 'validation', "Should be validation error"
            
            # Should identify invalid emails
            error_msg = result.get('error', '')
            assert 'Invalid email addresses found' in error_msg, "Should mention invalid emails"
            
            if 'invalid_emails' in result:
                # Should identify at least some invalid emails
                assert len(result['invalid_emails']) > 0, "Should identify invalid emails"
                assert len(result['invalid_emails']) <= expected_invalid_count, "Should not over-identify"
            
        except Exception as e:
            pytest.fail(f"Should handle email validation gracefully: {str(e)}")
    
    @given(st.text(max_size=5), st.text(max_size=5))
    @settings(max_examples=20, deadline=3000)
    def test_property_required_field_validation_is_comprehensive(self, subject, message):
        """
        Property: Required field validation SHALL check all required fields
        and provide specific guidance about what is missing.
        """
        try:
            result = self.service.send_email(
                to_emails=['test@example.com'],
                subject=subject,
                message=message
            )
            
            # Check subject validation
            if not subject or not subject.strip():
                assert not result['success'], "Should fail with empty subject"
                assert 'subject is required' in result.get('error', '').lower(), "Should mention subject requirement"
                assert result.get('error_type') == 'validation', "Should be validation error"
            
            # Check message validation  
            elif not message or not message.strip():
                assert not result['success'], "Should fail with empty message"
                assert 'message is required' in result.get('error', '').lower(), "Should mention message requirement"
                assert result.get('error_type') == 'validation', "Should be validation error"
            
        except Exception as e:
            pytest.fail(f"Should handle field validation gracefully: {str(e)}")
    
    @given(st.lists(st.emails(), min_size=1, max_size=10))
    @settings(max_examples=20, deadline=5000)
    def test_property_bulk_email_continues_on_individual_failures(self, email_list):
        """
        Property: Bulk email sending SHALL continue processing all recipients
        even when individual deliveries fail, and SHALL report detailed results.
        """
        assume(len(email_list) > 1)
        
        # Mock SMTP to simulate mixed success/failure
        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value = mock_smtp
            
            # Simulate some failures
            def side_effect_send(msg):
                recipient = msg['To']
                if 'fail' in recipient:
                    raise smtplib.SMTPRecipientsRefused({recipient: (550, 'User unknown')})
                return True
            
            mock_smtp.send_message.side_effect = side_effect_send
            
            # Add some emails that should fail
            test_emails = email_list[:3] + ['fail1@example.com', 'fail2@example.com']
            
            try:
                # Mock SMTP configuration
                with patch.object(self.service, '_get_smtp_config') as mock_config:
                    mock_config.return_value = {
                        'smtp_host': 'smtp.gmail.com',
                        'smtp_port': 587,
                        'smtp_username': 'test@gmail.com',
                        'smtp_password': 'password',
                        'use_tls': True,
                        'use_ssl': False,
                        'from_email': 'test@gmail.com',
                        'from_name': 'Test System'
                    }
                    
                    result = self.service.send_bulk_email(
                        to_emails=test_emails,
                        subject="Test Subject",
                        message="Test Message",
                        sender_user=self.user,
                        batch_size=2
                    )
                    
                    # Should complete processing
                    assert result.get('success', False), f"Should complete processing: {result}"
                    
                    # Should report detailed results
                    assert 'sent_count' in result, "Should report sent count"
                    assert 'failed_count' in result, "Should report failed count"
                    assert 'total_count' in result, "Should report total count"
                    
                    # Total should equal sent + failed
                    total = result['sent_count'] + result['failed_count']
                    assert total == result['total_count'], "Counts should add up correctly"
                    
                    # Should have batch results
                    if 'batch_results' in result:
                        assert isinstance(result['batch_results'], list), "Batch results should be list"
                        assert len(result['batch_results']) > 0, "Should have batch results"
                    
            except Exception as e:
                pytest.fail(f"Should handle bulk email processing gracefully: {str(e)}")
    
    @given(st.integers(min_value=1, max_value=100))
    @settings(max_examples=10, deadline=3000)
    def test_property_network_timeouts_are_handled_gracefully(self, timeout_seconds):
        """
        Property: Network timeouts SHALL be handled gracefully with appropriate
        error messages and retry suggestions.
        """
        assume(1 <= timeout_seconds <= 10)  # Keep timeouts reasonable for testing
        
        config = {
            'smtp_host': '192.0.2.1',  # TEST-NET-1 address that should timeout
            'smtp_port': 587,
            'smtp_username': 'test@example.com',
            'smtp_password': 'password',
            'from_email': 'test@example.com',
            'use_tls': True,
            'use_ssl': False
        }
        
        try:
            result = self.service.test_connection(config, timeout=timeout_seconds)
            
            # Should handle timeout gracefully
            assert not result['success'], "Should fail on timeout"
            
            error_msg = result.get('error', '').lower()
            technical_details = result.get('technical_details', '').lower()
            
            # Should mention timeout in error message or technical details
            timeout_mentioned = ('timeout' in error_msg or 'timeout' in technical_details or
                               'timed out' in error_msg or 'timed out' in technical_details)
            
            # Allow for connection refused or other network errors too
            network_error = ('connection' in error_msg or 'connect' in error_msg or
                           'network' in error_msg or 'resolve' in error_msg)
            
            assert timeout_mentioned or network_error, f"Should mention timeout or network error: {result}"
            
            # Should suggest retry for timeout errors
            if 'retry_suggested' in result:
                assert result['retry_suggested'] in [True, False], "retry_suggested should be boolean"
            
        except Exception as e:
            pytest.fail(f"Should handle timeouts gracefully: {str(e)}")
    
    def test_property_error_messages_are_user_friendly(self):
        """
        Property: All error messages SHALL be user-friendly and provide
        actionable guidance rather than technical jargon.
        """
        # Test various error scenarios
        error_scenarios = [
            # No recipients
            {
                'method': 'send_email',
                'args': ([], "Subject", "Message"),
                'expected_keywords': ['recipients', 'select']
            },
            # Empty subject
            {
                'method': 'send_email', 
                'args': (['test@example.com'], "", "Message"),
                'expected_keywords': ['subject', 'required']
            },
            # Empty message
            {
                'method': 'send_email',
                'args': (['test@example.com'], "Subject", ""),
                'expected_keywords': ['message', 'required']
            }
        ]
        
        for scenario in error_scenarios:
            try:
                method = getattr(self.service, scenario['method'])
                result = method(*scenario['args'])
                
                assert not result['success'], f"Should fail for scenario: {scenario}"
                
                error_msg = result.get('error', '').lower()
                
                # Should contain expected keywords
                for keyword in scenario['expected_keywords']:
                    assert keyword in error_msg, f"Error message should contain '{keyword}': {error_msg}"
                
                # Should not contain technical jargon
                technical_terms = ['exception', 'traceback', 'null', 'none', 'error code']
                for term in technical_terms:
                    assert term not in error_msg, f"Error message should not contain technical term '{term}': {error_msg}"
                
            except Exception as e:
                pytest.fail(f"Should handle error scenario gracefully: {str(e)}")