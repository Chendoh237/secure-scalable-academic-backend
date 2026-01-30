#!/usr/bin/env python
"""
Simple test to verify email management URL patterns
"""

import os
import sys
import django

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.urls import reverse, resolve
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from students.email_views import (
    get_smtp_configuration,
    get_smtp_providers,
    get_email_templates,
    get_recipient_options,
    get_email_history,
    get_email_statistics
)

def test_email_url_patterns():
    """Test that email management URL patterns are correctly configured"""
    
    print("Testing email management URL patterns...")
    print("=" * 50)
    
    # Test URL patterns
    url_patterns = [
        ('admin_get_smtp_config', 'admin/email/smtp/config/'),
        ('admin_get_smtp_providers', 'admin/email/smtp/providers/'),
        ('admin_get_email_templates', 'admin/email/templates/'),
        ('admin_get_recipient_options', 'admin/email/recipients/options/'),
        ('admin_get_email_history', 'admin/email/history/'),
        ('admin_get_email_statistics', 'admin/email/statistics/'),
    ]
    
    for url_name, expected_path in url_patterns:
        try:
            # Test reverse URL lookup
            url = reverse(url_name)
            print(f"✅ {url_name}: {url}")
            
            # Test URL resolution
            resolved = resolve(url)
            print(f"   Resolves to: {resolved.func.__name__}")
            
        except Exception as e:
            print(f"❌ {url_name}: Error - {str(e)}")
    
    print("\n" + "=" * 50)
    
    # Test view function imports
    print("Testing view function imports...")
    view_functions = [
        ('get_smtp_configuration', get_smtp_configuration),
        ('get_smtp_providers', get_smtp_providers),
        ('get_email_templates', get_email_templates),
        ('get_recipient_options', get_recipient_options),
        ('get_email_history', get_email_history),
        ('get_email_statistics', get_email_statistics),
    ]
    
    for func_name, func in view_functions:
        if callable(func):
            print(f"✅ {func_name}: Imported successfully")
        else:
            print(f"❌ {func_name}: Import failed")
    
    print("\n" + "=" * 50)
    print("URL pattern test completed!")

if __name__ == "__main__":
    test_email_url_patterns()