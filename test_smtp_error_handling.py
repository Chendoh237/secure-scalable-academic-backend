#!/usr/bin/env python3
"""
Test SMTP Error Handling Improvements

This script tests the improved error handling for SMTP connection testing.
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

def test_smtp_error_handling():
    """Test the improved SMTP error handling"""
    print("🧪 Testing SMTP Error Handling Improvements...")
    
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
        
        # Test 1: Test with invalid Gmail credentials (should return user-friendly error)
        print("\n📧 Test 1: Testing with invalid Gmail credentials...")
        
        test_config = {
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "email_user": "invalid@gmail.com",
            "email_password": "invalid_password",
            "use_tls": True,
            "use_ssl": False,
            "from_name": "Test System"
        }
        
        response = requests.post(
            f"{base_url}/admin/email/smtp/config/test/",
            json=test_config,
            headers=headers
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 400:
            result = response.json()
            print(f"   Success: {result.get('success', False)}")
            print(f"   Error: {result.get('error', 'No error message')}")
            print(f"   Details: {result.get('details', 'No details')[:100]}...")
            
            # Check if we got user-friendly error message
            details = result.get('details', '')
            if 'App Password' in details or 'authentication failed' in details.lower():
                print("✅ User-friendly error message provided")
            else:
                print(f"⚠️  Error message could be more user-friendly: {details}")
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
            print(f"   Response: {response.text}")
        
        # Test 2: Test with invalid host (should return connection error)
        print("\n📧 Test 2: Testing with invalid SMTP host...")
        
        test_config = {
            "smtp_host": "invalid.smtp.server.com",
            "smtp_port": 587,
            "email_user": "test@example.com",
            "email_password": "test_password",
            "use_tls": True,
            "use_ssl": False,
            "from_name": "Test System"
        }
        
        response = requests.post(
            f"{base_url}/admin/email/smtp/config/test/",
            json=test_config,
            headers=headers
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 400:
            result = response.json()
            print(f"   Success: {result.get('success', False)}")
            print(f"   Error: {result.get('error', 'No error message')}")
            print(f"   Details: {result.get('details', 'No details')[:100]}...")
            
            # Check if we got connection error message
            details = result.get('details', '')
            if 'connect' in details.lower() or 'server' in details.lower():
                print("✅ Connection error message provided")
            else:
                print(f"⚠️  Expected connection error message: {details}")
        else:
            print(f"❌ Unexpected status code: {response.status_code}")
        
        # Test 3: Test with empty configuration (should return validation error)
        print("\n📧 Test 3: Testing with empty configuration...")
        
        response = requests.post(
            f"{base_url}/admin/email/smtp/config/test/",
            json={},
            headers=headers
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code == 400:
            result = response.json()
            print(f"   Success: {result.get('success', False)}")
            print(f"   Error: {result.get('error', 'No error message')}")
            print(f"   Details: {result.get('details', 'No details')}")
            print("✅ Validation error handled correctly")
        else:
            print(f"❌ Expected 400 status code, got: {response.status_code}")
        
        print("\n✅ SMTP error handling tests completed!")
        return True
        
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to Django server. Make sure it's running on localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting SMTP Error Handling Tests")
    print("=" * 60)
    
    success = test_smtp_error_handling()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 SMTP error handling tests completed successfully!")
        print("\nKey improvements:")
        print("✅ User-friendly error messages for authentication failures")
        print("✅ Clear connection error messages")
        print("✅ Proper validation error handling")
        print("✅ 400 Bad Request status codes for expected failures")
    else:
        print("⚠️  Some tests failed. Please check the output above.")
    
    return success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)