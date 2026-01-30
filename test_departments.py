#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from institutions.models import Department
from courses.models import Lecturer

print("Departments:")
for dept in Department.objects.all():
    print(f"  {dept.id}: {dept.name}")

print("\nLecturers:")
for lecturer in Lecturer.objects.all():
    print(f"  {lecturer.id}: {lecturer.user.first_name} {lecturer.user.last_name} ({lecturer.employee_id})")