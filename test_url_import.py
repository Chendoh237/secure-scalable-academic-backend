#!/usr/bin/env python3
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

try:
    from institutions.urls import urlpatterns
    print("Successfully imported institutions URLs")
    print(f"Number of URL patterns: {len(urlpatterns)}")
    
    for i, pattern in enumerate(urlpatterns):
        print(f"{i+1}. {pattern.pattern} -> {pattern.name}")
        
except Exception as e:
    print(f"Error importing institutions URLs: {e}")
    import traceback
    traceback.print_exc()

try:
    from django.urls import reverse
    print("\nTesting URL reversal:")
    
    # Test basic endpoints
    print(f"get_programs: {reverse('get_programs')}")
    print(f"get_departments: {reverse('get_departments')}")
    
    # Test admin endpoints
    try:
        print(f"admin_departments: {reverse('admin_departments')}")
        print(f"admin_courses_enhanced: {reverse('admin_courses_enhanced')}")
    except Exception as e:
        print(f"Error reversing admin URLs: {e}")
        
except Exception as e:
    print(f"Error testing URL reversal: {e}")