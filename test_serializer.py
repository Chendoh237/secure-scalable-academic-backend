#!/usr/bin/env python
import os
import sys
import django
from django.conf import settings

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from students.serializers import StudentRegistrationSerializer
from institutions.program_models import AcademicProgram
from institutions.models import Faculty, Department

def test_serializer():
    # Get first available program, faculty, department
    program = AcademicProgram.objects.first()
    faculty = Faculty.objects.filter(program=program).first()
    department = Department.objects.filter(faculty=faculty).first()
    
    if not all([program, faculty, department]):
        print("Missing academic data")
        return
    
    print(f"Using Program: {program.name} (ID: {program.id})")
    print(f"Faculty: {faculty.name} (ID: {faculty.id})")
    print(f"Department: {department.name} (ID: {department.id})")
    
    data = {
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'testuser2@example.com',
        'matric_number': 'TEST123457',
        'program': program.id,
        'faculty': faculty.id,
        'department': department.id,
        'password': 'testpass123',
        'confirm_password': 'testpass123',
    }
    
    serializer = StudentRegistrationSerializer(data=data)
    
    if serializer.is_valid():
        print("Serializer validation passed!")
        try:
            student = serializer.save()
            print(f"Student created successfully: {student.full_name}")
        except Exception as e:
            print(f"Error creating student: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Serializer validation failed!")
        print("Errors:", serializer.errors)

if __name__ == '__main__':
    test_serializer()