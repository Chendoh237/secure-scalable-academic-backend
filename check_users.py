#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print("All users:")
users = User.objects.all()
for user in users:
    print(f'  User: {user.username}, Role: {user.role}, Active: {user.is_active}')

print("\nAdmin users:")
admin_users = User.objects.filter(role__in=['admin', 'super_admin', 'institution_admin', 'department_admin'], is_active=True)
for user in admin_users:
    print(f'  Admin: {user.username}, Role: {user.role}')