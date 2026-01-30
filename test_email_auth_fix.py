#!/usr/bin/env python
"""
Test script to verify email management API authentication fix
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

def test_email_endpoints():
    """Test email management endpoints with JWT authentication"""
    
    base_url = "http://localhost:8000"
    
    # Test endpoints that should return 401 without authentication
    endpoints_to_test = [
        "/admin/email/smtp/config/",
        "/admin/email/smtp/providers/",
        "/admin/email/templates/",
        "/admin/email/recipients/options/",
        "/admin/email/history/",
        "/admin/email/statistics/"
    ]
    
    print("Testing email management API endpoints...")
    print("=" * 50)
    
    for endpoint in endpoints_to_test:
        try:
            url = f"{base_url}{endpoint}"
            print(f"\nTesting: {endpoint}")
            
            # Test without authentication - should return 401
            response = requests.get(url, timeout=5)
            print(f"  Status Code: {response.status_code}")
            
            if response.status_code == 401:
                print(f"  ✅ Correctly returns 401 Unauthorized (JWT auth working)")
            elif response.status_code == 404:
                print(f"  ❌ Returns 404 Not Found (URL routing issue)")
            elif response.status_code == 302:
                print(f"  ❌ Returns 302 Redirect (still using session auth)")
                if 'Location' in response.headers:
                    print(f"     Redirects to: {response.headers['Location']}")
            else:
                print(f"  ⚠️  Unexpected status code: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"  ⚠️  Connection failed - Django server not running")
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("Test completed!")
    print("\nExpected results:")
    print("- 401 Unauthorized = JWT authentication working correctly")
    print("- 404 Not Found = URL routing issue")
    print("- 302 Redirect = Still using Django session authentication")

if __name__ == "__main__":
    test_email_endpoints()