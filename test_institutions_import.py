#!/usr/bin/env python3
import os
import sys
import django

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

print("Testing institutions app import...")

try:
    # Test importing the institutions app
    import institutions
    print("✅ institutions app imported successfully")
    
    # Test importing the views
    from institutions import views
    print("✅ institutions.views imported successfully")
    
    # Test importing the URLs
    from institutions import urls
    print("✅ institutions.urls imported successfully")
    
    # Check the URL patterns
    print(f"✅ Found {len(urls.urlpatterns)} URL patterns")
    for i, pattern in enumerate(urls.urlpatterns):
        print(f"  {i+1}. {pattern.pattern} -> {pattern.name}")
    
    # Test if the admin views exist
    admin_views = ['admin_departments', 'admin_courses_enhanced', 'admin_department_detail', 'admin_course_create']
    for view_name in admin_views:
        if hasattr(views, view_name):
            print(f"✅ {view_name} view exists")
        else:
            print(f"❌ {view_name} view missing")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\nTesting URL inclusion in main URLconf...")
try:
    from django.urls import get_resolver
    resolver = get_resolver()
    
    # Check if institutions URLs are included
    institutions_found = False
    for pattern in resolver.url_patterns:
        if hasattr(pattern, 'url_patterns') and 'institutions' in str(pattern.pattern):
            institutions_found = True
            print(f"✅ Found institutions URL pattern: {pattern.pattern}")
            
            # Check if admin patterns are in the included URLs
            admin_patterns = []
            for sub_pattern in pattern.url_patterns:
                if 'admin' in str(sub_pattern.pattern):
                    admin_patterns.append(str(sub_pattern.pattern))
            
            if admin_patterns:
                print(f"✅ Found {len(admin_patterns)} admin patterns:")
                for ap in admin_patterns:
                    print(f"  - {ap}")
            else:
                print("❌ No admin patterns found in institutions URLs")
    
    if not institutions_found:
        print("❌ institutions URL pattern not found in main URLconf")
        
except Exception as e:
    print(f"❌ Error checking URL inclusion: {e}")
    import traceback
    traceback.print_exc()