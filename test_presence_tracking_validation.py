#!/usr/bin/env python3
"""
Test script to validate presence tracking data structure and calculations
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from attendance.models import Attendance, CourseRegistration
from students.models import Student
from courses.models import Course
from django.utils import timezone

def test_presence_tracking_fields():
    """Test that all presence tracking fields exist and work correctly"""
    
    print("🔍 Testing Presence Tracking Data Structure...")
    
    # Test 1: Check if all fields exist in the model
    print("\n1. Checking model fields...")
    
    required_fields = [
        'presence_duration',
        'total_class_duration', 
        'presence_percentage',
        'first_detected_at',
        'last_detected_at',
        'detection_count'
    ]
    
    attendance_fields = [field.name for field in Attendance._meta.get_fields()]
    
    for field in required_fields:
        if field in attendance_fields:
            print(f"   ✅ {field} - EXISTS")
        else:
            print(f"   ❌ {field} - MISSING")
    
    # Test 2: Check status choices include 'partial'
    print("\n2. Checking status choices...")
    status_choices = dict(Attendance.STATUS_CHOICES)
    if 'partial' in status_choices:
        print(f"   ✅ 'partial' status - EXISTS ({status_choices['partial']})")
    else:
        print(f"   ❌ 'partial' status - MISSING")
    
    # Test 3: Test calculation methods
    print("\n3. Testing calculation methods...")
    
    # Create a test attendance record
    try:
        # Get or create test data
        student = Student.objects.first()
        if not student:
            print("   ⚠️  No students found in database")
            return
            
        course_reg = CourseRegistration.objects.filter(student=student).first()
        if not course_reg:
            print("   ⚠️  No course registrations found")
            return
        
        # Create test attendance record
        test_attendance = Attendance(
            student=student,
            course_registration=course_reg,
            date=timezone.now().date(),
            presence_duration=timedelta(minutes=67, seconds=30),  # 67.5 minutes
            total_class_duration=timedelta(minutes=90),  # 90 minutes
            detection_count=15,
            first_detected_at=timezone.now() - timedelta(minutes=67, seconds=30),
            last_detected_at=timezone.now() - timedelta(minutes=0)
        )
        
        # Test calculation methods
        percentage = test_attendance.calculate_presence_percentage()
        expected_percentage = (67.5 / 90) * 100  # Should be 75.0%
        
        print(f"   📊 Presence calculation test:")
        print(f"      Duration: 67.5 min / 90 min")
        print(f"      Calculated: {percentage:.1f}%")
        print(f"      Expected: {expected_percentage:.1f}%")
        
        if abs(percentage - expected_percentage) < 0.1:
            print(f"   ✅ calculate_presence_percentage() - CORRECT")
        else:
            print(f"   ❌ calculate_presence_percentage() - INCORRECT")
        
        # Test status determination
        status = test_attendance.determine_attendance_status()
        expected_status = 'present'  # 75% should be 'present'
        
        print(f"   📊 Status determination test:")
        print(f"      Percentage: {percentage:.1f}%")
        print(f"      Determined: {status}")
        print(f"      Expected: {expected_status}")
        
        if status == expected_status:
            print(f"   ✅ determine_attendance_status() - CORRECT")
        else:
            print(f"   ❌ determine_attendance_status() - INCORRECT")
        
        # Test presence summary
        summary = test_attendance.get_presence_summary()
        print(f"   📊 Presence summary test:")
        print(f"      Summary keys: {list(summary.keys())}")
        
        expected_keys = [
            'presence_duration_minutes',
            'total_class_duration_minutes',
            'presence_percentage',
            'detection_count',
            'first_detected',
            'last_detected',
            'status',
            'is_manual_override'
        ]
        
        missing_keys = [key for key in expected_keys if key not in summary]
        if not missing_keys:
            print(f"   ✅ get_presence_summary() - ALL KEYS PRESENT")
        else:
            print(f"   ❌ get_presence_summary() - MISSING KEYS: {missing_keys}")
        
        print(f"      Duration: {summary['presence_duration_minutes']:.1f} min")
        print(f"      Percentage: {summary['presence_percentage']:.1f}%")
        print(f"      Detections: {summary['detection_count']}")
        
    except Exception as e:
        print(f"   ❌ Error testing calculation methods: {e}")
    
    # Test 4: Test different threshold scenarios
    print("\n4. Testing threshold scenarios...")
    
    test_cases = [
        (90, 90, 'present'),   # 100% - should be present
        (67.5, 90, 'present'), # 75% - should be present  
        (60, 90, 'partial'),   # 66.7% - should be partial
        (45, 90, 'partial'),   # 50% - should be partial
        (30, 90, 'late'),      # 33.3% - should be late
        (22.5, 90, 'late'),    # 25% - should be late
        (15, 90, 'absent'),    # 16.7% - should be absent
        (0, 90, 'absent'),     # 0% - should be absent
    ]
    
    for presence_min, total_min, expected in test_cases:
        test_record = Attendance(
            student=student,
            course_registration=course_reg,
            presence_duration=timedelta(minutes=presence_min),
            total_class_duration=timedelta(minutes=total_min)
        )
        
        percentage = test_record.calculate_presence_percentage()
        status = test_record.determine_attendance_status()
        
        result = "✅" if status == expected else "❌"
        print(f"   {result} {presence_min}min/{total_min}min = {percentage:.1f}% → {status} (expected: {expected})")

def test_database_records():
    """Test existing database records"""
    
    print("\n🗄️  Testing Database Records...")
    
    total_records = Attendance.objects.count()
    print(f"   Total attendance records: {total_records}")
    
    if total_records > 0:
        # Check records with presence data
        with_presence = Attendance.objects.exclude(presence_percentage__isnull=True).count()
        with_duration = Attendance.objects.exclude(presence_duration__isnull=True).count()
        with_detections = Attendance.objects.filter(detection_count__gt=0).count()
        
        print(f"   Records with presence percentage: {with_presence}")
        print(f"   Records with presence duration: {with_duration}")
        print(f"   Records with detections: {with_detections}")
        
        # Show sample records
        sample_records = Attendance.objects.all()[:3]
        print(f"\n   Sample records:")
        for i, record in enumerate(sample_records, 1):
            print(f"   {i}. {record.student.matric_number} - {record.status}")
            print(f"      Presence: {record.presence_percentage}% | Detections: {record.detection_count}")
    else:
        print("   No attendance records found")

if __name__ == "__main__":
    print("=" * 60)
    print("🎯 PRESENCE TRACKING VALIDATION TEST")
    print("=" * 60)
    
    try:
        test_presence_tracking_fields()
        test_database_records()
        
        print("\n" + "=" * 60)
        print("✅ VALIDATION COMPLETE")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        import traceback
        traceback.print_exc()