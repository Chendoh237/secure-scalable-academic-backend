"""
Simple manual test for Course Registration & Approval feature
Creates its own test data
Run with: python test_course_registration_simple.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from students.models import Student, StudentCourseSelection
from courses.models import Course, Level
from institutions.models import Institution, Faculty, Department
from students.course_selection_service import (
    can_register_for_course,
    get_my_courses,
    get_pending_registrations
)
from students.timetable_selection_service import mark_timetable_course_offering
from students.direct_registration_service import register_course_directly
from students.approval_service import approve_registration

User = get_user_model()

def test_basic_workflow():
    """Test basic course registration workflow"""
    
    print("\n" + "="*80)
    print("TESTING COURSE REGISTRATION & APPROVAL - BASIC WORKFLOW")
    print("="*80 + "\n")
    
    try:
        # Get existing data
        institution = Institution.objects.first()
        department = Department.objects.first()
        student = Student.objects.first()
        admin_user = User.objects.filter(is_superuser=True).first()
        
        if not all([institution, department, student, admin_user]):
            print("❌ ERROR: Missing required data (institution, department, student, or admin)")
            return False
        
        print(f"✓ Using student: {student.full_name}")
        print(f"✓ Using department: {department.name}")
        
        # Get or create levels
        level, _ = Level.objects.get_or_create(
            department=department,
            code="200",
            defaults={'name': "200 Level"}
        )
        
        # Get or create courses in the student's department
        course1, _ = Course.objects.get_or_create(
            code="TEST201",
            department=student.department,
            defaults={
                'title': "Test Course 1",
                'level': level,
                'credit_units': 3
            }
        )
        
        course2, _ = Course.objects.get_or_create(
            code="TEST202",
            department=student.department,
            defaults={
                'title': "Test Course 2",
                'level': level,
                'credit_units': 3
            }
        )
        
        print(f"✓ Using courses: {course1.code}, {course2.code}\n")
        
        # Clean up existing selections
        StudentCourseSelection.objects.filter(
            student=student,
            course__in=[course1, course2]
        ).delete()
        
        # TEST 1: Timetable selection (auto-approved)
        print("TEST 1: Timetable Course Selection (Auto-Approved)")
        print("-" * 60)
        
        selection1 = mark_timetable_course_offering(student, course1, level)
        
        assert selection1.is_offered == True
        assert selection1.is_approved == True
        print(f"✓ Marked {course1.code} as offering")
        print(f"✓ Auto-approved: is_offered={selection1.is_offered}, is_approved={selection1.is_approved}")
        
        my_courses = get_my_courses(student)
        assert my_courses.filter(course=course1).exists()
        print(f"✓ Course appears in My Courses\n")
        
        # TEST 2: Direct registration (pending)
        print("TEST 2: Direct Registration (Pending Approval)")
        print("-" * 60)
        
        can_register, reason = can_register_for_course(student, course2)
        assert can_register == True, f"Should be able to register: {reason}"
        print(f"✓ Can register for {course2.code}")
        
        selection2 = register_course_directly(student, course2, level)
        assert selection2.is_offered == True
        assert selection2.is_approved == False
        print(f"✓ Registered for {course2.code}")
        print(f"✓ Pending approval: is_offered={selection2.is_offered}, is_approved={selection2.is_approved}")
        
        pending = get_pending_registrations(student)
        assert pending.filter(course=course2).exists()
        print(f"✓ Appears in pending registrations\n")
        
        # TEST 3: Duplicate prevention
        print("TEST 3: Duplicate Prevention")
        print("-" * 60)
        
        can_register, reason = can_register_for_course(student, course1)
        assert can_register == False
        print(f"✓ Cannot register for approved course: {reason}")
        
        can_register, reason = can_register_for_course(student, course2)
        assert can_register == False
        print(f"✓ Cannot register for pending course: {reason}\n")
        
        # TEST 4: Admin approval
        print("TEST 4: Admin Approval")
        print("-" * 60)
        
        result = approve_registration(selection2.id, admin_user)
        print(f"✓ Admin approved: {result['message']}")
        
        selection2.refresh_from_db()
        assert selection2.is_approved == True
        print(f"✓ Now approved: is_approved={selection2.is_approved}")
        
        my_courses = get_my_courses(student)
        assert my_courses.filter(course=course2).exists()
        print(f"✓ Now appears in My Courses")
        
        pending = get_pending_registrations(student)
        assert not pending.filter(course=course2).exists()
        print(f"✓ No longer in pending registrations\n")
        
        # TEST 5: Attendance integration
        print("TEST 5: Attendance Integration")
        print("-" * 60)
        
        my_courses = get_my_courses(student)
        print(f"✓ My Courses (attendance query): {my_courses.count()} courses")
        
        for sel in my_courses.filter(course__in=[course1, course2]):
            assert sel.is_offered and sel.is_approved
            print(f"  - {sel.course.code}: offered={sel.is_offered}, approved={sel.is_approved}")
        
        print()
        
        # Summary
        print("="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nVerified:")
        print("  ✓ Timetable courses are auto-approved")
        print("  ✓ Direct registrations require approval")
        print("  ✓ Duplicate prevention works")
        print("  ✓ Admin approval workflow works")
        print("  ✓ Attendance integration works")
        print()
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_basic_workflow()
    exit(0 if success else 1)
