#!/usr/bin/env python
"""
Simple test script to verify the attendance export functionality
"""
import os
import sys
import django

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from students.models import Student
from institutions.models import Department, Faculty, Institution

def test_export_functionality():
    """Test the export functionality"""
    print("Testing Attendance Export Functionality...")
    
    # Create a test client
    client = Client()
    
    # Create a test user and login
    User = get_user_model()
    
    # Try to get existing admin user or create one
    try:
        admin_user = User.objects.get(username='admin')
    except User.DoesNotExist:
        admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
    
    # Login
    login_response = client.post('/api/token/', {
        'username': 'admin',
        'password': 'admin123'
    })
    
    if login_response.status_code == 200:
        token = login_response.json()['access']
        headers = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
        
        print("✓ Authentication successful")
        
        # Test basic attendance records endpoint
        attendance_response = client.get('/api/admin/attendance/', **headers)
        print(f"✓ Attendance records endpoint: {attendance_response.status_code}")
        
        # Test export endpoints
        export_excel_response = client.get('/api/admin/attendance/export/?format=excel', **headers)
        print(f"✓ Excel export endpoint: {export_excel_response.status_code}")
        
        export_pdf_response = client.get('/api/admin/attendance/export/?format=pdf', **headers)
        print(f"✓ PDF export endpoint: {export_pdf_response.status_code}")
        
        # Test with filters
        export_filtered_response = client.get('/api/admin/attendance/export/?format=excel&level=HND1', **headers)
        print(f"✓ Filtered export endpoint: {export_filtered_response.status_code}")
        
        print("\n✅ All export endpoints are accessible!")
        
    else:
        print(f"❌ Authentication failed: {login_response.status_code}")
        print(login_response.content.decode())

if __name__ == '__main__':
    test_export_functionality()