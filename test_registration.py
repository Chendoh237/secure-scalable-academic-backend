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

from rest_framework.test import APIClient
from institutions.program_models import AcademicProgram
from institutions.models import Faculty, Department

def test_registration():
    client = APIClient()
    
    # Get first available program, faculty, department
    program = AcademicProgram.objects.first()
    faculty = Faculty.objects.filter(program=program).first()
    department = Department.objects.filter(faculty=faculty).first()
    
    if not all([program, faculty, department]):
        print("Missing academic data")
        return
    
    print(f"Using Program: {program.name}, Faculty: {faculty.name}, Department: {department.name}")
    
    data = {
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'testuser@example.com',
        'matric_number': 'TEST123456',
        'program': program.id,
        'faculty': faculty.id,
        'department': department.id,
        'password': 'testpass123',
        'confirm_password': 'testpass123',
    }
    
    try:
        # Use force_authenticate to bypass ALLOWED_HOSTS
        response = client.post('/api/register/', data, format='json', HTTP_HOST='localhost')
        print(f"Status Code: {response.status_code}")
        
        if hasattr(response, 'data'):
            print(f"Response: {response.data}")
        else:
            print(f"Response Content: {response.content.decode()}")
        
        if response.status_code == 201:
            print("✅ Registration successful!")
        else:
            print("❌ Registration failed!")
    except Exception as e:
        print(f"Error during registration: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_registration()