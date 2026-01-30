#!/usr/bin/env python3
"""
Reset all student passwords to 'password123'
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from students.models import Student

User = get_user_model()

def reset_student_passwords():
    print("🔐 Resetting Student Passwords")
    print("=" * 50)
    
    # Get all non-staff users (students)
    students = User.objects.filter(is_staff=False)
    
    print(f"Found {students.count()} student accounts")
    print("\nUpdating passwords...")
    
    updated_count = 0
    for user in students:
        user.set_password('password123')
        user.save()
        print(f"✅ Updated: {user.username} ({user.email})")
        updated_count += 1
    
    print(f"\n🎉 Successfully updated {updated_count} student passwords!")
    print("All student accounts now use password: password123")
    
    # Test a few logins
    print("\n🧪 Testing sample logins...")
    sample_users = students[:3]
    for user in sample_users:
        if user.check_password('password123'):
            print(f"✅ {user.username}: Password verified")
        else:
            print(f"❌ {user.username}: Password verification failed")

if __name__ == "__main__":
    reset_student_passwords()