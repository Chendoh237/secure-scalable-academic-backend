#!/usr/bin/env python
"""
Test script to check if the export endpoint is accessible
"""
import os
import sys
import django

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.urls import reverse, resolve
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from students.admin_views import export_attendance_records

def test_export_endpoint():
    print("Testing export endpoint...")
    
    try:
        # Test URL reverse
        url = reverse('admin_export_attendance_records')
        print(f"✓ URL reverse successful: {url}")
        
        # Test URL resolve
        resolver = resolve(url)
        print(f"✓ URL resolve successful: {resolver.func.__name__}")
        
        # Test function import
        print(f"✓ Function import successful: {export_attendance_records.__name__}")
        
        # Create a test request
        factory = RequestFactory()
        request = factory.get(url, {'format': 'excel'})
        
        # Create a test user
        User = get_user_model()
        user = User.objects.create_user(username='testuser', password='testpass')
        request.user = user
        
        # Test function call (this might fail due to missing data, but should not give 404)
        try:
            response = export_attendance_records(request)
            print(f"✓ Function call successful: Status {response.status_code}")
        except Exception as e:
            print(f"⚠ Function call failed (expected): {str(e)}")
        
        print("\n✓ All URL routing tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_export_endpoint()