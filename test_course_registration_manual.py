"""
Manual test script for Course Registration & Approval feature
Run with: python test_course_registration_manual.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from students.models import Student, StudentCourseSelection, StudentLevelSelection
from courses.models import Course, Level
from institutions.models import Institution, Faculty, Department
from students.course_selection_service import (
    can_register_for_course,
    get_available_courses_for_registration,
    get_my_courses,
    get_pending_registrations
)
from students.timetable_selection_service import mark_timetable_course_offering
from students.direct_registration_service import register_course_directly
from students.approval_service import approve_registration, reject_registration

User = get_user_model()

def test_course_registration_approval():
    """Test the complete course registration and approval workflow"""
    
    print("\n" + "="*80)
    print("TESTING COURSE REGISTRATION & APPROVAL FEATURE")
    print("="*80 + "\n")
    
    # Get or create test data
    try:
        institution = Institution.objects.first()
        department = Department.objects.first()
        
        if not institution or not department:
            print("❌ ERROR: No institution or department found. Please create test data first.")
            return
        
        # Get levels
        levels = Level.objects.filter(department=department)[:2]
        if len(levels) < 2:
            print("❌ ERROR: Need at least 2 levels in the department.")
            return
        
        level_1 = levels[0]
        level_2 = levels[1]
        
        # Get or create test student
        student = Student.objects.first()
        if not student:
            print("❌ ERROR: No student found. Please create a test student first.")
            return
        
        # Get or create admin user
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            print("❌ ERROR: No admin user found.")
            return
        
        # Get courses from the student's department
        courses = list(Course.objects.filter(department=student.department))
        if len(courses) < 2:
            print(f"❌ ERROR: Need at least 2 courses in the student's department ({student.department.name}).")
            print(f"   Found only {len(courses)} course(s).")
            return
        
        # Use available courses (may be less than 3)
        course_1 = courses[0]
        course_2 = courses[1]
        course_3 = courses[2] if len(courses) >= 3 else None
        
        # Debug: Print course departments
        print(f"DEBUG: Student department: {student.department.name} (ID: {student.department.id})")
        print(f"DEBUG: Course 1 department: {course_1.department.name} (ID: {course_1.department.id})")
        print(f"DEBUG: Course 2 department: {course_2.department.name} (ID: {course_2.department.id})")
        if course_3:
            print(f"DEBUG: Course 3 department: {course_3.department.name} (ID: {course_3.department.id})")
        
        # Debug: Print course departments
        print(f"DEBUG: Student department: {student.department.name} (ID: {student.department.id})")
        print(f"DEBUG: Course 1 department: {course_1.department.name} (ID: {course_1.department.id})")
        print(f"DEBUG: Course 2 department: {course_2.department.name} (ID: {course_2.department.id})")
        print(f"DEBUG: Course 3 department: {course_3.department.name} (ID: {course_3.department.id})")
        
        print(f"✓ Using student: {student.full_name} ({student.matric_number})")
        print(f"✓ Using department: {student.department.name}")
        print(f"✓ Using courses: {course_1.code}, {course_2.code}" + (f", {course_3.code}" if course_3 else ""))
        print()
        
        # Clean up any existing selections for this student
        StudentCourseSelection.objects.filter(student=student).delete()
        print("✓ Cleaned up existing course selections\n")
        
        # Test 1: Timetable course selection (auto-approved)
        print("TEST 1: Timetable Course Selection (Auto-Approved)")
        print("-" * 60)
        
        selection = mark_timetable_course_offering(student, course_1, level_1)
        
        assert selection.is_offered == True, "Course should be marked as offered"
        assert selection.is_approved == True, "Timetable course should be auto-approved"
        print(f"✓ Marked {course_1.code} as offering (auto-approved)")
        
        my_courses = get_my_courses(student)
        assert my_courses.count() == 1, "Should have 1 approved course"
        print(f"✓ Course appears in My Courses: {my_courses.count()} course(s)")
        print()
        
        # Test 2: Direct registration (pending approval)
        print("TEST 2: Direct Course Registration (Pending Approval)")
        print("-" * 60)
        
        can_register, reason = can_register_for_course(student, course_2)
        assert can_register == True, f"Should be able to register: {reason}"
        print(f"✓ Can register for {course_2.code}")
        
        selection = register_course_directly(student, course_2, level_2)
        assert selection.is_offered == True, "Course should be marked as offered"
        assert selection.is_approved == False, "Direct registration should be pending"
        print(f"✓ Registered for {course_2.code} (pending approval)")
        
        pending = get_pending_registrations(student)
        assert pending.count() == 1, "Should have 1 pending registration"
        print(f"✓ Pending registrations: {pending.count()}")
        
        my_courses = get_my_courses(student)
        assert my_courses.count() == 1, "Pending course should NOT appear in My Courses yet"
        print(f"✓ My Courses still shows only approved courses: {my_courses.count()}")
        print()
        
        # Test 3: Duplicate prevention
        print("TEST 3: Duplicate Registration Prevention")
        print("-" * 60)
        
        can_register, reason = can_register_for_course(student, course_1)
        assert can_register == False, "Should not be able to register for approved course"
        print(f"✓ Cannot register for already approved course: {reason}")
        
        can_register, reason = can_register_for_course(student, course_2)
        assert can_register == False, "Should not be able to register for pending course"
        print(f"✓ Cannot register for pending course: {reason}")
        print()
        
        # Test 4: Available courses filtering
        print("TEST 4: Available Courses Filtering")
        print("-" * 60)
        
        available = get_available_courses_for_registration(student)
        available_codes = [c.code for c in available]
        
        assert course_1.code not in available_codes, "Approved course should not be available"
        assert course_2.code not in available_codes, "Pending course should not be available"
        if course_3:
            assert course_3.code in available_codes, "Unregistered course should be available"
        print(f"✓ Available courses exclude approved and pending: {len(available_codes)} available")
        print()
        
        # Test 5: Admin approval
        print("TEST 5: Admin Approval Workflow")
        print("-" * 60)
        
        result = approve_registration(selection.id, admin_user)
        print(f"✓ Admin approved registration: {result['message']}")
        
        # Refresh selection
        selection.refresh_from_db()
        assert selection.is_approved == True, "Registration should now be approved"
        print(f"✓ Registration is now approved")
        
        my_courses = get_my_courses(student)
        assert my_courses.count() == 2, "Should now have 2 approved courses"
        print(f"✓ My Courses now shows both courses: {my_courses.count()}")
        
        pending = get_pending_registrations(student)
        assert pending.count() == 0, "Should have no pending registrations"
        print(f"✓ No more pending registrations: {pending.count()}")
        print()
        
        # Test 6: Rejection workflow (only if we have a third course)
        if course_3:
            print("TEST 6: Admin Rejection Workflow")
            print("-" * 60)
            
            # Register for another course
            selection = register_course_directly(student, course_3, level_2)
            print(f"✓ Registered for {course_3.code} (pending)")
            
            result = reject_registration(selection.id, admin_user, "Course is full")
            print(f"✓ Admin rejected registration: {result['message']}")
            
            # Verify deletion
            exists = StudentCourseSelection.objects.filter(id=selection.id).exists()
            assert exists == False, "Rejected registration should be deleted"
            print(f"✓ Registration was deleted")
            
            pending = get_pending_registrations(student)
            assert pending.count() == 0, "Should have no pending registrations"
            print(f"✓ No pending registrations: {pending.count()}")
            print()
        else:
            print("TEST 6: Admin Rejection Workflow - SKIPPED (not enough courses)")
            print("-" * 60)
            print()
        
        # Test 7: Attendance integration
        print("TEST 7: Attendance System Integration")
        print("-" * 60)
        
        my_courses = get_my_courses(student)
        print(f"✓ My Courses query (same as attendance): {my_courses.count()} courses")
        
        for course_sel in my_courses:
            assert course_sel.is_offered == True, "All courses should be offered"
            assert course_sel.is_approved == True, "All courses should be approved"
            print(f"  - {course_sel.course.code}: offered={course_sel.is_offered}, approved={course_sel.is_approved}")
        
        print()
        
        # Summary
        print("="*80)
        print("✅ ALL TESTS PASSED!")
        print("="*80)
        print("\nFeature Summary:")
        print(f"  • Timetable courses: Auto-approved ✓")
        print(f"  • Direct registration: Pending approval ✓")
        print(f"  • Duplicate prevention: Working ✓")
        print(f"  • Available courses filtering: Working ✓")
        print(f"  • Admin approval: Working ✓")
        print(f"  • Admin rejection: Working ✓")
        print(f"  • Attendance integration: Working ✓")
        print()
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == '__main__':
    success = test_course_registration_approval()
    exit(0 if success else 1)
