#!/usr/bin/env python3
"""
Test Face Tracking Integration with Timetable System
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from rest_framework.test import force_authenticate
from attendance.face_tracking_views import (
    get_face_model_status, 
    get_current_timetable_info,
    get_today_attendance_summary
)

def test_face_tracking_endpoints():
    """Test face tracking endpoints"""
    print("Testing Face Tracking Integration...")
    
    # Create a test request factory
    factory = RequestFactory()
    
    # Get a test user (admin)
    user = User.objects.filter(is_staff=True).first()
    if not user:
        print("❌ No admin user found. Please create an admin user first.")
        return
    
    print(f"✅ Using admin user: {user.username}")
    
    # Test 1: Face Model Status
    print("\n1. Testing Face Model Status...")
    try:
        request = factory.get('/attendance/face-tracking/model-status/')
        response = get_face_model_status(request)
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.data}")
        if response.status_code == 200:
            print("   ✅ Face model status endpoint working")
        else:
            print("   ❌ Face model status endpoint failed")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    # Test 2: Current Timetable Info
    print("\n2. Testing Current Timetable Info...")
    try:
        request = factory.get('/attendance/face-tracking/current-timetable/')
        response = get_current_timetable_info(request)
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.data}")
        if response.status_code == 200:
            print("   ✅ Current timetable info endpoint working")
        else:
            print("   ❌ Current timetable info endpoint failed")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    # Test 3: Today's Attendance Summary
    print("\n3. Testing Today's Attendance Summary...")
    try:
        request = factory.get('/attendance/face-tracking/attendance-summary/')
        response = get_today_attendance_summary(request)
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.data}")
        if response.status_code == 200:
            print("   ✅ Attendance summary endpoint working")
        else:
            print("   ❌ Attendance summary endpoint failed")
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
    
    print("\n" + "="*50)
    print("Face Tracking Integration Test Complete!")
    print("="*50)

if __name__ == "__main__":
    test_face_tracking_endpoints()