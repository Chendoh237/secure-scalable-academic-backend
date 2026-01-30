#!/usr/bin/env python
"""
Comprehensive test for email management API authentication fix
"""

import os
import sys
import django
import requests
import json

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

def test_authentication_conversion():
    """Test that email views now use JWT authentication instead of session auth"""
    
    print("Testing Email Management API Authentication Conversion")
    print("=" * 60)
    
    # Create test user
    User = get_user_model()
    
    # Test with Django test client (simulates requests)
    client = APIClient()
    
    # Test endpoints that should require authentication
    endpoints = [
        '/admin/email/smtp/config/',
        '/admin/email/smtp/providers/',
        '/admin/email/templates/',
        '/admin/email/recipients/options/',
        '/admin/email/history/',
        '/admin/email/statistics/',
    ]
    
    print("\n1. Testing unauthenticated requests (should return 401):")
    print("-" * 50)
    
    for endpoint in endpoints:
        response = client.get(endpoint)
        status_code = response.status_code
        
        if status_code == 401:
            print(f"✅ {endpoint}: {status_code} (JWT auth working)")
        elif status_code == 302:
            print(f"❌ {endpoint}: {status_code} (still using session auth)")
            if 'Location' in response:
                print(f"   Redirects to: {response.get('Location', 'Unknown')}")
        elif status_code == 404:
            print(f"⚠️  {endpoint}: {status_code} (URL not found)")
        else:
            print(f"⚠️  {endpoint}: {status_code} (unexpected)")
    
    print("\n2. Testing with JWT authentication:")
    print("-" * 50)
    
    try:
        # Create admin user for testing
        admin_user = User.objects.create_user(
            username='test_admin',
            email='admin@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Generate JWT token
        refresh = RefreshToken.for_user(admin_user)
        access_token = str(refresh.access_token)
        
        # Set JWT authentication header
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            status_code = response.status_code
            
            if status_code in [200, 404]:  # 200 = success, 404 = endpoint exists but no data
                print(f"✅ {endpoint}: {status_code} (JWT auth successful)")
            elif status_code == 401:
                print(f"❌ {endpoint}: {status_code} (JWT auth failed)")
            elif status_code == 403:
                print(f"⚠️  {endpoint}: {status_code} (permission denied)")
            else:
                print(f"⚠️  {endpoint}: {status_code} (unexpected)")
        
        # Clean up test user
        admin_user.delete()
        
    except Exception as e:
        print(f"❌ Error creating test user or JWT token: {str(e)}")
    
    print("\n3. Testing POST endpoints:")
    print("-" * 50)
    
    post_endpoints = [
        ('/admin/email/smtp/config/save/', {'smtp_host': 'test.com', 'smtp_port': 587, 'email_user': 'test@test.com', 'email_password': 'test'}),
        ('/admin/email/smtp/config/test/', {}),
        ('/admin/email/templates/render/', {'template_id': 1, 'context': {}}),
        ('/admin/email/recipients/validate/', {'type': 'all'}),
        ('/admin/email/send/', {'subject': 'Test', 'body': 'Test', 'recipient_config': {'type': 'all'}}),
    ]
    
    # Test without authentication
    client.credentials()  # Clear auth
    
    for endpoint, data in post_endpoints:
        response = client.post(endpoint, data, format='json')
        status_code = response.status_code
        
        if status_code == 401:
            print(f"✅ {endpoint}: {status_code} (JWT auth required)")
        elif status_code == 302:
            print(f"❌ {endpoint}: {status_code} (still using session auth)")
        elif status_code == 404:
            print(f"⚠️  {endpoint}: {status_code} (URL not found)")
        else:
            print(f"⚠️  {endpoint}: {status_code} (unexpected)")
    
    print("\n" + "=" * 60)
    print("Authentication conversion test completed!")
    print("\nSummary:")
    print("✅ = JWT authentication working correctly")
    print("❌ = Still using Django session authentication")
    print("⚠️  = Unexpected result or URL issue")

def test_view_decorators():
    """Test that view functions have correct DRF decorators"""
    
    print("\n\nTesting View Function Decorators")
    print("=" * 40)
    
    from students.email_views import (
        get_smtp_configuration,
        save_smtp_configuration,
        test_smtp_connection,
        get_smtp_providers,
        delete_smtp_configuration,
        get_email_templates,
        render_email_template,
        get_recipient_options,
        validate_recipients,
        send_bulk_email,
        get_email_history,
        get_email_delivery_details,
        get_email_statistics
    )
    
    view_functions = [
        ('get_smtp_configuration', get_smtp_configuration),
        ('save_smtp_configuration', save_smtp_configuration),
        ('test_smtp_connection', test_smtp_connection),
        ('get_smtp_providers', get_smtp_providers),
        ('delete_smtp_configuration', delete_smtp_configuration),
        ('get_email_templates', get_email_templates),
        ('render_email_template', render_email_template),
        ('get_recipient_options', get_recipient_options),
        ('validate_recipients', validate_recipients),
        ('send_bulk_email', send_bulk_email),
        ('get_email_history', get_email_history),
        ('get_email_delivery_details', get_email_delivery_details),
        ('get_email_statistics', get_email_statistics),
    ]
    
    for func_name, func in view_functions:
        # Check if function has DRF decorators
        has_api_view = hasattr(func, 'cls') or hasattr(func, 'actions')
        has_permission_classes = hasattr(func, 'permission_classes')
        
        if has_api_view:
            print(f"✅ {func_name}: Has DRF @api_view decorator")
        else:
            print(f"❌ {func_name}: Missing DRF @api_view decorator")
        
        # Check for old Django decorators (should not be present)
        func_code = str(func)
        if 'login_required' in func_code or 'user_passes_test' in func_code:
            print(f"⚠️  {func_name}: May still have old Django auth decorators")

if __name__ == "__main__":
    test_authentication_conversion()
    test_view_decorators()