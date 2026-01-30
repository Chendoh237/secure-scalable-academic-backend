#!/usr/bin/env python3
"""
Simple test for Face Tracking API without authentication
"""

import requests
import json

def test_simple():
    """Test the simple test endpoint"""
    try:
        response = requests.get("http://localhost:8000/api/attendance/face-tracking/test/")
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("✅ API is working!")
        else:
            print("❌ API has issues")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_simple()