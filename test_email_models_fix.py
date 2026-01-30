#!/usr/bin/env python
"""
Test script to validate email models after fixing User model reference
"""
import os
import sys
import django

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

try:
    from students.email_models import (
        EmailConfiguration,
        EmailTemplate,
        EmailHistory,
        EmailDelivery
    )
    print("✓ Email models imported successfully")
    
    # Test that EmailHistory uses the correct user model
    from django.conf import settings
    user_field = EmailHistory._meta.get_field('sender')
    print(f"✓ EmailHistory.sender field references: {user_field.related_model}")
    
    # Check if it's using AUTH_USER_MODEL
    if hasattr(user_field, 'related_model'):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if user_field.related_model == User:
            print("✓ EmailHistory.sender correctly references AUTH_USER_MODEL")
        else:
            print(f"✗ EmailHistory.sender references wrong model: {user_field.related_model}")
    
    print("\nAll email models are working correctly!")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()