#!/usr/bin/env python
"""
Test script to debug user authentication and roles.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def debug_user_authentication():
    """Debug user authentication and roles."""
    
    print("🔧 Debugging User Authentication and Roles")
    print("=" * 50)
    
    # List all users and their roles
    users = User.objects.all()
    
    print(f"📊 Total users in database: {users.count()}")
    print()
    
    for user in users:
        print(f"👤 User: {user.username}")
        print(f"   - Full name: {user.get_full_name() or 'Not set'}")
        print(f"   - Email: {user.email or 'Not set'}")
        print(f"   - Role: {getattr(user, 'role', 'No role attribute')}")
        print(f"   - is_staff: {user.is_staff}")
        print(f"   - is_superuser: {user.is_superuser}")
        print(f"   - is_active: {user.is_active}")
        
        # Test is_admin_user method
        try:
            is_admin = user.is_admin_user()
            print(f"   - is_admin_user(): {is_admin}")
        except Exception as e:
            print(f"   - is_admin_user() ERROR: {e}")
        
        print()
    
    # Check for admin users
    admin_users = User.objects.filter(role__in=['admin', 'super_admin', 'institution_admin', 'department_admin'])
    staff_users = User.objects.filter(is_staff=True)
    superusers = User.objects.filter(is_superuser=True)
    
    print(f"📈 User Statistics:")
    print(f"   - Admin role users: {admin_users.count()}")
    print(f"   - Staff users: {staff_users.count()}")
    print(f"   - Superusers: {superusers.count()}")
    
    # Recommend creating an admin user if none exist
    if admin_users.count() == 0 and staff_users.count() == 0 and superusers.count() == 0:
        print()
        print("⚠️  WARNING: No admin users found!")
        print("   To fix the 403 error, you need at least one admin user.")
        print("   Run: python manage.py createsuperuser")
        print("   Or update an existing user's role to 'admin'")
    
    return True

if __name__ == "__main__":
    success = debug_user_authentication()
    sys.exit(0 if success else 1)