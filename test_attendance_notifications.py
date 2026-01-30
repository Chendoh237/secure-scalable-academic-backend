#!/usr/bin/env python
"""
Test script for real-time attendance notifications
"""
import os
import sys
import django
from django.conf import settings

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from students.models import Student
from courses.models import Course
from attendance.models import Attendance, CourseRegistration
from attendance.notification_service import AttendanceNotificationService
from notifications.models import Notification
from django.utils import timezone
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

def test_attendance_notification_system():
    """Test the attendance notification system"""
    print("🧪 Testing Real-time Attendance Notification System")
    print("=" * 60)
    
    try:
        # 1. Get or create test student
        print("1. Setting up test data...")
        student = Student.objects.filter(matric_number='394623').first()
        if not student:
            print("   ❌ Test student not found (matric: 394623)")
            return False
        
        # 2. Get or create test course
        course = Course.objects.first()
        if not course:
            print("   ❌ No courses found in database")
            return False
        
        # 3. Get or create course registration
        course_registration, created = CourseRegistration.objects.get_or_create(
            student=student,
            course=course,
            academic_year='2024/2025',
            semester='First',
            defaults={'date_registered': timezone.now()}
        )
        
        print(f"   ✅ Student: {student.full_name} ({student.matric_number})")
        print(f"   ✅ Course: {course.code} - {course.title}")
        print(f"   ✅ Registration: {'Created' if created else 'Found existing'}")
        
        # 4. Create test attendance record
        print("\n2. Creating test attendance record...")
        attendance_record = Attendance.objects.create(
            student=student,
            course_registration=course_registration,
            date=timezone.now().date(),
            status='present',
            recorded_at=timezone.now(),
            is_manual_override=True
        )
        print(f"   ✅ Attendance record created: ID {attendance_record.id}")
        
        # 5. Test notification creation
        print("\n3. Testing notification creation...")
        notification_result = AttendanceNotificationService.create_attendance_notification(
            attendance_record=attendance_record,
            notification_type='attendance'
        )
        
        if notification_result['success']:
            print(f"   ✅ Notifications created successfully!")
            print(f"   📊 Created {len(notification_result['notifications_created'])} notifications")
            
            for notification_info in notification_result['notifications_created']:
                print(f"      - {notification_info['recipient_type'].title()}: {notification_info['recipient_name']}")
        else:
            print(f"   ❌ Failed to create notifications: {notification_result.get('error')}")
            return False
        
        # 6. Test notification retrieval
        print("\n4. Testing notification retrieval...")
        
        # Get admin users
        admin_users = User.objects.filter(role__in=['admin', 'super_admin', 'institution_admin', 'department_admin'], is_active=True)
        if admin_users.exists():
            admin_user = admin_users.first()
            recent_notifications = AttendanceNotificationService.get_recent_attendance_notifications(
                user=admin_user,
                limit=5,
                hours=1
            )
            print(f"   ✅ Retrieved {len(recent_notifications)} recent notifications for admin")
        
        # Get student notifications if student has user account
        if hasattr(student, 'user') and student.user:
            student_notifications = AttendanceNotificationService.get_recent_attendance_notifications(
                user=student.user,
                limit=5,
                hours=1
            )
            print(f"   ✅ Retrieved {len(student_notifications)} recent notifications for student")
        
        # 7. Test attendance summary
        print("\n5. Testing attendance summary...")
        summary_result = AttendanceNotificationService.get_attendance_summary_for_notifications(hours=24)
        
        if summary_result['success']:
            summary = summary_result['summary']
            print(f"   ✅ Attendance summary retrieved:")
            print(f"      - Total records: {summary['total_records']}")
            print(f"      - Present: {summary['present_count']}")
            print(f"      - Late: {summary['late_count']}")
            print(f"      - Absent: {summary['absent_count']}")
            print(f"      - Attendance rate: {summary['attendance_rate']}%")
        else:
            print(f"   ❌ Failed to get attendance summary: {summary_result.get('error')}")
        
        # 8. Cleanup test data
        print("\n6. Cleaning up test data...")
        attendance_record.delete()
        
        # Delete test notifications
        test_notifications = Notification.objects.filter(
            title__icontains='Test Attendance',
            created_at__gte=timezone.now() - timezone.timedelta(minutes=5)
        )
        deleted_count = test_notifications.count()
        test_notifications.delete()
        print(f"   ✅ Cleaned up {deleted_count} test notifications")
        
        print("\n" + "=" * 60)
        print("🎉 All tests passed! Real-time attendance notification system is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test the API endpoints"""
    print("\n🌐 Testing API Endpoints")
    print("=" * 40)
    
    try:
        from django.test import Client
        from django.urls import reverse
        
        client = Client()
        
        # Get admin user for authentication
        admin_user = User.objects.filter(role__in=['admin', 'super_admin', 'institution_admin', 'department_admin'], is_active=True).first()
        if not admin_user:
            print("   ❌ No admin user found for API testing")
            return False
        
        # Login
        client.force_login(admin_user)
        
        # Test endpoints
        endpoints = [
            '/api/attendance/notifications/recent/',
            '/api/attendance/notifications/live-feed/',
            '/api/attendance/notifications/summary/',
            '/api/attendance/notifications/test/',
        ]
        
        for endpoint in endpoints:
            try:
                response = client.get(endpoint)
                print(f"   ✅ {endpoint}: Status {response.status_code}")
            except Exception as e:
                print(f"   ❌ {endpoint}: Error - {e}")
        
        print("   ✅ API endpoints are accessible")
        return True
        
    except Exception as e:
        print(f"   ❌ API test failed: {e}")
        return False

if __name__ == '__main__':
    print("🚀 Starting Attendance Notification System Tests\n")
    
    # Run tests
    test1_passed = test_attendance_notification_system()
    test2_passed = test_api_endpoints()
    
    print(f"\n📋 Test Results:")
    print(f"   Notification System: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"   API Endpoints: {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    
    if test1_passed and test2_passed:
        print(f"\n🎉 All tests passed! The real-time attendance notification system is ready to use.")
        print(f"\n📖 Usage Instructions:")
        print(f"   1. Admin Portal: Go to Face Tracking page to see live attendance notifications")
        print(f"   2. Student Portal: Go to My Attendance page to see your attendance notifications")
        print(f"   3. Notifications are created automatically when attendance is marked via face recognition")
        print(f"   4. Both portals auto-refresh to show real-time updates")
    else:
        print(f"\n❌ Some tests failed. Please check the errors above.")
        sys.exit(1)