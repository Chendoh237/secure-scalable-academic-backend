#!/usr/bin/env python
"""
Test Email Configuration API Endpoints

This test verifies that the email configuration API endpoints work correctly.
"""

import os
import sys
import django
import json
import requests
from django.conf import settings

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from students.email_models import EmailConfiguration

User = get_user_model()

def test_email_config_api():
    """Test email configuration API endpoints"""
    
    print("🔍 Testing Email Configuration API Endpoints")
    print("=" * 50)
    
    # Create test client
    client = Client()
    
    # Create admin user
    admin_user = User.objects.get_or_create(
        username="email_api_admin",
        defaults={
            'email': 'admin@test.com',
            'is_staff': True,
            'is_superuser': True
        }
    )[0]
    admin_user.set_password('testpass123')
    admin_user.save()
    
    # Login as admin
    login_success = client.login(username='email_api_admin', password='testpass123')
    if not login_success:
        print("❌ Failed to login as admin user")
        return False
    
    print("✅ Admin user logged in successfully")
    
    # Test 1: Get SMTP providers
    print("\n🔍 Test 1: Get SMTP Providers")
    try:
        response = client.get('/api/admin/email/smtp/providers/')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Providers retrieved: {list(data.get('providers', {}).keys())}")
        else:
            print(f"❌ Failed to get providers: {response.content}")
            return False
    except Exception as e:
        print(f"❌ Error getting providers: {str(e)}")
        return False
    
    # Test 2: Get current SMTP configuration (should be empty initially)
    print("\n🔍 Test 2: Get Current SMTP Configuration")
    try:
        response = client.get('/api/admin/email/smtp/config/')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Configuration status: {data}")
        else:
            print(f"❌ Failed to get config: {response.content}")
            return False
    except Exception as e:
        print(f"❌ Error getting config: {str(e)}")
        return False
    
    # Test 3: Save SMTP configuration
    print("\n🔍 Test 3: Save SMTP Configuration")
    try:
        config_data = {
            'smtp_host': 'smtp.gmail.com',
            'smtp_port': 587,
            'email_user': 'test@gmail.com',
            'email_password': 'testpassword123',
            'use_tls': True,
            'use_ssl': False,
            'from_name': 'Test University',
            'provider': 'gmail'
        }
        
        response = client.post(
            '/api/admin/email/smtp/config/save/',
            data=json.dumps(config_data),
            content_type='application/json'
        )
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Configuration saved: {data}")
        else:
            print(f"❌ Failed to save config: {response.content}")
            return False
    except Exception as e:
        print(f"❌ Error saving config: {str(e)}")
        return False
    
    # Test 4: Get SMTP configuration again (should now have data)
    print("\n🔍 Test 4: Get Updated SMTP Configuration")
    try:
        response = client.get('/api/admin/email/smtp/config/')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Configuration retrieved: configured={data.get('configured')}")
            print(f"   SMTP Host: {data.get('smtp_host')}")
            print(f"   Email User: {data.get('email_user')}")
            print(f"   Password: {data.get('email_password')}")  # Should be masked
        else:
            print(f"❌ Failed to get updated config: {response.content}")
            return False
    except Exception as e:
        print(f"❌ Error getting updated config: {str(e)}")
        return False
    
    # Test 5: Test SMTP connection (will fail with fake credentials, but should handle gracefully)
    print("\n🔍 Test 5: Test SMTP Connection")
    try:
        response = client.post('/api/admin/email/smtp/config/test/')
        print(f"Status Code: {response.status_code}")
        
        # This should return 400 because we're using fake credentials
        if response.status_code in [200, 400]:
            data = response.json()
            print(f"✅ Connection test response: {data}")
        else:
            print(f"❌ Unexpected response: {response.content}")
            return False
    except Exception as e:
        print(f"❌ Error testing connection: {str(e)}")
        return False
    
    # Test 6: Delete SMTP configuration
    print("\n🔍 Test 6: Delete SMTP Configuration")
    try:
        response = client.delete('/api/admin/email/smtp/config/delete/')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Configuration deleted: {data}")
        else:
            print(f"❌ Failed to delete config: {response.content}")
            return False
    except Exception as e:
        print(f"❌ Error deleting config: {str(e)}")
        return False
    
    # Test 7: Verify configuration is deleted
    print("\n🔍 Test 7: Verify Configuration Deleted")
    try:
        response = client.get('/api/admin/email/smtp/config/')
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if not data.get('configured'):
                print(f"✅ Configuration properly deleted: {data}")
            else:
                print(f"❌ Configuration still exists: {data}")
                return False
        else:
            print(f"❌ Failed to verify deletion: {response.content}")
            return False
    except Exception as e:
        print(f"❌ Error verifying deletion: {str(e)}")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 All Email Configuration API tests passed!")
    return True

def main():
    """Main function to run API tests"""
    success = test_email_config_api()
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())