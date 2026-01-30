#!/usr/bin/env python3
"""
Simple test for settings integration
"""

import os
import sys
import django

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from students.models_settings import SystemSettings

def test_system_settings():
    """Test SystemSettings model"""
    print("🔧 Testing SystemSettings Model...")
    
    try:
        # Test getting settings (should create default if none exist)
        settings = SystemSettings.get_settings()
        print("✅ Successfully retrieved settings")
        print(f"Institution: {settings['general']['institutionName']}")
        print(f"Attendance Threshold: {settings['attendance']['attendanceThreshold']}%")
        
        # Test updating settings
        update_data = {
            'attendance': {
                'attendanceThreshold': 85
            },
            'general': {
                'institutionName': 'Test University'
            }
        }
        
        success = SystemSettings.update_settings(update_data)
        if success:
            print("✅ Successfully updated settings")
            
            # Verify update
            updated_settings = SystemSettings.get_settings()
            print(f"New Institution: {updated_settings['general']['institutionName']}")
            print(f"New Threshold: {updated_settings['attendance']['attendanceThreshold']}%")
            
            return True
        else:
            print("❌ Failed to update settings")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_helper_methods():
    """Test helper methods"""
    print("\n🎯 Testing Helper Methods...")
    
    try:
        threshold = SystemSettings.get_attendance_threshold()
        print(f"✅ Attendance threshold: {threshold}%")
        
        institution_info = SystemSettings.get_institution_info()
        print(f"✅ Institution info: {institution_info}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Testing SystemSettings Integration")
    print("=" * 50)
    
    model_success = test_system_settings()
    helper_success = test_helper_methods()
    
    print("\n" + "=" * 50)
    if model_success and helper_success:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed.")