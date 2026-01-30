#!/usr/bin/env python
"""
Fix admin user roles - set proper admin role for staff and superusers.
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

def fix_admin_user_roles():
    """Fix admin user roles for staff and superusers."""
    
    print("🔧 Fixing Admin User Roles")
    print("=" * 40)
    
    # Find users who should be admins but have student role
    users_to_fix = User.objects.filter(
        role='student'
    ).filter(
        models.Q(is_staff=True) | models.Q(is_superuser=True)
    )
    
    print(f"📊 Found {users_to_fix.count()} users to fix:")
    
    fixed_count = 0
    
    for user in users_to_fix:
        old_role = user.role
        
        # Set appropriate admin role
        if user.is_superuser:
            user.role = 'super_admin'
        elif user.is_staff:
            user.role = 'admin'
        
        user.save()
        fixed_count += 1
        
        print(f"   ✅ {user.username}: {old_role} → {user.role}")
    
    print(f"\n🎉 Fixed {fixed_count} user roles")
    
    # Verify the fix
    print(f"\n📈 Updated Statistics:")
    admin_users = User.objects.filter(role__in=['admin', 'super_admin', 'institution_admin', 'department_admin'])
    staff_users = User.objects.filter(is_staff=True)
    superusers = User.objects.filter(is_superuser=True)
    
    print(f"   - Admin role users: {admin_users.count()}")
    print(f"   - Staff users: {staff_users.count()}")
    print(f"   - Superusers: {superusers.count()}")
    
    # Show admin users
    print(f"\n👑 Admin Users:")
    for user in admin_users:
        print(f"   - {user.username} ({user.role}) - Staff: {user.is_staff}, Super: {user.is_superuser}")
    
    return True

if __name__ == "__main__":
    from django.db import models
    success = fix_admin_user_roles()
    sys.exit(0 if success else 1)