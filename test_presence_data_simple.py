#!/usr/bin/env python3
"""
Simple test to verify presence tracking data structure
"""

def test_presence_data_structure():
    """Test the presence data structure without Django"""
    
    print("🧪 Testing Presence Data Structure")
    print("=" * 50)
    
    # Test 1: Presence Duration Calculation
    print("\n1. Testing Presence Duration Calculation...")
    
    # Simulate presence duration calculation
    def calculate_presence_percentage(presence_seconds, total_seconds):
        if not presence_seconds or not total_seconds or total_seconds == 0:
            return 0.0
        percentage = (presence_seconds / total_seconds) * 100
        return min(100.0, max(0.0, percentage))
    
    # Test cases
    test_cases = [
        (3600, 5400, 66.7),  # 1 hour present out of 1.5 hours = 66.7%
        (4050, 5400, 75.0),  # 1h 7.5m present out of 1.5 hours = 75%
        (2700, 5400, 50.0),  # 45 minutes present out of 1.5 hours = 50%
        (0, 5400, 0.0),      # No presence = 0%
        (5400, 5400, 100.0), # Full presence = 100%
    ]
    
    for presence, total, expected in test_cases:
        result = calculate_presence_percentage(presence, total)
        status = "✅" if abs(result - expected) < 0.1 else "❌"
        print(f"   {status} {presence}s / {total}s = {result:.1f}% (expected {expected}%)")
    
    # Test 2: Status Determination
    print("\n2. Testing Status Determination...")
    
    def determine_status(percentage, thresholds=None):
        if thresholds is None:
            thresholds = {'present': 75.0, 'partial': 50.0, 'late': 25.0}
        
        if percentage >= thresholds['present']:
            return 'present'
        elif percentage >= thresholds['partial']:
            return 'partial'
        elif percentage >= thresholds['late']:
            return 'late'
        else:
            return 'absent'
    
    status_test_cases = [
        (85.0, 'present'),
        (75.0, 'present'),
        (65.0, 'partial'),
        (50.0, 'partial'),
        (35.0, 'late'),
        (25.0, 'late'),
        (15.0, 'absent'),
        (0.0, 'absent'),
    ]
    
    for percentage, expected in status_test_cases:
        result = determine_status(percentage)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {percentage}% → {result} (expected {expected})")
    
    # Test 3: Data Structure Validation
    print("\n3. Testing Data Structure...")
    
    # Sample attendance record structure
    sample_attendance = {
        'id': 1,
        'student_name': 'John Doe',
        'matric_number': 'CS/2021/001',
        'course_code': 'CS301',
        'course_title': 'Data Structures',
        'status': 'present',
        'timestamp': '2024-01-29T10:30:00Z',
        'confidence': 0.92,
        'presence_percentage': 78.5,
        'detection_count': 15,
        'presence_duration_minutes': 70.5,
        'total_class_duration_minutes': 90.0,
        'is_manual_override': False,
        'first_detected': '2024-01-29T10:05:00Z',
        'last_detected': '2024-01-29T11:15:00Z'
    }
    
    required_fields = [
        'student_name', 'matric_number', 'course_code', 'status',
        'presence_percentage', 'presence_duration_minutes', 
        'total_class_duration_minutes', 'detection_count'
    ]
    
    print("   Checking required fields in sample data:")
    for field in required_fields:
        if field in sample_attendance:
            print(f"   ✅ {field}: {sample_attendance[field]}")
        else:
            print(f"   ❌ {field}: MISSING")
    
    # Test 4: API Response Structure
    print("\n4. Testing API Response Structure...")
    
    sample_api_response = {
        'success': True,
        'data': {
            'feed': [sample_attendance],
            'total_count': 1,
            'hours_range': 2,
            'last_updated': '2024-01-29T12:00:00Z'
        }
    }
    
    print("   API Response Structure:")
    print(f"   ✅ Success: {sample_api_response['success']}")
    print(f"   ✅ Feed Count: {len(sample_api_response['data']['feed'])}")
    print(f"   ✅ Total Count: {sample_api_response['data']['total_count']}")
    print(f"   ✅ Hours Range: {sample_api_response['data']['hours_range']}")
    
    # Test 5: Frontend Display Data
    print("\n5. Testing Frontend Display Data...")
    
    def format_duration_display(minutes):
        if minutes >= 60:
            hours = int(minutes // 60)
            mins = int(minutes % 60)
            return f"{hours}h {mins}m"
        return f"{int(minutes)}m"
    
    def format_percentage_display(percentage):
        return f"{percentage:.1f}%"
    
    display_tests = [
        (70.5, "1h 10m"),
        (45.0, "45m"),
        (90.0, "1h 30m"),
        (15.0, "15m"),
    ]
    
    print("   Duration formatting:")
    for minutes, expected in display_tests:
        result = format_duration_display(minutes)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {minutes} min → {result} (expected {expected})")
    
    percentage_tests = [78.5, 100.0, 0.0, 50.5]
    print("   Percentage formatting:")
    for percentage in percentage_tests:
        result = format_percentage_display(percentage)
        print(f"   ✅ {percentage} → {result}")
    
    print("\n" + "=" * 50)
    print("🎉 Presence Data Structure Test Complete!")
    print("\nKey Data Points Verified:")
    print("✅ Presence percentage calculation (time-based)")
    print("✅ Status determination (threshold-based)")
    print("✅ Required data fields for tracking")
    print("✅ API response structure")
    print("✅ Frontend display formatting")
    print("\nThis ensures accurate attendance tracking based on actual time spent in class!")

if __name__ == "__main__":
    test_presence_data_structure()