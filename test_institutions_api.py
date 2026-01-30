#!/usr/bin/env python3
"""
Test script for Institutions API endpoints
"""

import requests
import json

BASE_URL = "http://localhost:8000/api/institutions"

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
                    print(f"Data count: {len(result['data']) if isinstance(result['data'], list) else 'N/A'}")
                elif 'message' in result:
                    print(f"Message: {result['message']}")
            except:
                print(f"Response: {response.text[:200]}...")
        else:
            print(f"Error: {response.text[:200]}...")
            
    except Exception as e:
        print(f"Request failed: {e}")

def main():
    print("Testing Institutions API Endpoints...")
    
    # Test basic endpoints
    test_endpoint("departments")
    test_endpoint("admin/departments")
    test_endpoint("admin/courses")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()