"""
Property-Based Tests for Rate Limiting Compliance

This module contains property-based tests that validate the rate limiting
compliance properties of the email management system, ensuring that the
system respects SMTP server rate limits and prevents service disruption.

**Property 24: Rate Limiting Compliance**
For any email sending operation, the system should respect configured rate 
limits to comply with SMTP server restrictions.
**Validates: Requirements 10.2**
"""

import unittest
from hypothesis import given, strategies as st, settings, assume
from django.test import TestCase
from unittest.mock import patch, MagicMock
import time
from datetime import datetime, timedelta
from collections import defaultdict

from students.email_service import EmailService, EmailRateLimiter
from students.email_models import EmailConfiguration


class RateLimitingCompliancePropertiesTest(TestCase):
    """
    Property-based tests for rate limiting compliance.
    
    **Feature: email-management-system, Property 24: Rate Limiting Compliance**
    **Validates: Requirements 10.2**
    """
    
    def setUp(self):
        """Set up test environment"""
        self.email_service = EmailService()
        self.rate_limiter = EmailRateLimiter()
    
    @given(
        provider=st.sampled_from(['gmail', 'outlook', 'yahoo', 'office365', 'custom']),
        email_counts=st.lists(st.integers(min_value=1, max_value=50), min_size=1, max_size=20)
    )
    @settings(max_examples=30, deadline=5000)
    def test_rate_limit_enforcement_property(self, provider, email_counts):
        """
        **Property 24a: Rate Limit Enforcement**
        For any provider and sequence of email sending requests, the rate limiter
        should enforce limits and prevent exceeding configured thresholds.
        **Validates: Requirements 10.2**
        """
        # Get provider limits
        provider_limits = self.rate_limiter.rate_limits[provider]
        minute_limit = provider_limits['emails_per_minute']
        hour_limit = provider_limits['emails_per_hour']
        
        # Reset rate limiter for clean test
        self.rate_limiter.counters[provider] = {'minute': [], 'hour': []}
        
        total_sent = 0
        total_blocked = 0
        
        for count in email_counts:
            # Check if we can send this batch
            can_send, reason = self.rate_limiter.can_send_email(provider, count)
            
            if can_send:
                # Record the emails as sent
                self.rate_limiter.record_sent_emails(provider, count)
                total_sent += count
                
                # Verify we haven't exceeded limits
                current_minute = len(self.rate_limiter.counters[provider]['minute'])
                current_hour = len(self.rate_limiter.counters[provider]['hour'])
                
                self.assertLessEqual(current_minute, minute_limit,
                                   f"Minute limit exceeded: {current_minute} > {minute_limit}")
                self.assertLessEqual(current_hour, hour_limit,
                                   f"Hour limit exceeded: {current_hour} > {hour_limit}")
            else:
                total_blocked += count
                # Verify reason is provided when blocked
                self.assertIsInstance(reason, str)
                self.assertGreater(len(reason), 0, "Block reason should be provided")
        
        # Verify that rate limiting actually prevented some sends if we would have exceeded limits
        total_requested = sum(email_counts)
        if total_requested > minute_limit:
            self.assertGreater(total_blocked, 0, 
                             "Rate limiter should have blocked some emails when limit would be exceeded")
    
    @given(
        provider=st.sampled_from(['gmail', 'outlook', 'yahoo', 'office365', 'custom']),
        batch_size=st.integers(min_value=1, max_value=200)
    )
    @settings(max_examples=50, deadline=3000)
    def test_rate_limit_boundary_conditions_property(self, provider, batch_size):
        """
        **Property 24b: Rate Limit Boundary Conditions**
        For any provider and batch size, rate limiting should correctly handle
        boundary conditions at the exact limit thresholds.
        **Validates: Requirements 10.2**
        """
        # Get provider limits
        provider_limits = self.rate_limiter.rate_limits[provider]
        minute_limit = provider_limits['emails_per_minute']
        hour_limit = provider_limits['emails_per_hour']
        
        # Reset rate limiter
        self.rate_limiter.counters[provider] = {'minute': [], 'hour': []}
        
        # Test at exact minute limit
        if batch_size <= minute_limit:
            # Should be able to send up to the limit
            can_send, _ = self.rate_limiter.can_send_email(provider, batch_size)
            self.assertTrue(can_send, f"Should be able to send {batch_size} emails within limit {minute_limit}")
            
            # Record the emails
            self.rate_limiter.record_sent_emails(provider, batch_size)
            
            # Now should not be able to send more if it would exceed limit
            remaining_capacity = minute_limit - batch_size
            if remaining_capacity > 0:
                can_send_more, _ = self.rate_limiter.can_send_email(provider, remaining_capacity)
                self.assertTrue(can_send_more, "Should be able to send remaining capacity")
                
                # But not more than remaining
                can_exceed, reason = self.rate_limiter.can_send_email(provider, remaining_capacity + 1)
                self.assertFalse(can_exceed, "Should not be able to exceed minute limit")
                self.assertIn("minute", reason.lower(), "Reason should mention minute limit")
        else:
            # Batch size exceeds minute limit
            can_send, reason = self.rate_limiter.can_send_email(provider, batch_size)
            self.assertFalse(can_send, f"Should not be able to send {batch_size} emails exceeding limit {minute_limit}")
            self.assertIn("minute", reason.lower(), "Reason should mention minute limit")
    
    @given(
        provider=st.sampled_from(['gmail', 'outlook', 'yahoo', 'custom']),
        time_intervals=st.lists(st.floats(min_value=0.1, max_value=120.0), min_size=2, max_size=10)
    )
    @settings(max_examples=20, deadline=8000)
    def test_time_window_accuracy_property(self, provider, time_intervals):
        """
        **Property 24c: Time Window Accuracy**
        For any provider and sequence of time intervals, the rate limiter should
        accurately track time windows and clean up old entries.
        **Validates: Requirements 10.2**
        """
        # Reset rate limiter
        self.rate_limiter.counters[provider] = {'minute': [], 'hour': []}
        
        # Simulate sending emails at different time intervals
        base_time = datetime.now()
        
        for i, interval in enumerate(time_intervals):
            # Simulate time passing
            current_time = base_time + timedelta(seconds=sum(time_intervals[:i+1]))
            
            # Manually add entries with specific timestamps
            self.rate_limiter.counters[provider]['minute'].append(current_time)
            self.rate_limiter.counters[provider]['hour'].append(current_time)
            
            # Clean old entries using the current time
            self.rate_limiter._clean_old_entries(provider, current_time + timedelta(seconds=1))
            
            # Verify entries within time windows are kept
            minute_ago = current_time + timedelta(seconds=1) - timedelta(minutes=1)
            hour_ago = current_time + timedelta(seconds=1) - timedelta(hours=1)
            
            minute_entries = self.rate_limiter.counters[provider]['minute']
            hour_entries = self.rate_limiter.counters[provider]['hour']
            
            # All remaining entries should be within time windows
            for entry_time in minute_entries:
                self.assertGreater(entry_time, minute_ago, 
                                 "Minute entries should be within 1 minute window")
            
            for entry_time in hour_entries:
                self.assertGreater(entry_time, hour_ago, 
                                 "Hour entries should be within 1 hour window")
        
        # Final cleanup test - simulate time passing beyond all windows
        future_time = base_time + timedelta(hours=2)
        self.rate_limiter._clean_old_entries(provider, future_time)
        
        # All entries should be cleaned up
        self.assertEqual(len(self.rate_limiter.counters[provider]['minute']), 0,
                        "All minute entries should be cleaned after 2 hours")
        self.assertEqual(len(self.rate_limiter.counters[provider]['hour']), 0,
                        "All hour entries should be cleaned after 2 hours")
    
    @given(
        providers=st.lists(st.sampled_from(['gmail', 'outlook', 'yahoo', 'custom']), 
                          min_size=1, max_size=4, unique=True),
        email_counts=st.lists(st.integers(min_value=1, max_value=30), min_size=1, max_size=10)
    )
    @settings(max_examples=15, deadline=5000)
    def test_multi_provider_isolation_property(self, providers, email_counts):
        """
        **Property 24d: Multi-Provider Isolation**
        For any set of providers and email counts, rate limiting should be
        isolated per provider and not interfere between providers.
        **Validates: Requirements 10.2**
        """
        # Reset all provider counters
        for provider in providers:
            self.rate_limiter.counters[provider] = {'minute': [], 'hour': []}
        
        # Send emails for each provider
        provider_totals = defaultdict(int)
        
        for provider in providers:
            for count in email_counts:
                # Check if we can send for this provider
                can_send, _ = self.rate_limiter.can_send_email(provider, count)
                
                if can_send:
                    # Record emails for this provider
                    self.rate_limiter.record_sent_emails(provider, count)
                    provider_totals[provider] += count
        
        # Verify each provider's limits are enforced independently
        for provider in providers:
            provider_limits = self.rate_limiter.rate_limits[provider]
            minute_count = len(self.rate_limiter.counters[provider]['minute'])
            hour_count = len(self.rate_limiter.counters[provider]['hour'])
            
            # Should not exceed this provider's limits
            self.assertLessEqual(minute_count, provider_limits['emails_per_minute'],
                               f"Provider {provider} minute limit should be enforced independently")
            self.assertLessEqual(hour_count, provider_limits['emails_per_hour'],
                               f"Provider {provider} hour limit should be enforced independently")
            
            # Verify counts match what we recorded
            self.assertEqual(minute_count, provider_totals[provider],
                           f"Recorded count should match actual count for {provider}")
    
    @given(
        provider=st.sampled_from(['gmail', 'outlook', 'yahoo', 'custom']),
        email_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=30, deadline=3000)
    def test_wait_time_calculation_property(self, provider, email_count):
        """
        **Property 24e: Wait Time Calculation**
        For any provider and email count, when rate limited, the system should
        provide accurate wait time recommendations.
        **Validates: Requirements 10.2**
        """
        # Get provider limits
        provider_limits = self.rate_limiter.rate_limits[provider]
        minute_limit = provider_limits['emails_per_minute']
        
        # Reset rate limiter
        self.rate_limiter.counters[provider] = {'minute': [], 'hour': []}
        
        # Fill up to the minute limit
        if email_count <= minute_limit:
            self.rate_limiter.record_sent_emails(provider, email_count)
            
            # Should still be able to send more if under limit
            remaining = minute_limit - email_count
            if remaining > 0:
                wait_time = self.rate_limiter.get_wait_time(provider)
                self.assertEqual(wait_time, 0, "Should not need to wait when under limit")
            else:
                # At exact limit, should need to wait
                wait_time = self.rate_limiter.get_wait_time(provider)
                self.assertGreaterEqual(wait_time, 0, "Wait time should be non-negative")
                self.assertLessEqual(wait_time, 60, "Wait time should not exceed 60 seconds")
        else:
            # Exceeds minute limit - fill to limit first
            self.rate_limiter.record_sent_emails(provider, minute_limit)
            
            # Now should need to wait
            wait_time = self.rate_limiter.get_wait_time(provider)
            self.assertGreater(wait_time, 0, "Should need to wait when at limit")
            self.assertLessEqual(wait_time, 60, "Wait time should not exceed 60 seconds")
    
    @patch('students.email_service.smtplib.SMTP')
    @given(
        recipient_count=st.integers(min_value=50, max_value=300),
        provider=st.sampled_from(['gmail', 'outlook', 'custom'])
    )
    @settings(max_examples=10, deadline=15000)
    def test_bulk_email_rate_limiting_integration_property(self, mock_smtp, recipient_count, provider):
        """
        **Property 24f: Bulk Email Rate Limiting Integration**
        For any bulk email operation, rate limiting should be properly integrated
        and prevent exceeding provider limits during actual sending.
        **Validates: Requirements 10.2**
        """
        # Create mock SMTP server
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server
        
        # Create test recipients
        recipients = [f"test{i}@example.com" for i in range(recipient_count)]
        
        # Create email configuration for the provider
        host_map = {
            'gmail': 'smtp.gmail.com',
            'outlook': 'smtp-mail.outlook.com',
            'custom': 'smtp.custom.com'
        }
        
        config = EmailConfiguration.objects.create(
            smtp_host=host_map[provider],
            smtp_port=587,
            smtp_username='test@test.com',
            from_email='test@test.com',
            use_tls=True,
            use_ssl=False,
            from_name='Test System',
            is_active=True
        )
        config.set_password('test_password')
        config.save()
        
        # Track actual send calls to verify rate limiting
        send_calls = []
        send_times = []
        
        def mock_send_message(msg):
            send_calls.append(msg)
            send_times.append(datetime.now())
            return True
        
        mock_server.send_message.side_effect = mock_send_message
        
        # Test bulk email sending with rate limiting
        with patch.object(self.email_service, '_get_or_create_smtp_connection', return_value=mock_server):
            start_time = datetime.now()
            result = self.email_service.send_bulk_email(
                to_emails=recipients,
                subject="Test Subject",
                message="Test Message"
            )
            end_time = datetime.now()
        
        # Verify bulk email succeeded
        self.assertTrue(result['success'], f"Bulk email should succeed: {result.get('error', '')}")
        
        # Verify rate limiting was applied
        provider_limits = self.rate_limiter.rate_limits[provider]
        minute_limit = provider_limits['emails_per_minute']
        
        # Check that batching respected rate limits
        performance_stats = result.get('performance_stats', {})
        batch_size_used = performance_stats.get('batch_size_used', 0)
        
        self.assertGreater(batch_size_used, 0, "Batch size should be positive")
        self.assertLessEqual(batch_size_used, minute_limit, 
                           f"Batch size {batch_size_used} should not exceed minute limit {minute_limit}")
        
        # Verify all emails were sent
        self.assertEqual(len(send_calls), recipient_count, 
                        "All emails should be sent despite rate limiting")
        
        # If operation took multiple batches, verify timing
        if recipient_count > batch_size_used:
            total_duration = (end_time - start_time).total_seconds()
            expected_batches = (recipient_count + batch_size_used - 1) // batch_size_used
            
            if expected_batches > 1:
                # Should have taken some time due to batch delays
                min_expected_time = (expected_batches - 1) * 0.5  # Minimum delay between batches
                self.assertGreaterEqual(total_duration, min_expected_time,
                                      f"Operation should take time for rate limiting: {total_duration}s >= {min_expected_time}s")
    
    def test_rate_limiter_thread_safety(self):
        """
        Test that rate limiter is thread-safe for concurrent operations.
        **Validates: Requirements 10.2**
        """
        import threading
        
        provider = 'gmail'
        self.rate_limiter.counters[provider] = {'minute': [], 'hour': []}
        
        # Function to simulate concurrent email sending
        def send_emails(count):
            for _ in range(count):
                can_send, _ = self.rate_limiter.can_send_email(provider, 1)
                if can_send:
                    self.rate_limiter.record_sent_emails(provider, 1)
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=send_emails, args=(10,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify final counts are consistent
        minute_count = len(self.rate_limiter.counters[provider]['minute'])
        hour_count = len(self.rate_limiter.counters[provider]['hour'])
        
        # Counts should be equal (same time window)
        self.assertEqual(minute_count, hour_count, 
                        "Minute and hour counts should be equal for same time window")
        
        # Should not exceed limits due to race conditions
        provider_limits = self.rate_limiter.rate_limits[provider]
        self.assertLessEqual(minute_count, provider_limits['emails_per_minute'],
                           "Thread safety should prevent exceeding limits")
    
    def test_rate_limit_configuration_validation(self):
        """
        Test that rate limit configurations are valid and reasonable.
        **Validates: Requirements 10.2**
        """
        for provider, limits in self.rate_limiter.rate_limits.items():
            # Verify required fields exist
            self.assertIn('emails_per_minute', limits, f"Provider {provider} missing minute limit")
            self.assertIn('emails_per_hour', limits, f"Provider {provider} missing hour limit")
            
            minute_limit = limits['emails_per_minute']
            hour_limit = limits['emails_per_hour']
            
            # Verify limits are positive
            self.assertGreater(minute_limit, 0, f"Provider {provider} minute limit must be positive")
            self.assertGreater(hour_limit, 0, f"Provider {provider} hour limit must be positive")
            
            # Verify hour limit is at least as large as minute limit
            self.assertGreaterEqual(hour_limit, minute_limit, 
                                  f"Provider {provider} hour limit should be >= minute limit")
            
            # Verify limits are reasonable (not too high or too low)
            self.assertLessEqual(minute_limit, 1000, f"Provider {provider} minute limit seems too high")
            self.assertLessEqual(hour_limit, 100000, f"Provider {provider} hour limit seems too high")
            self.assertGreaterEqual(minute_limit, 1, f"Provider {provider} minute limit too low")


if __name__ == '__main__':
    unittest.main()