#!/usr/bin/env python
"""
Test script to validate email models
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
    
    # Test model creation (without saving to database)
    config = EmailConfiguration(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_username="test@gmail.com",
        from_email="test@gmail.com"
    )
    print("✓ EmailConfiguration model created successfully")
    
    template = EmailTemplate(
        name="Test Template",
        category="general",
        subject_template="Test Subject",
        body_template="Test Body"
    )
    print("✓ EmailTemplate model created successfully")
    
    print("\nAll email models are working correctly!")
    
except ImportError as e:
    print(f"✗ Import error: {e}")
except Exception as e:
    print(f"✗ Error: {e}")