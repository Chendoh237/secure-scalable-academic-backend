#!/usr/bin/env python
"""
Property-Based Tests for Email Management API

This module contains property-based tests that validate the correctness
properties of the email management API endpoints.
"""

import os
import sys
import django
from django.conf import settings

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

import unittest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
import json

User = get_user_model()


class EmailAPIAuthenticationPropertyTests(TestCase):
    """
    Property-based tests for email API authentication enforcement
    
    **Property 11: Authentication Enforcement**
    *For any* email management operation, the system should require valid 
    administrator authentication and reject unauthenticated requests
    **Validates: Requirements 5.1, 5.3**
    """
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create regular user (non-admin)
        self.regular_user = User.objects.create_user(
            username='regular_test',
            email='regular@test.com',
            password='testpass123',
            is_staff=False,
            is_superuser=False
        )
        
        # Email API endpoints to test
        self.email_endpoints = [
            '/api/admin/email/smtp/config/',
            '/api/admin/email/smtp/config/save/',
            '/api/admin/email/smtp/config/test/',
            '/api/admin/email/smtp/providers/',
            '/api/admin/email/smtp/config/delete/',
        ]
    
    def test_property_unauthenticated_requests_rejected(self):
        """
        Property: All email management endpoints should reject unauthenticated requests
        
        For any email management endpoint, an unauthenticated request should be rejected
        with appropriate authentication error.
        """
        print("\n🔍 Testing Property 11: Authentication Enforcement - Unauthenticated Requests")
        
        for endpoint in self.email_endpoints:
            with self.subTest(endpoint=endpoint):
                # Test GET requests
                if 'save' not in endpoint and 'test' not in endpoint and 'delete' not in endpoint:
                    response = self.client.get(endpoint)
                    self.assertIn(response.status_code, [302, 401, 403], 
                                f"Unauthenticated GET to {endpoint} should be rejected")
                
                # Test POST requests
                if 'save' in endpoint or 'test' in endpoint:
                    response = self.client.post(endpoint, 
                                              data=json.dumps({'test': 'data'}),
                                              content_type='application/json')
                    self.assertIn(response.status_code, [302, 401, 403], 
                                f"Unauthenticated POST to {endpoint} should be rejected")
                
                # Test DELETE requests
                if 'delete' in endpoint:
                    response = self.client.delete(endpoint)
                    self.assertIn(response.status_code, [302, 401, 403], 
                                f"Unauthenticated DELETE to {endpoint} should be rejected")
        
        print("✅ Property verified: All unauthenticated requests are properly rejected")
    
    def test_property_non_admin_requests_rejected(self):
        """
        Property: All email management endpoints should reject non-admin authenticated requests
        
        For any email management endpoint, a request from an authenticated but non-admin 
        user should be rejected with appropriate authorization error.
        """
        print("\n🔍 Testing Property 11: Authentication Enforcement - Non-Admin Requests")
        
        # Login as regular user
        self.client.login(username='regular_test', password='testpass123')
        
        for endpoint in self.email_endpoints:
            with self.subTest(endpoint=endpoint):
                # Test GET requests
                if 'save' not in endpoint and 'test' not in endpoint and 'delete' not in endpoint:
                    response = self.client.get(endpoint)
                    self.assertIn(response.status_code, [302, 401, 403], 
                                f"Non-admin GET to {endpoint} should be rejected")
                
                # Test POST requests
                if 'save' in endpoint or 'test' in endpoint:
                    response = self.client.post(endpoint, 
                                              data=json.dumps({'test': 'data'}),
                                              content_type='application/json')
                    self.assertIn(response.status_code, [302, 401, 403], 
                                f"Non-admin POST to {endpoint} should be rejected")
                
                # Test DELETE requests
                if 'delete' in endpoint:
                    response = self.client.delete(endpoint)
                    self.assertIn(response.status_code, [302, 401, 403], 
                                f"Non-admin DELETE to {endpoint} should be rejected")
        
        print("✅ Property verified: All non-admin requests are properly rejected")
    
    def test_property_admin_requests_accepted(self):
        """
        Property: All email management endpoints should accept valid admin requests
        
        For any email management endpoint, a request from an authenticated admin 
        user should be processed (not rejected due to authentication/authorization).
        """
        print("\n🔍 Testing Property 11: Authentication Enforcement - Admin Requests")
        
        # Login as admin user
        self.client.login(username='admin_test', password='testpass123')
        
        for endpoint in self.email_endpoints:
            with self.subTest(endpoint=endpoint):
                # Test GET requests (should not be rejected for auth reasons)
                if 'save' not in endpoint and 'test' not in endpoint and 'delete' not in endpoint:
                    response = self.client.get(endpoint)
                    # Should not be 401/403 (auth errors), but may be 400/500 for other reasons
                    self.assertNotIn(response.status_code, [401, 403], 
                                   f"Admin GET to {endpoint} should not be rejected for auth reasons")
                
                # Test POST requests with minimal valid data
                if 'save' in endpoint:
                    # Provide minimal required data for save endpoint
                    test_data = {
                        'smtp_host': 'smtp.test.com',
                        'smtp_port': 587,
                        'email_user': 'test@test.com',
                        'email_password': 'testpass'
                    }
                    response = self.client.post(endpoint, 
                                              data=json.dumps(test_data),
                                              content_type='application/json')
                    # Should not be 401/403 (auth errors)
                    self.assertNotIn(response.status_code, [401, 403], 
                                   f"Admin POST to {endpoint} should not be rejected for auth reasons")
                
                elif 'test' in endpoint:
                    # Test endpoint can work with empty data (uses saved config)
                    response = self.client.post(endpoint, 
                                              data=json.dumps({}),
                                              content_type='application/json')
                    # Should not be 401/403 (auth errors)
                    self.assertNotIn(response.status_code, [401, 403], 
                                   f"Admin POST to {endpoint} should not be rejected for auth reasons")
                
                # Test DELETE requests
                if 'delete' in endpoint:
                    response = self.client.delete(endpoint)
                    # Should not be 401/403 (auth errors), may be 404 if no config exists
                    self.assertNotIn(response.status_code, [401, 403], 
                                   f"Admin DELETE to {endpoint} should not be rejected for auth reasons")
        
        print("✅ Property verified: All admin requests are properly authenticated")
    
    def test_property_authentication_consistency(self):
        """
        Property: Authentication behavior should be consistent across all endpoints
        
        For any two email management endpoints, the authentication requirements 
        should be consistent - both should require admin authentication.
        """
        print("\n🔍 Testing Property 11: Authentication Enforcement - Consistency")
        
        auth_responses = {}
        
        # Test unauthenticated access to all endpoints
        for endpoint in self.email_endpoints:
            if 'save' not in endpoint and 'test' not in endpoint and 'delete' not in endpoint:
                response = self.client.get(endpoint)
                auth_responses[endpoint] = response.status_code
        
        # All endpoints should have similar authentication behavior
        status_codes = set(auth_responses.values())
        
        # Should all be authentication/authorization errors
        for status_code in status_codes:
            self.assertIn(status_code, [302, 401, 403], 
                        f"All endpoints should return auth errors, got: {auth_responses}")
        
        print("✅ Property verified: Authentication behavior is consistent across endpoints")
    
    def test_property_session_requirement(self):
        """
        Property: Valid session should be required for all operations
        
        For any email management operation, a valid session should be required,
        and expired/invalid sessions should be rejected.
        """
        print("\n🔍 Testing Property 11: Authentication Enforcement - Session Requirement")
        
        # Login as admin
        self.client.login(username='admin_test', password='testpass123')
        
        # Verify we can access an endpoint
        response = self.client.get('/api/admin/email/smtp/providers/')
        self.assertEqual(response.status_code, 200, "Should be able to access with valid session")
        
        # Logout (invalidate session)
        self.client.logout()
        
        # Verify we can no longer access the endpoint
        response = self.client.get('/api/admin/email/smtp/providers/')
        self.assertIn(response.status_code, [302, 401, 403], 
                    "Should not be able to access after logout")
        
        print("✅ Property verified: Valid session is required for all operations")


def run_property_tests():
    """Run all property-based tests"""
    print("🚀 Running Email API Authentication Property Tests")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(EmailAPIAuthenticationPropertyTests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "=" * 60)
    print("📊 PROPERTY TEST SUMMARY")
    print("=" * 60)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors
    
    print(f"Total Property Tests: {total_tests}")
    print(f"Passed: {passed}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    
    if failures > 0:
        print("\n❌ FAILED TESTS:")
        for test, traceback in result.failures:
            print(f"  • {test}: {traceback}")
    
    if errors > 0:
        print("\n💥 ERROR TESTS:")
        for test, traceback in result.errors:
            print(f"  • {test}: {traceback}")
    
    success = failures == 0 and errors == 0
    
    if success:
        print("\n🎉 ALL PROPERTY TESTS PASSED!")
        print("✅ Property 11: Authentication Enforcement - VERIFIED")
    else:
        print("\n⚠️  SOME PROPERTY TESTS FAILED!")
        print("❌ Property 11: Authentication Enforcement - NEEDS ATTENTION")
    
    return success


if __name__ == '__main__':
    success = run_property_tests()
    sys.exit(0 if success else 1)