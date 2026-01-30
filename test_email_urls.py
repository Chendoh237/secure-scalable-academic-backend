#!/usr/bin/env python
"""
Test script to check email management URLs
"""
import os
import sys
import django
from django.conf import settings

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.urls import reverse, NoReverseMatch

User = get_user_model()

def test_email_urls():
    """Test if email management URLs are accessible"""
    
    # Create a test admin user
    try:
        admin_user = User.objects.get(username='admin')
    except User.DoesNotExist:
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
    
    client = Client()
    
    # Login as admin
    login_success = client.login(username='admin', password='admin123')
    print(f"Admin login successful: {login_success}")
    
    if not login_success:
        print("Failed to login as admin")
        return
    
    # Test email management URLs
    email_urls = [
        '/api/admin/email/smtp/config/',
        '/api/admin/email/smtp/providers/',
        '/api/admin/email/templates/',
        '/api/admin/email/recipients/options/',
        '/api/admin/email/history/',
        '/api/admin/email/statistics/',
    ]
    
    print("\nTesting email management URLs:")
    for url in email_urls:
        try:
            response = client.get(url)
            print(f"GET {url} -> Status: {response.status_code}")
            if response.status_code == 404:
                print(f"  ERROR: URL not found!")
            elif response.status_code == 500:
                print(f"  ERROR: Server error - {response.content[:100]}")
        except Exception as e:
            print(f"GET {url} -> Exception: {e}")
    
    # Test URL reverse lookup
    print("\nTesting URL reverse lookup:")
    url_names = [
        'admin_get_smtp_config',
        'admin_get_smtp_providers',
        'admin_get_email_templates',
        'admin_get_recipient_options',
        'admin_get_email_history',
        'admin_get_email_statistics',
    ]
    
    for url_name in url_names:
        try:
            url = reverse(url_name)
            print(f"{url_name} -> {url}")
        except NoReverseMatch as e:
            print(f"{url_name} -> ERROR: {e}")

if __name__ == '__main__':
    test_email_urls()