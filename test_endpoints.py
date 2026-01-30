#!/usr/bin/env python
"""
Simple test to check if the attendance endpoints are accessible
"""
import requests
import json

def test_endpoints():
    base_url = "http://localhost:8000"
    
    # First, try to get a token
    print("Testing authentication...")
    try:
        auth_response = requests.post(f"{base_url}/api/token/", {
            'username': 'admin',
            'password': 'admin123'
        })
        
        if auth_response.status_code == 200:
            token = auth_response.json()['access']
            headers = {'Authorization': f'Bearer {token}'}
            print("✓ Authentication successful")
            
            # Test basic attendance endpoint
            print("\nTesting attendance records endpoint...")
            attendance_response = requests.get(f"{base_url}/api/admin/attendance/", headers=headers)
            print(f"Status: {attendance_response.status_code}")
            if attendance_response.status_code != 200:
                print(f"Error: {attendance_response.text}")
            else:
                print("✓ Attendance records endpoint working")
            
            # Test export endpoint
            print("\nTesting export endpoint...")
            export_response = requests.get(f"{base_url}/api/admin/attendance/export/?format=excel", headers=headers)
            print(f"Status: {export_response.status_code}")
            if export_response.status_code != 200:
                print(f"Error: {export_response.text}")
            else:
                print("✓ Export endpoint working")
                print(f"Content-Type: {export_response.headers.get('content-type')}")
                
        else:
            print(f"❌ Authentication failed: {auth_response.status_code}")
            print(f"Response: {auth_response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure Django server is running on localhost:8000")
    except Exception as e:
        print(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    test_endpoints()