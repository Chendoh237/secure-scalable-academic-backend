#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from students.models import StudentCourseSelection
from students.approval_service import get_all_pending_registrations

def main():
    print("Checking pending registrations...")
    
    # Check for existing pending registrations
    pending = get_all_pending_registrations()
    print(f'Existing pending registrations: {pending.count()}')
    
    for selection in pending:
        print(f'- {selection.student.matric_number}: {selection.course.code} (Level: {selection.level.name})')
    
    # Also check all course selections
    all_selections = StudentCourseSelection.objects.all()
    print(f'\nAll course selections: {all_selections.count()}')
    
    approved_count = all_selections.filter(is_approved=True).count()
    pending_count = all_selections.filter(is_approved=False).count()
    
    print(f'- Approved: {approved_count}')
    print(f'- Pending: {pending_count}')

if __name__ == '__main__':
    main()