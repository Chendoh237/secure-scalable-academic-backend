#!/usr/bin/env python
"""
Test script for active_sessions API endpoint
"""

import os
import sys
import django
from django.conf import settings

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import force_authenticate
from students.admin_views import active_sessions

User = get_user_model()

def test_active_sessions():
    """Test the active_sessions API endpoint"""
    print("Testing active_sessions API endpoint...")
    
    try:
        # Create request factory and user
        factory = RequestFactory()
        request = factory.get('/api/admin/sessions/active/')
        
        # Create or get a test user
        user, created = User.objects.get_or_create(
            username='testuser',
            defaults={'email': 'test@example.com'}
        )
        
        # Authenticate the request
        force_authenticate(request, user=user)
        
        # Call the active_sessions function
        response = active_sessions(request)
        
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        
        if response.status_code == 200:
            print("✓ active_sessions API working correctly")
            return True
        else:
            print(f"❌ active_sessions API returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing active_sessions: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_active_sessions()
    sys.exit(0 if success else 1)