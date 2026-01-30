import requests

# Test if the server is accessible
try:
    response = requests.get('http://localhost:8000/api/admin/attendance/')
    print(f"Basic attendance endpoint: {response.status_code}")
    
    response = requests.get('http://localhost:8000/api/admin/attendance/export/')
    print(f"Export endpoint (no auth): {response.status_code}")
    
except Exception as e:
    print(f"Error: {e}")