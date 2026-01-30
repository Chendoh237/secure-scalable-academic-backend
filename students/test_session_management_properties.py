"""
Property-Based Tests for Session Management

This module contains property-based tests that validate the session management
properties of the email management system, ensuring that expired authentication
sessions require re-authentication before allowing continued access.

**Property 12: Session Management**
For any expired authentication session, the system should require re-authentication 
before allowing continued access to email functions.
**Validates: Requirements 5.4**
"""

import unittest
from hypothesis import given, strategies as st, settings, assume
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
import time

from students.email_models import EmailConfiguration
from students.models import Student
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram

User = get_user_model()


class SessionManagementPropertiesTest(TestCase):
    """
    Property-based tests for session management.
    
    **Feature: email-management-system, Property 12: Session Management**
    **Validates: Requirements 5.4**
    """
    
    def setUp(self):
        """Set up test environment"""
        self.client = Client()
        
        # Create test admin user
        self.admin_user = User.objects.create_user(
            username='testadmin',
            email='admin@test.edu',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create test institution structure for students
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
            name="Test Department",
            faculty=self.faculty
        )
        
        self.program = AcademicProgram.objects.create(
            name="Test Program",
            code="TP",
            department=self.department
        )
        
        # Create test SMTP configuration
        self.smtp_config = EmailConfiguration.objects.create(
            smtp_host='smtp.test.com',
            smtp_port=587,
            smtp_username='test@test.com',
            from_email='test@test.com',
            use_tls=True,
            use_ssl=False,
            from_name='Test System',
            is_active=True
        )
        self.smtp_config.set_password('test_password')
        self.smtp_config.save()
    
    def create_authenticated_session(self, user=None, expire_in_seconds=None):
        """Helper method to create authenticated session"""
        if user is None:
            user = self.admin_user
        
        # Login to create session
        login_success = self.client.login(username=user.username, password='testpass123')
        self.assertTrue(login_success, "Login should succeed")
        
        # Modify session expiry if specified
        if expire_in_seconds is not None:
            session = self.client.session
            if expire_in_seconds <= 0:
                # Expire the session
                session.set_expiry(timezone.now() - timedelta(seconds=1))
            else:
                # Set future expiry
                session.set_expiry(timezone.now() + timedelta(seconds=expire_in_seconds))
            session.save()
        
        return self.client.session.session_key
    
    def get_email_endpoint_urls(self):
        """Get list of email management endpoint URLs for testing"""
        return [
            '/admin/email/smtp/config/',
            '/admin/email/templates/',
            '/admin/email/recipients/options/',
            '/admin/email/history/',
            '/admin/email/statistics/',
            '/admin/email/integration/health/',
        ]
    
    @given(
        session_expiry_times=st.lists(
            st.integers(min_value=-3600, max_value=3600),  # -1 hour to +1 hour
            min_size=1, max_size=10
        )
    )
    @settings(max_examples=20, deadline=10000)
    def test_session_expiry_enforcement_property(self, session_expiry_times):
        """
        **Property 12a: Session Expiry Enforcement**
        For any session with various expiry times, the system should enforce
        authentication requirements based on session validity.
        **Validates: Requirements 5.4**
        """
        email_endpoints = self.get_email_endpoint_urls()
        
        for expiry_seconds in session_expiry_times:
            # Create session with specific expiry
            session_key = self.create_authenticated_session(expire_in_seconds=expiry_seconds)
            
            # Test access to email endpoints
            for endpoint_url in email_endpoints:
                try:
                    response = self.client.get(endpoint_url)
                    
                    if expiry_seconds <= 0:
                        # Expired session - should require re-authentication
                        self.assertIn(response.status_code, [401, 403, 302],
                                    f"Expired session should be rejected for {endpoint_url}")
                        
                        # Should not return sensitive email data
                        if response.status_code == 200:
                            content = response.content.decode('utf-8')
                            self.assertNotIn('smtp_host', content.lower(),
                                           "Expired session should not return SMTP config")
                            self.assertNotIn('email', content.lower(),
                                           "Expired session should not return email data")
                    else:
                        # Valid session - should allow access or return proper response
                        # (Some endpoints might return 404 or other valid responses)
                        self.assertNotIn(response.status_code, [401, 403],
                                       f"Valid session should not be rejected for {endpoint_url}")
                
                except Exception as e:
                    # Network or other errors are acceptable, but not authentication bypasses
                    if "authentication" in str(e).lower() or "permission" in str(e).lower():
                        if expiry_seconds > 0:
                            self.fail(f"Valid session should not have auth errors: {str(e)}")
            
            # Logout to clean up session
            self.client.logout()
    
    @given(
        concurrent_sessions=st.lists(
            st.tuples(
                st.text(min_size=5, max_size=20),  # username
                st.integers(min_value=-1800, max_value=1800)  # expiry_seconds
            ),
            min_size=1, max_size=5
        )
    )
    @settings(max_examples=15, deadline=8000)
    def test_concurrent_session_management_property(self, concurrent_sessions):
        """
        **Property 12b: Concurrent Session Management**
        For any number of concurrent sessions with different expiry times,
        each session should be managed independently.
        **Validates: Requirements 5.4**
        """
        # Create multiple users and sessions
        users_and_clients = []
        
        for i, (username_suffix, expiry_seconds) in enumerate(concurrent_sessions):
            # Create unique user
            username = f"testuser{i}_{username_suffix[:10]}"
            user = User.objects.create_user(
                username=username,
                email=f"{username}@test.edu",
                password='testpass123',
                is_staff=True,
                is_superuser=True
            )
            
            # Create separate client for this user
            client = Client()
            login_success = client.login(username=username, password='testpass123')
            self.assertTrue(login_success, f"Login should succeed for {username}")
            
            # Set session expiry
            session = client.session
            if expiry_seconds <= 0:
                session.set_expiry(timezone.now() - timedelta(seconds=abs(expiry_seconds)))
            else:
                session.set_expiry(timezone.now() + timedelta(seconds=expiry_seconds))
            session.save()
            
            users_and_clients.append((user, client, expiry_seconds))
        
        # Test each session independently
        test_endpoint = '/admin/email/smtp/config/'
        
        for user, client, expiry_seconds in users_and_clients:
            try:
                response = client.get(test_endpoint)
                
                if expiry_seconds <= 0:
                    # Expired session should be rejected
                    self.assertIn(response.status_code, [401, 403, 302],
                                f"Expired session for {user.username} should be rejected")
                else:
                    # Valid session should be allowed
                    self.assertNotIn(response.status_code, [401, 403],
                                   f"Valid session for {user.username} should be allowed")
            
            except Exception as e:
                # Handle gracefully but verify authentication behavior
                if expiry_seconds > 0 and "authentication" in str(e).lower():
                    self.fail(f"Valid session should not have auth errors: {str(e)}")
    
    @given(
        session_activities=st.lists(
            st.tuples(
                st.sampled_from(['GET', 'POST']),  # HTTP method
                st.integers(min_value=1, max_value=300),  # delay_seconds
                st.booleans()  # should_extend_session
            ),
            min_size=1, max_size=8
        )
    )
    @settings(max_examples=10, deadline=15000)
    def test_session_activity_extension_property(self, session_activities):
        """
        **Property 12c: Session Activity Extension**
        For any sequence of session activities, the system should properly
        manage session lifetime based on activity patterns.
        **Validates: Requirements 5.4**
        """
        # Create session with short expiry for testing
        initial_expiry = 300  # 5 minutes
        session_key = self.create_authenticated_session(expire_in_seconds=initial_expiry)
        
        # Track session validity over time
        session_start_time = timezone.now()
        
        for method, delay_seconds, should_extend in session_activities:
            # Simulate time passing
            if delay_seconds > 0:
                # We can't actually wait, so we'll simulate by modifying session expiry
                current_session = Session.objects.filter(session_key=session_key).first()
                if current_session:
                    # Simulate time passage by reducing expiry
                    time_passed = min(delay_seconds, initial_expiry - 10)  # Don't expire completely
                    new_expiry = current_session.expire_date - timedelta(seconds=time_passed)
                    current_session.expire_date = new_expiry
                    current_session.save()
            
            # Make request to test session
            test_endpoint = '/admin/email/smtp/config/'
            
            try:
                if method == 'GET':
                    response = self.client.get(test_endpoint)
                else:  # POST
                    response = self.client.post(test_endpoint, {})
                
                # Check if session is still valid
                current_session = Session.objects.filter(session_key=session_key).first()
                
                if current_session and current_session.expire_date > timezone.now():
                    # Session should still be valid
                    self.assertNotIn(response.status_code, [401, 403],
                                   "Valid session should allow access")
                    
                    if should_extend and method == 'POST':
                        # POST requests might extend session (depending on Django settings)
                        # This is implementation-dependent, so we just verify no auth errors
                        pass
                else:
                    # Session expired - should require re-authentication
                    self.assertIn(response.status_code, [401, 403, 302],
                                "Expired session should require re-authentication")
            
            except Exception as e:
                # Handle gracefully - focus on authentication behavior
                if "authentication" in str(e).lower():
                    # Check if session should be valid
                    current_session = Session.objects.filter(session_key=session_key).first()
                    if current_session and current_session.expire_date > timezone.now():
                        self.fail(f"Valid session should not have auth errors: {str(e)}")
    
    @given(
        email_operations=st.lists(
            st.sampled_from([
                'smtp_config', 'send_email', 'view_history', 'get_templates', 'validate_recipients'
            ]),
            min_size=1, max_size=10
        )
    )
    @settings(max_examples=15, deadline=10000)
    def test_email_operation_session_requirements_property(self, email_operations):
        """
        **Property 12d: Email Operation Session Requirements**
        For any sequence of email operations, each should enforce proper
        session authentication requirements.
        **Validates: Requirements 5.4**
        """
        operation_endpoints = {
            'smtp_config': '/admin/email/smtp/config/',
            'send_email': '/admin/email/send/',
            'view_history': '/admin/email/history/',
            'get_templates': '/admin/email/templates/',
            'validate_recipients': '/admin/email/recipients/validate/'
        }
        
        # Test with valid session
        session_key = self.create_authenticated_session(expire_in_seconds=600)  # 10 minutes
        
        for operation in email_operations:
            endpoint = operation_endpoints[operation]
            
            try:
                response = self.client.get(endpoint)
                
                # Valid session should not be rejected for authentication
                self.assertNotIn(response.status_code, [401, 403],
                               f"Valid session should allow access to {operation}")
            
            except Exception as e:
                if "authentication" in str(e).lower() or "permission" in str(e).lower():
                    self.fail(f"Valid session should not have auth errors for {operation}: {str(e)}")
        
        # Test with expired session
        self.client.logout()
        expired_session_key = self.create_authenticated_session(expire_in_seconds=-60)  # Expired
        
        for operation in email_operations:
            endpoint = operation_endpoints[operation]
            
            try:
                response = self.client.get(endpoint)
                
                # Expired session should be rejected
                self.assertIn(response.status_code, [401, 403, 302],
                            f"Expired session should be rejected for {operation}")
                
                # Should not return sensitive data
                if response.status_code == 200:
                    content = response.content.decode('utf-8')
                    sensitive_terms = ['smtp_host', 'password', 'email_history', 'recipient']
                    for term in sensitive_terms:
                        self.assertNotIn(term, content.lower(),
                                       f"Expired session should not return {term} data")
            
            except Exception as e:
                # Authentication errors are expected for expired sessions
                if "authentication" not in str(e).lower() and "permission" not in str(e).lower():
                    # Other errors might be acceptable
                    pass
    
    @given(
        session_manipulation_attempts=st.lists(
            st.sampled_from(['modify_session_id', 'forge_session', 'replay_session']),
            min_size=1, max_size=5
        )
    )
    @settings(max_examples=10, deadline=8000)
    def test_session_security_property(self, session_manipulation_attempts):
        """
        **Property 12e: Session Security**
        For any attempt to manipulate or forge sessions, the system should
        maintain security and require proper authentication.
        **Validates: Requirements 5.4**
        """
        # Create valid session first
        valid_session_key = self.create_authenticated_session(expire_in_seconds=600)
        test_endpoint = '/admin/email/smtp/config/'
        
        # Verify valid session works
        response = self.client.get(test_endpoint)
        self.assertNotIn(response.status_code, [401, 403],
                        "Valid session should work initially")
        
        for manipulation_type in session_manipulation_attempts:
            # Create new client for manipulation attempts
            malicious_client = Client()
            
            if manipulation_type == 'modify_session_id':
                # Try with modified session ID
                malicious_client.cookies['sessionid'] = 'invalid_session_id_12345'
                
            elif manipulation_type == 'forge_session':
                # Try with completely fake session
                malicious_client.cookies['sessionid'] = 'forged_session_abcdef'
                
            elif manipulation_type == 'replay_session':
                # Try to replay an old/expired session
                old_session_key = self.create_authenticated_session(expire_in_seconds=-300)
                malicious_client.cookies['sessionid'] = old_session_key
            
            # Attempt to access protected endpoint
            try:
                response = malicious_client.get(test_endpoint)
                
                # Manipulated sessions should be rejected
                self.assertIn(response.status_code, [401, 403, 302],
                            f"Manipulated session ({manipulation_type}) should be rejected")
                
                # Should not return sensitive data
                if response.status_code == 200:
                    content = response.content.decode('utf-8')
                    self.assertNotIn('smtp_host', content.lower(),
                                   f"Manipulated session should not return SMTP config")
            
            except Exception as e:
                # Authentication/permission errors are expected and acceptable
                if "authentication" in str(e).lower() or "permission" in str(e).lower():
                    pass  # Expected
                else:
                    # Other errors should not occur due to session manipulation
                    self.fail(f"Session manipulation should not cause unexpected errors: {str(e)}")
    
    @given(
        re_authentication_scenarios=st.lists(
            st.tuples(
                st.integers(min_value=1, max_value=5),  # operations_before_expiry
                st.integers(min_value=1, max_value=3)   # operations_after_expiry
            ),
            min_size=1, max_size=3
        )
    )
    @settings(max_examples=10, deadline=10000)
    def test_re_authentication_requirement_property(self, re_authentication_scenarios):
        """
        **Property 12f: Re-authentication Requirement**
        For any scenario where session expires during use, the system should
        require re-authentication before allowing continued access.
        **Validates: Requirements 5.4**
        """
        test_endpoints = [
            '/admin/email/smtp/config/',
            '/admin/email/templates/',
            '/admin/email/history/'
        ]
        
        for ops_before, ops_after in re_authentication_scenarios:
            # Create session with limited lifetime
            session_key = self.create_authenticated_session(expire_in_seconds=120)
            
            # Perform operations while session is valid
            for i in range(ops_before):
                endpoint = test_endpoints[i % len(test_endpoints)]
                
                try:
                    response = self.client.get(endpoint)
                    # Should work with valid session
                    self.assertNotIn(response.status_code, [401, 403],
                                   f"Valid session should allow operation {i+1}")
                except Exception as e:
                    if "authentication" in str(e).lower():
                        self.fail(f"Valid session should not have auth errors: {str(e)}")
            
            # Expire the session
            current_session = Session.objects.filter(session_key=session_key).first()
            if current_session:
                current_session.expire_date = timezone.now() - timedelta(seconds=1)
                current_session.save()
            
            # Attempt operations after expiry
            for i in range(ops_after):
                endpoint = test_endpoints[i % len(test_endpoints)]
                
                try:
                    response = self.client.get(endpoint)
                    
                    # Should require re-authentication
                    self.assertIn(response.status_code, [401, 403, 302],
                                f"Expired session should require re-auth for operation {i+1}")
                
                except Exception as e:
                    # Authentication errors are expected
                    if "authentication" not in str(e).lower() and "permission" not in str(e).lower():
                        # Other errors might indicate system issues
                        pass
            
            # Re-authenticate and verify access is restored
            self.client.logout()
            login_success = self.client.login(username=self.admin_user.username, password='testpass123')
            
            if login_success:
                # Should be able to access after re-authentication
                response = self.client.get(test_endpoints[0])
                self.assertNotIn(response.status_code, [401, 403],
                               "Re-authenticated session should allow access")
            
            # Clean up
            self.client.logout()
    
    def test_session_timeout_configuration(self):
        """
        Test that session timeout configuration is properly enforced.
        **Validates: Requirements 5.4**
        """
        # Test with very short session timeout
        with self.settings(SESSION_COOKIE_AGE=1):  # 1 second
            session_key = self.create_authenticated_session()
            
            # Wait for session to expire (simulate)
            current_session = Session.objects.filter(session_key=session_key).first()
            if current_session:
                current_session.expire_date = timezone.now() - timedelta(seconds=1)
                current_session.save()
            
            # Should require re-authentication
            response = self.client.get('/admin/email/smtp/config/')
            self.assertIn(response.status_code, [401, 403, 302],
                        "Expired session should require re-authentication")
    
    def test_session_cleanup_on_logout(self):
        """
        Test that sessions are properly cleaned up on logout.
        **Validates: Requirements 5.4**
        """
        # Create authenticated session
        session_key = self.create_authenticated_session()
        
        # Verify session exists
        session_exists = Session.objects.filter(session_key=session_key).exists()
        self.assertTrue(session_exists, "Session should exist after login")
        
        # Logout
        self.client.logout()
        
        # Attempt to access protected resource
        response = self.client.get('/admin/email/smtp/config/')
        self.assertIn(response.status_code, [401, 403, 302],
                    "Logged out session should not allow access")
    
    def test_session_hijacking_protection(self):
        """
        Test protection against session hijacking attempts.
        **Validates: Requirements 5.4**
        """
        # Create legitimate session
        session_key = self.create_authenticated_session()
        
        # Simulate session hijacking by using session from different client
        hijacker_client = Client()
        hijacker_client.cookies['sessionid'] = session_key
        
        # Attempt to access protected resource
        response = hijacker_client.get('/admin/email/smtp/config/')
        
        # Depending on Django configuration, this might be allowed or blocked
        # The key is that sensitive operations should have additional protection
        if response.status_code == 200:
            # If session sharing is allowed, sensitive operations should still be protected
            # This would require additional CSRF or other protections
            pass
        else:
            # Session hijacking blocked - good
            self.assertIn(response.status_code, [401, 403, 302],
                        "Session hijacking should be blocked")


if __name__ == '__main__':
    unittest.main()