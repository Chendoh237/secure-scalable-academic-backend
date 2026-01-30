"""
Manual test script to check course endpoints
Run this to see what data the endpoints are returning
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from students.models import Student, StudentCourseSelection
from courses.models import Course
from students.course_selection_service import get_available_courses_for_registration, get_my_courses
from django.contrib.auth import get_user_model

User = get_user_model()

print("=" * 80)
print("COURSE ENDPOINTS TEST")
print("=" * 80)

# Get first student
students = Student.objects.all()
print(f"\n1. Total Students: {students.count()}")

if not students.exists():
    print("   ❌ No students found!")
    exit()

student = students.first()
print(f"   ✓ Testing with: {student.matric_number} - {student.full_name}")
print(f"   ✓ Department: {student.department.name if student.department else 'None'}")
print(f"   ✓ Has level selection: {hasattr(student, 'level_selection') and student.level_selection is not None}")

# Check courses in database
print(f"\n2. Total Courses in Database: {Course.objects.count()}")

if student.department:
    dept_courses = Course.objects.filter(department=student.department)
    print(f"   ✓ Courses in {student.department.name}: {dept_courses.count()}")
    
    if dept_courses.exists():
        print("\n   Sample courses:")
        for course in dept_courses[:5]:
            print(f"      - {course.code}: {course.title} (Level: {course.level}, Credits: {course.credit_units})")
    else:
        print("   ❌ No courses in student's department!")
else:
    print("   ❌ Student has no department!")

# Test get_available_courses_for_registration
print(f"\n3. Testing get_available_courses_for_registration()...")
try:
    available = get_available_courses_for_registration(student)
    print(f"   ✓ Available courses: {available.count()}")
    
    if available.exists():
        print("\n   Sample available courses:")
        for course in available[:5]:
            print(f"      - {course.code}: {course.title}")
    else:
        print("   ⚠️  No available courses (might all be registered)")
        
        # Check if student has any registrations
        registrations = StudentCourseSelection.objects.filter(student=student, is_offered=True)
        print(f"   ℹ️  Student has {registrations.count()} course selections")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test get_my_courses
print(f"\n4. Testing get_my_courses()...")
try:
    my_courses = get_my_courses(student)
    print(f"   ✓ My courses: {my_courses.count()}")
    
    if my_courses.exists():
        print("\n   My courses list:")
        for selection in my_courses:
            print(f"      - {selection.course.code}: {selection.course.title}")
            print(f"        is_offered: {selection.is_offered}, is_approved: {selection.is_approved}")
    else:
        print("   ℹ️  No approved courses yet")
        
        # Check pending
        pending = StudentCourseSelection.objects.filter(
            student=student,
            is_offered=True,
            is_approved=False
        )
        print(f"   ℹ️  Pending registrations: {pending.count()}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Check all StudentCourseSelection records for this student
print(f"\n5. All StudentCourseSelection records for this student:")
all_selections = StudentCourseSelection.objects.filter(student=student)
print(f"   Total: {all_selections.count()}")

if all_selections.exists():
    for selection in all_selections:
        print(f"      - {selection.course.code}: offered={selection.is_offered}, approved={selection.is_approved}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
