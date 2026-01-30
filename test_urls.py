#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.urls import reverse

try:
    print('admin_departments:', reverse('admin_departments'))
except Exception as e:
    print('admin_departments URL not found:', e)

try:
    print('admin_courses_enhanced:', reverse('admin_courses_enhanced'))
except Exception as e:
    print('admin_courses_enhanced URL not found:', e)

# Test if the views exist
try:
    from institutions.views import admin_departments, admin_courses_enhanced
    print('Views imported successfully')
except Exception as e:
    print('Views import failed:', e)