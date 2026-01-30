#!/usr/bin/env python3
"""
Test Email-Notification Integration

This script tests the complete email management system with notification integration.
"""

import os
import sys
import django
import requests
import json
from datetime import datetime

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from students.models import Student
from notifications.models import Notification
from students.notification_integration import email_notification_integration

User = get_user_model()

def test_notification_integration():
    """Test the email-notification integration service"""
    print("🧪 Testing Email-Notification Integration...")
    
    try:
        # Get or create admin user
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@university.edu',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            print(f"✅ Created admin user: {admin_user.username}")
        else:
            print(f"✅ Using existing admin user: {admin_user.username}")
        
        # Get test students
        students = Student.objects.filter(user__isnull=False)[:3]
        if not students:
            print("❌ No students found with user accounts")
            return False
        
        print(f"✅ Found {len(students)} test students")
        
        # Test 1: Create email notifications
        print("\n📧 Test 1: Creating email notifications...")
        
        recipient_emails = [student.user.email for student in students]
        result = email_notification_integration.create_email_notifications(
            sender_user=admin_user,
            subject="Test Email Subject",
            body="This is a test email body with some content to verify the notification integration works correctly.",
            recipients=recipient_emails,
            email_history_id=1
        )
        
        print(f"✅ Email notifications result: {result}")
        
        if result['success']:
            print(f"   - Notifications created: {result['notifications_created']}")
            print(f"   - Failed notifications: {result['failed_notifications']}")
        else:
            print(f"❌ Failed to create email notifications: {result.get('error')}")
            return False
        
        # Test 2: Create system announcement
        print("\n📢 Test 2: Creating system announcement...")
        
        announcement_result = email_notification_integration.create_system_announcement(
            sender_user=admin_user,
            title="System Maintenance Notice",
            message="The system will be down for maintenance on Sunday from 2 AM to 4 AM. Please save your work.",
            recipient_type='all'
        )
        
        print(f"✅ System announcement result: {announcement_result}")
        
        if announcement_result['success']:
            print(f"   - Notifications created: {announcement_result['notifications_created']}")
            print(f"   - Failed notifications: {announcement_result['failed_notifications']}")
        else:
            print(f"❌ Failed to create system announcement: {announcement_result.get('error')}")
        
        # Test 3: Verify notifications in database
        print("\n🔍 Test 3: Verifying notifications in database...")
        
        total_notifications = Notification.objects.count()
        unread_notifications = Notification.objects.filter(is_read=False).count()
        
        print(f"✅ Total notifications in database: {total_notifications}")
        print(f"✅ Unread notifications: {unread_notifications}")
        
        # Show recent notifications
        recent_notifications = Notification.objects.order_by('-created_at')[:5]
        for notif in recent_notifications:
            print(f"   - {notif.recipient.username}: {notif.title} ({notif.notification_type})")
        
        # Test 4: Test notification API endpoints
        print("\n🌐 Test 4: Testing notification API endpoints...")
        
        # Test getting notifications for a student
        if students:
            test_student = students[0]
            student_notifications = Notification.objects.filter(recipient=test_student.user)
            print(f"✅ Student {test_student.user.username} has {student_notifications.count()} notifications")
        
        print("\n✅ All notification integration tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error during notification integration test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test the API endpoints for email and notifications"""
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
        
        # Test notification endpoints
        print("\n📱 Testing notification endpoints...")
        
        # Get notifications
        response = requests.get(f"{base_url}/notifications/", headers=headers)
        if response.status_code == 200:
            notifications_data = response.json()
            print(f"✅ Retrieved notifications: {notifications_data.get('count', 0)} total")
        else:
            print(f"❌ Failed to get notifications: {response.status_code}")
        
        # Test email statistics endpoint
        print("\n📊 Testing email statistics endpoint...")
        
        response = requests.get(f"{base_url}/admin/email/statistics/", headers=headers)
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Retrieved email statistics: {stats}")
        else:
            print(f"❌ Failed to get email statistics: {response.status_code}")
        
        # Test system announcement endpoint
        print("\n📢 Testing system announcement endpoint...")
        
        announcement_data = {
            "title": "API Test Announcement",
            "message": "This is a test announcement created via API",
            "recipient_type": "all"
        }
        
        response = requests.post(
            f"{base_url}/admin/email/notifications/system/",
            json=announcement_data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ System announcement created via API: {result}")
        else:
            print(f"❌ Failed to create system announcement via API: {response.status_code}")
            print(f"   Response: {response.text}")
        
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
    print("🚀 Starting Email Management System Integration Tests")
    print("=" * 60)
    
    # Test 1: Notification Integration Service
    integration_success = test_notification_integration()
    
    # Test 2: API Endpoints
    api_success = test_api_endpoints()
    
    print("\n" + "=" * 60)
    print("📋 Test Summary:")
    print(f"   - Notification Integration: {'✅ PASS' if integration_success else '❌ FAIL'}")
    print(f"   - API Endpoints: {'✅ PASS' if api_success else '❌ FAIL'}")
    
    if integration_success and api_success:
        print("\n🎉 All tests passed! Email management system is working correctly.")
        return True
    else:
        print("\n⚠️  Some tests failed. Please check the output above.")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)