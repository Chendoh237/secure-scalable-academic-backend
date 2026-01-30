import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from students.models import Student
from courses.models import Course
from django.contrib.auth import get_user_model

User = get_user_model()

print("=" * 60)
print("Database Check")
print("=" * 60)

# Check users
users = User.objects.all()
print(f"\nTotal Users: {users.count()}")
for user in users[:5]:
    print(f"  - {user.username} ({user.email})")

# Check students
students = Student.objects.all()
print(f"\nTotal Students: {students.count()}")
for student in students[:5]:
    print(f"  - {student.matric_number}: {student.full_name}")
    print(f"    Department: {student.department.name if student.department else 'None'}")
    print(f"    User: {student.user.username if student.user else 'None'}")

# Check courses
courses = Course.objects.all()
print(f"\nTotal Courses: {courses.count()}")
for course in courses[:10]:
    print(f"  - {course.code}: {course.title}")
    print(f"    Department: {course.department.name}")
    print(f"    Level: {course.level}")

# Check if any student has courses
if students.exists():
    student = students.first()
    print(f"\nChecking first student: {student.matric_number}")
    print(f"  Department: {student.department.name if student.department else 'None'}")
    
    if student.department:
        dept_courses = Course.objects.filter(department=student.department)
        print(f"  Courses in department: {dept_courses.count()}")
        for course in dept_courses[:5]:
            print(f"    - {course.code}: {course.title}")

print("\n" + "=" * 60)
