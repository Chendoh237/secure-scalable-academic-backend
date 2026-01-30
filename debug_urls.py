#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.urls import reverse, resolve
from django.conf import settings

def debug_urls():
    print("Django URL Debug")
    print("=" * 50)
    
    # Test URL patterns
    url_names_to_test = [
        'admin_attendance_records',
        'admin_export_attendance_records',
        'admin_students',
        'admin_dashboard_stats'
    ]
    
    for url_name in url_names_to_test:
        try:
            url = reverse(url_name)
            print(f"✓ {url_name}: {url}")
            
            # Test resolve
            try:
                resolver = resolve(url)
                print(f"  → Function: {resolver.func.__name__}")
                print(f"  → Module: {resolver.func.__module__}")
            except Exception as resolve_error:
                print(f"  ✗ Resolve error: {resolve_error}")
                
        except Exception as reverse_error:
            print(f"✗ {url_name}: {reverse_error}")
    
    print("\n" + "=" * 50)
    print("Testing specific URL path...")
    
    # Test the specific path
    test_path = '/api/admin/attendance/export/'
    try:
        resolver = resolve(test_path)
        print(f"✓ Path '{test_path}' resolves to:")
        print(f"  → Function: {resolver.func.__name__}")
        print(f"  → Module: {resolver.func.__module__}")
        print(f"  → URL name: {resolver.url_name}")
    except Exception as e:
        print(f"✗ Path '{test_path}' failed to resolve: {e}")
    
    # Test variations
    test_paths = [
        '/api/admin/attendance/',
        '/api/admin/attendance/export',
        '/api/admin/attendance/export/',
        '/admin/attendance/export/',
    ]
    
    print(f"\nTesting path variations...")
    for path in test_paths:
        try:
            resolver = resolve(path)
            print(f"✓ {path} → {resolver.func.__name__}")
        except Exception as e:
            print(f"✗ {path} → {e}")

if __name__ == '__main__':
    debug_urls()