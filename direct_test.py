#!/usr/bin/env python3
import requests

print("Testing Face Tracking API...")

# Test endpoints
endpoints = [
    "test",
    "model-status", 
    "active-sessions",
    "attendance-summary"
]

for endpoint in endpoints:
    try:
        url = f"http://localhost:8000/api/attendance/face-tracking/{endpoint}/"
        response = requests.get(url)
        print(f"\n{endpoint}: Status {response.status_code}")
        if response.status_code == 200:
            print(f"✅ Success: {response.json()}")
        else:
            print(f"❌ Error: {response.text}")
    except Exception as e:
        print(f"❌ {endpoint}: {e}")

print("\nDone!")