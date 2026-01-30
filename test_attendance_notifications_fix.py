#!/usr/bin/env python
"""
Test script to debug attendance notifications 403 error.
"""

import os
import sys
import django
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

User = get_user_model()

def test_attendance_notifications_permissions():
    """Test attendance notifications permissions and endpoints."""
    
    print("🔧 Testing Attendance Notifications Permissions")
    print("=" * 60)
    
    # Find admin and student users
    admin_user = User.objects.filter(role__in=['admin', 'super_admin']).first()
    student_user = User.objects.filter(role='student').first()
    
    if not admin_user:
        print("❌ No admin user found")
        return False
    
    if not student_user:
        print("❌ No student user found")
        return False
    
    print(f"✅ Admin user: {admin_user.username} (role: {admin_user.role})")
    print(f"✅ Student user: {student_user.username} (role: {student_user.role})")
    
    # Test is_admin_user method
    print(f"\n🔍 Testing is_admin_user() method:")
    print(f"   Admin user is_admin_user(): {admin_user.is_admin_user()}")
    print(f"   Student user is_admin_user(): {student_user.is_admin_user()}")
    
    # Test with Django test client
    client = Client()
    
    print(f"\n🌐 Testing endpoints with Django test client:")
    
    # Test as admin user
    client.force_login(admin_user)
    
    try:
        response = client.get('/api/attendance/notifications/live-feed/?hours=2&limit=20')
        print(f"   Admin access to live-feed: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response success: {data.get('success', False)}")
        else:
            print(f"   Response content: {response.content.decode()}")
    except Exception as e:
        print(f"   Error testing admin access: {e}")
    
    # Test as student user
    client.force_login(student_user)
    
    try:
        response = client.get('/api/attendance/notifications/live-feed/?hours=2&limit=20')
        print(f"   Student access to live-feed: {response.status_code}")
        if response.status_code != 403:
            print(f"   ⚠️  Student should get 403, got {response.status_code}")
        else:
            print(f"   ✅ Student correctly blocked with 403")
    except Exception as e:
        print(f"   Error testing student access: {e}")
    
    # Test student-specific endpoint
    try:
        response = client.get('/api/attendance/notifications/student/?hours=24&limit=10')
        print(f"   Student access to student notifications: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Student notifications success: {data.get('success', False)}")
    except Exception as e:
        print(f"   Error testing student notifications: {e}")
    
    # Test with actual HTTP request (like frontend)
    print(f"\n🌍 Testing with actual HTTP requests:")
    
    # Get admin token
    try:
        login_response = requests.post('http://localhost:8000/api/token/', {
            'username': admin_user.username,
            'password': 'admin123'  # Default password
        })
        
        if login_response.status_code == 200:
            admin_token = login_response.json().get('access')
            print(f"   ✅ Admin login successful")
            
            # Test live feed with token
            headers = {'Authorization': f'Bearer {admin_token}'}
            feed_response = requests.get(
                'http://localhost:8000/api/attendance/notifications/live-feed/?hours=2&limit=20',
                headers=headers
            )
            print(f"   Admin live-feed HTTP request: {feed_response.status_code}")
            
        else:
            print(f"   ❌ Admin login failed: {login_response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print(f"   ⚠️  Server not running on localhost:8000")
    except Exception as e:
        print(f"   Error with HTTP request: {e}")
    
    return True

if __name__ == "__main__":
    success = test_attendance_notifications_permissions()
    sys.exit(0 if success else 1)