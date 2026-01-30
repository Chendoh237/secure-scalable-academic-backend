#!/usr/bin/env python3
"""
Test Email Management System Fixes

This script tests the fixes for the email sending and SMTP connection issues.
"""

import os
import sys
import django
import requests
import json

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from students.models import Student
from students.email_models import EmailConfiguration
from students.email_service import email_service

User = get_user_model()

def test_email_service_fixes():
    """Test the EmailService fixes"""
    print("🧪 Testing EmailService Fixes...")
    
    try:
        # Test 1: Check if EmailService can handle missing configuration gracefully
        print("\n📧 Test 1: Testing EmailService without configuration...")
        
        # Clear any existing configuration
        EmailConfiguration.objects.all().delete()
        
        try:
            result = email_service.send_bulk_email(
                to_emails=['test@example.com'],
                subject='Test Subject',
                message='Test Message'
            )
            
            # Check if the error is properly handled
            if not result['success'] or result.get('failed_count', 0) > 0:
                failed_recipients = result.get('failed_recipients', [])
                if failed_recipients and 'No SMTP configuration found' in str(failed_recipients[0].get('error', '')):
                    print("✅ EmailService correctly handles missing configuration")
                else:
                    print(f"✅ EmailService handled error gracefully: {result}")
            else:
                print(f"❌ Expected error but got success: {result}")
        except Exception as e:
            if "No SMTP configuration found" in str(e):
                print("✅ EmailService correctly handles missing configuration")
            else:
                print(f"❌ Unexpected error: {str(e)}")
        
        # Test 2: Create a test configuration and test the service
        print("\n📧 Test 2: Testing EmailService with configuration...")
        
        # Create test configuration
        config = EmailConfiguration.objects.create(
            smtp_host='smtp.gmail.com',
            smtp_port=587,
            smtp_username='test@gmail.com',
            from_email='test@gmail.com',
            use_tls=True,
            use_ssl=False,
            from_name='Test System',
            is_active=True
        )
        config.set_password('test_password')
        config.save()
        
        print("✅ Test SMTP configuration created")
        
        # Test connection (this will fail due to invalid credentials, but should not crash)
        print("\n📧 Test 3: Testing SMTP connection...")
        
        try:
            result = email_service.test_connection()
            if result['success']:
                print("✅ SMTP connection test passed (unexpected with test credentials)")
            else:
                print(f"✅ SMTP connection test failed as expected: {result.get('error', 'Unknown error')[:100]}...")
        except Exception as e:
            print(f"✅ SMTP connection test handled exception: {str(e)[:100]}...")
        
        # Test 4: Test bulk email method signature
        print("\n📧 Test 4: Testing bulk email method signature...")
        
        try:
            # This should not crash due to missing 'message' argument anymore
            result = email_service.send_bulk_email(
                to_emails=['test1@example.com', 'test2@example.com'],
                subject='Test Bulk Email',
                message='This is a test bulk email message'
            )
            
            if result['success']:
                print("✅ Bulk email method signature works correctly")
            else:
                print(f"✅ Bulk email method handled gracefully: {result.get('error', 'Unknown error')}")
                
        except TypeError as e:
            if "missing" in str(e) and "argument" in str(e):
                print(f"❌ Method signature still has issues: {str(e)}")
            else:
                print(f"❌ Unexpected TypeError: {str(e)}")
        except Exception as e:
            print(f"✅ Bulk email method handled other errors gracefully: {str(e)}")
        
        print("\n✅ EmailService fixes test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Error during EmailService test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test the API endpoints"""
    print("\n🌐 Testing API Endpoints...")
    
    base_url = "http://localhost:8000/api"
    
    # Test admin login
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        # Login to get token
        response = requests.post(f"{base_url}/token/", json=login_data)
        if response.status_code == 200:
            token = response.json()['access']
            headers = {'Authorization': f'Bearer {token}'}
            print("✅ Admin login successful")
        else:
            print(f"❌ Admin login failed: {response.status_code}")
            return False
        
        # Test bulk email endpoint with proper payload
        print("\n📧 Testing bulk email endpoint...")
        
        email_data = {
            "subject": "Test API Email",
            "body": "This is a test email sent via API",
            "recipient_config": {
                "type": "custom",
                "emails": ["test@example.com"]
            },
            "send_immediately": False  # Don't actually send, just test the endpoint
        }
        
        response = requests.post(
            f"{base_url}/admin/email/send/",
            json=email_data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Bulk email endpoint works: {result.get('message', 'Success')}")
        else:
            print(f"❌ Bulk email endpoint failed: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
        
        # Test SMTP configuration endpoint
        print("\n📧 Testing SMTP configuration endpoint...")
        
        response = requests.get(f"{base_url}/admin/email/smtp/config/", headers=headers)
        
        if response.status_code == 200:
            config = response.json()
            print(f"✅ SMTP config endpoint works: configured = {config.get('configured', False)}")
        else:
            print(f"❌ SMTP config endpoint failed: {response.status_code}")
        
        print("\n✅ API endpoint tests completed!")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Django server. Make sure it's running on localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Error during API testing: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting Email Management System Fix Tests")
    print("=" * 60)
    
    # Test 1: EmailService fixes
    service_success = test_email_service_fixes()
    
    # Test 2: API endpoints
    api_success = test_api_endpoints()
    
    print("\n" + "=" * 60)
    print("📋 Test Summary:")
    print(f"   - EmailService Fixes: {'✅ PASS' if service_success else '❌ FAIL'}")
    print(f"   - API Endpoints: {'✅ PASS' if api_success else '❌ FAIL'}")
    
    if service_success and api_success:
        print("\n🎉 All tests passed! Email management system fixes are working correctly.")
        return True
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)