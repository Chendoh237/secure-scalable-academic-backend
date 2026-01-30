#!/usr/bin/env python
"""
Test script for active_sessions API endpoint via HTTP
"""

import requests
import json

def test_active_sessions_http():
    """Test the active_sessions API endpoint via HTTP"""
    print("Testing active_sessions API endpoint via HTTP...")
    
    try:
        # First, login to get authentication
        login_url = "http://localhost:8000/api/auth/login/"
        login_data = {
            "username": "admin",  # Assuming there's an admin user
            "password": "admin123"  # Default admin password
        }
        
        session = requests.Session()
        
        # Try to login
        try:
            login_response = session.post(login_url, json=login_data)
            print(f"Login status: {login_response.status_code}")
            
            if login_response.status_code != 200:
                print("Login failed, testing without authentication...")
                # Test without authentication to see the error
                response = requests.get("http://localhost:8000/api/admin/sessions/active/")
                print(f"Response status (no auth): {response.status_code}")
                print(f"Response text: {response.text}")
                return False
                
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to Django server. Make sure it's running on localhost:8000")
            return False
        
        # Test the active sessions endpoint
        api_url = "http://localhost:8000/api/admin/sessions/active/"
        
        try:
            response = session.get(api_url)
            print(f"Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Response data: {data}")
                print("✓ active_sessions API working correctly via HTTP")
                return True
            else:
                print(f"Response text: {response.text}")
                print(f"❌ active_sessions API returned status {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            print("❌ Cannot connect to Django server. Make sure it's running on localhost:8000")
            return False
            
    except Exception as e:
        print(f"❌ Error testing active_sessions via HTTP: {str(e)}")
        return False

if __name__ == '__main__':
    success = test_active_sessions_http()
    if not success:
        print("\nNote: Make sure the Django development server is running:")
        print("  python backend/manage.py runserver")