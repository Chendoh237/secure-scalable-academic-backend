#!/usr/bin/env python3
"""
Test script for Face Tracking API endpoints
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/attendance/face-tracking"

def test_endpoint(endpoint, method="GET", data=None):
    """Test a single API endpoint"""
    url = f"{BASE_URL}/{endpoint}/"
    
    try:
        if method == "GET":
            response = requests.get(url)
        elif method == "POST":
            response = requests.post(url, json=data)
        
        print(f"\n=== {method} {endpoint} ===")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            try:
                result = response.json()
                print(f"Success: {result.get('success', 'N/A')}")
                if 'data' in result:
                    print(f"Data: {json.dumps(result['data'], indent=2)}")
                elif 'message' in result:
                    print(f"Message: {result['message']}")
            except:
                print(f"Response: {response.text}")
        else:
            print(f"Error: {response.text}")
            
    except Exception as e:
        print(f"Request failed: {e}")

def main():
    print("Testing Face Tracking API Endpoints...")
    
    # Test basic endpoints
    test_endpoint("test")
    test_endpoint("model-status")
    test_endpoint("active-sessions")
    test_endpoint("attendance-summary")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()