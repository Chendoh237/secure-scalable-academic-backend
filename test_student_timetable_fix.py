#!/usr/bin/env python3

import requests
import json

# Test the student timetable endpoint
BASE_URL = "http://localhost:8000"

def test_student_timetable():
    """Test the student timetable endpoint that was returning 403"""
    
    # First, login as a student to get the token
    login_data = {
        "matricule": "EST1234",  # Use a known student
        "password": "testpass123"
    }
    
    print("🔐 Logging in as student...")
    login_response = requests.post(f"{BASE_URL}/api/login/", json=login_data)
    
    if login_response.status_code != 200:
        print(f"❌ Login failed: {login_response.status_code}")
        print(f"Response: {login_response.text}")
        return
    
    login_result = login_response.json()
    token = login_result.get('access')
    
    if not token:
        print("❌ No access token received")
        return
    
    print("✅ Login successful")
    
    # Test the student timetable endpoint
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    print("\n📅 Testing student timetable endpoint...")
    timetable_response = requests.get(f"{BASE_URL}/api/students/timetable/", headers=headers)
    
    print(f"Status Code: {timetable_response.status_code}")
    
    if timetable_response.status_code == 200:
        print("✅ Timetable endpoint working!")
        result = timetable_response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
    else:
        print(f"❌ Timetable endpoint failed: {timetable_response.status_code}")
        print(f"Response: {timetable_response.text}")

if __name__ == "__main__":
    test_student_timetable()