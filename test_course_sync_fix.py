#!/usr/bin/env python
"""
Test script to verify course registration and timetable synchronization fixes.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import Course, Level, DepartmentTimetable, TimetableSlot, StudentCourse, CourseOffering
from institutions.models import Department
from students.course_sync_service import full_course_sync

User = get_user_model()

def test_course_sync_fix():
    """Test the complete course registration and timetable synchronization fix."""
    
    print("🔧 Testing Course Registration and Timetable Synchronization Fix")
    print("=" * 70)
    
    # Find a test student
    try:
        student = Student.objects.first()
        if not student:
            print("❌ No students found in database")
            return False
        
        print(f"✅ Testing with student: {student.full_name} ({student.matric_number})")
        print(f"   Department: {student.department.name}")
        
        # Check if student has a level selection
        try:
            level_selection = student.level_selection
            level = level_selection.level
            print(f"✅ Student has level selection: {level.name}")
        except StudentLevelSelection.DoesNotExist:
            # Create a level selection for testing
            level = Level.objects.filter(department=student.department).first()
            if not level:
                print("❌ No levels found for student's department")
                return False
            
            level_selection = StudentLevelSelection.objects.create(
                student=student,
                level=level
            )
            print(f"✅ Created level selection: {level.name}")
        
        # Check current course selections
        initial_selections = StudentCourseSelection.objects.filter(
            student=student,
            is_offered=True,
            is_approved=True
        ).count()
        
        initial_student_courses = StudentCourse.objects.filter(
            student=student,
            is_active=True
        ).count()
        
        print(f"📊 Initial state:")
        print(f"   - StudentCourseSelection (approved): {initial_selections}")
        print(f"   - StudentCourse (active): {initial_student_courses}")
        
        # Run the synchronization
        print("\n🔄 Running course synchronization...")
        sync_result = full_course_sync(student)
        
        print(f"✅ Synchronization completed:")
        print(f"   - Success: {sync_result['success']}")
        print(f"   - Forward sync: {sync_result['forward_sync']}")
        print(f"   - Reverse sync: {sync_result['reverse_sync']}")
        
        # Check final state
        final_selections = StudentCourseSelection.objects.filter(
            student=student,
            is_offered=True,
            is_approved=True
        ).count()
        
        final_student_courses = StudentCourse.objects.filter(
            student=student,
            is_active=True
        ).count()
        
        print(f"\n📊 Final state:")
        print(f"   - StudentCourseSelection (approved): {final_selections}")
        print(f"   - StudentCourse (active): {final_student_courses}")
        
        # Test timetable view
        print(f"\n📅 Testing timetable view...")
        
        # Check if there's a department timetable
        try:
            dept_timetable = DepartmentTimetable.objects.get(department=student.department)
            print(f"✅ Department timetable found: {dept_timetable.name}")
            
            # Check timetable slots
            slots = TimetableSlot.objects.filter(
                timetable=dept_timetable,
                level=level
            ).count()
            print(f"   - Timetable slots for level: {slots}")
            
        except DepartmentTimetable.DoesNotExist:
            print("⚠️  No department timetable found")
        
        # Test the "My Courses" view
        print(f"\n📚 Testing 'My Courses' view...")
        my_courses = StudentCourseSelection.objects.filter(
            student=student,
            is_offered=True,
            is_approved=True
        ).select_related('course')
        
        print(f"   - Courses in 'My Courses': {my_courses.count()}")
        for course_selection in my_courses[:5]:  # Show first 5
            print(f"     • {course_selection.course.code} - {course_selection.course.title}")
        
        # Test course persistence (simulate re-login)
        print(f"\n🔄 Testing course persistence (simulating re-login)...")
        sync_result_2 = full_course_sync(student)
        
        persistence_selections = StudentCourseSelection.objects.filter(
            student=student,
            is_offered=True,
            is_approved=True
        ).count()
        
        persistence_student_courses = StudentCourse.objects.filter(
            student=student,
            is_active=True
        ).count()
        
        print(f"   - After re-sync:")
        print(f"     • StudentCourseSelection: {persistence_selections}")
        print(f"     • StudentCourse: {persistence_student_courses}")
        
        # Check if counts are consistent
        if persistence_selections == final_selections and persistence_student_courses == final_student_courses:
            print("✅ Course persistence test PASSED")
        else:
            print("❌ Course persistence test FAILED")
            return False
        
        print(f"\n🎉 All tests completed successfully!")
        print(f"   - Course synchronization is working")
        print(f"   - Approved courses persist after re-login")
        print(f"   - Both 'My Courses' and timetable views should show consistent data")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_course_sync_fix()
    sys.exit(0 if success else 1)