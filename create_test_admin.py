#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Update the existing test_admin user to have admin role
try:
    admin_user = User.objects.get(username='test_admin')
    admin_user.role = 'admin'
    admin_user.is_staff = True
    admin_user.save()
    print('✅ Test admin user updated to admin role')
except User.DoesNotExist:
    # Create new admin user
    admin_user = User.objects.create_user(
        username='test_admin',
        email='admin@test.com',
        password='testpass123',
        role='admin',
        is_active=True,
        is_staff=True
    )
    print('✅ Test admin user created with admin role')