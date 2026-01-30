#!/usr/bin/env python3
"""
Test script to verify face recognition setup
Run this to check if your face recognition models are properly configured
"""

import os
import sys
import django
from pathlib import Path

# Django setup
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from attendance.face_recognition import face_recognition_service
from students.models import Student

def test_face_recognition_setup():
    """Test the face recognition service setup"""
    print("🔍 Testing Face Recognition Setup...")
    print("=" * 50)
    
    try:
        # Test model status
        status = face_recognition_service.get_model_status()
        
        print("📊 Model Status:")
        print(f"  ✓ Model loaded: {status['model_loaded']}")
        print(f"  ✓ Labels loaded: {status['labels_loaded']}")
        print(f"  ✓ Cascade loaded: {status['cascade_loaded']}")
        print(f"  ✓ Total students: {status['total_students']}")
        print(f"  ✓ Model file exists: {status['model_file_exists']}")
        print(f"  ✓ Labels file exists: {status['labels_file_exists']}")
        
        if not status['model_loaded']:
            print("\n❌ Face recognition model not loaded!")
            print("   Please ensure you have:")
            print("   1. Trained the face recognition model")
            print("   2. face_trainer.yml file in backend/ml_models/")
            print("   3. labels.pkl file in backend/ml_models/")
            return False
        
        # Test database connection
        print(f"\n👥 Database Status:")
        total_students = Student.objects.count()
        approved_students = Student.objects.filter(is_approved=True).count()
        trained_students = Student.objects.filter(face_trained=True).count()
        
        print(f"  ✓ Total students: {total_students}")
        print(f"  ✓ Approved students: {approved_students}")
        print(f"  ✓ Face-trained students: {trained_students}")
        
        if total_students == 0:
            print("\n⚠️  No students found in database!")
            print("   Please add and approve students first.")
        
        if trained_students == 0:
            print("\n⚠️  No students have trained faces!")
            print("   Please train face models for students.")
        
        # Test file paths
        print(f"\n📁 File Paths:")
        model_dir = face_recognition_service.model_dir
        print(f"  ✓ Model directory: {model_dir}")
        print(f"  ✓ Model file: {face_recognition_service.model_file}")
        print(f"  ✓ Labels file: {face_recognition_service.labels_file}")
        print(f"  ✓ Cascade file: {face_recognition_service.cascade_path}")
        
        # Test label mappings
        if status['labels_loaded'] and status['total_students'] > 0:
            print(f"\n🏷️  Label Mappings (first 5):")
            for i, (matric, label_id) in enumerate(list(face_recognition_service.label_map.items())[:5]):
                print(f"  ✓ {matric} -> {label_id}")
                if i >= 4:  # Show only first 5
                    break
        
        print(f"\n✅ Face Recognition Setup Test Complete!")
        
        if all([
            status['model_loaded'],
            status['labels_loaded'], 
            status['cascade_loaded'],
            total_students > 0,
            approved_students > 0
        ]):
            print("🎉 All systems ready for face tracking!")
            return True
        else:
            print("⚠️  Some issues found. Please address them before using face tracking.")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during setup test: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_usage_instructions():
    """Show instructions for using the face tracking system"""
    print("\n" + "=" * 50)
    print("📋 Usage Instructions:")
    print("=" * 50)
    print("1. Start your Django development server:")
    print("   python manage.py runserver")
    print()
    print("2. Start your React frontend:")
    print("   npm run dev")
    print()
    print("3. Login as admin and navigate to:")
    print("   http://localhost:5173/admin/face-tracking")
    print()
    print("4. Select an active live session (optional)")
    print("5. Click 'Start' to begin face tracking")
    print("6. Allow camera permissions when prompted")
    print("7. Students will be automatically recognized and attendance marked")
    print()
    print("🔧 Troubleshooting:")
    print("- Ensure good lighting for face detection")
    print("- Make sure students look directly at camera")
    print("- Check browser console for any errors")
    print("- Verify camera permissions are granted")

if __name__ == "__main__":
    success = test_face_recognition_setup()
    
    if success:
        show_usage_instructions()
    else:
        print("\n❌ Please fix the issues above before proceeding.")
        print("💡 Need help? Check the documentation or contact support.")