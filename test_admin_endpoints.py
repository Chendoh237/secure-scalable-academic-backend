#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from institutions.views import admin_departments, admin_courses_enhanced
from institutions.models import Department, Faculty
from institutions.program_models import AcademicProgram

def test_admin_endpoints():
    factory = RequestFactory()
    
    print("Testing admin_departments endpoint...")
    try:
        request = factory.get('/api/institutions/admin/departments/')
        request.user = AnonymousUser()  # For testing, we'll use anonymous user
        
        response = admin_departments(request)
        print(f"Status Code: {response.status_code}")
        print(f"Response Data: {response.data}")
        
        if response.status_code == 200:
            print("✅ admin_departments endpoint working")
        else:
            print("❌ admin_departments endpoint failed")
            
    except Exception as e:
        print(f"❌ Error testing admin_departments: {e}")
    
    print("\nTesting admin_courses_enhanced endpoint...")
    try:
        request = factory.get('/api/institutions/admin/courses/')
        request.user = AnonymousUser()
        
        response = admin_courses_enhanced(request)
        print(f"Status Code: {response.status_code}")
        print(f"Response Data: {response.data}")
        
        if response.status_code == 200:
            print("✅ admin_courses_enhanced endpoint working")
        else:
            print("❌ admin_courses_enhanced endpoint failed")
            
    except Exception as e:
        print(f"❌ Error testing admin_courses_enhanced: {e}")
    
    print("\nChecking database data...")
    try:
        dept_count = Department.objects.count()
        faculty_count = Faculty.objects.count()
        program_count = AcademicProgram.objects.count()
        
        print(f"Departments in DB: {dept_count}")
        print(f"Faculties in DB: {faculty_count}")
        print(f"Programs in DB: {program_count}")
        
        if dept_count > 0:
            print("Sample departments:")
            for dept in Department.objects.all()[:3]:
                print(f"  - {dept.name} (Faculty: {dept.faculty.name})")
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")

if __name__ == "__main__":
    test_admin_endpoints()