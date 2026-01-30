#!/usr/bin/env python3
"""
Create a test user for authentication
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

def create_test_user():
    User = get_user_model()
    
    # Check if test user already exists
    test_email = "admin@test.com"
    test_password = "admin123"
    
    try:
        user = User.objects.get(email=test_email)
        print(f"User {test_email} already exists!")
        # Update password just in case
        user.set_password(test_password)
        user.save()
        print(f"Password updated for {test_email}")
    except User.DoesNotExist:
        # Create new user
        user = User.objects.create_user(
            email=test_email,
            username="admin",
            password=test_password,
            is_staff=True,
            is_superuser=True
        )
        print(f"Created test user: {test_email}")
    
    # List all users
    print("\nAll users in system:")
    for u in User.objects.all():
        print(f"- {u.email} (username: {u.username}, staff: {u.is_staff})")
    
    print(f"\nTest credentials:")
    print(f"Email: {test_email}")
    print(f"Password: {test_password}")

if __name__ == "__main__":
    create_test_user()