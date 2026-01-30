#!/usr/bin/env python
import os
import sys
import django

# Add the project directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Create admin user
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@example.com',
        password='admin123',
        first_name='Admin',
        last_name='User'
    )
    print("Admin user created successfully!")
    print("Email: admin@example.com")
    print("Password: admin123")
else:
    # Update existing admin user email
    admin_user = User.objects.get(username='admin')
    admin_user.email = 'admin@example.com'
    admin_user.save()
    print("Admin user already exists!")
    print("Email: admin@example.com")
    print("Password: admin123")