#!/usr/bin/env python
import os
import django
import requests

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Create admin user if doesn't exist
admin_user, created = User.objects.get_or_create(
    username='admin',
    defaults={
        'email': 'admin@test.com',
        'first_name': 'Admin',
        'last_name': 'User',
        'is_staff': True,
        'is_superuser': True
    }
)

if created:
    admin_user.set_password('admin123')
    admin_user.save()
    print("Admin user created")
else:
    print("Admin user already exists")

# Test login
login_data = {
    'username': 'admin',
    'password': 'admin123'
}

try:
    response = requests.post('http://localhost:8000/api/token/', json=login_data)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data['access']
        print(f"Login successful, token: {access_token[:50]}...")
        
        # Test admin endpoints
        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Test departments endpoint
        dept_response = requests.get('http://localhost:8000/api/institutions/admin/departments/', headers=headers)
        print(f"Departments endpoint: {dept_response.status_code}")
        if dept_response.status_code == 200:
            print(f"Departments data: {dept_response.json()}")
        else:
            print(f"Departments error: {dept_response.text}")
            
        # Test courses endpoint
        courses_response = requests.get('http://localhost:8000/api/institutions/admin/courses/', headers=headers)
        print(f"Courses endpoint: {courses_response.status_code}")
        if courses_response.status_code == 200:
            print(f"Courses data: {courses_response.json()}")
        else:
            print(f"Courses error: {courses_response.text}")
            
    else:
        print(f"Login failed: {response.status_code} - {response.text}")
        
except Exception as e:
    print(f"Error: {e}")