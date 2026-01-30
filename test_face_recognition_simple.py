#!/usr/bin/env python3
"""
Simple Face Recognition Test
"""

import os
import sys
import django
import cv2
import pickle
import numpy as np
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

def test_face_recognition():
    """Test face recognition with existing models"""
    print("=== Testing Face Recognition ===")
    
    model_dir = Path("ml_models")
    model_file = model_dir / "face_trainer.yml"
    labels_file = model_dir / "labels.pkl"
    
    # Check if files exist
    if not model_file.exists():
        print("❌ Model file not found!")
        return
        
    if not labels_file.exists():
        print("❌ Labels file not found!")
        return
    
    # Load model and labels
    try:
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(str(model_file))
        print("✅ Model loaded successfully")
        
        with open(labels_file, "rb") as f:
            label_map = pickle.load(f)
        
        id_to_matric = {v: k for k, v in label_map.items()}
        print(f"✅ Labels loaded: {len(label_map)} students")
        
        print("\nTrained students:")
        for matric, label_id in label_map.items():
            print(f"  {matric} -> Label ID: {label_id}")
            
        print(f"\nID to Matric mapping:")
        for label_id, matric in id_to_matric.items():
            print(f"  Label ID {label_id} -> {matric}")
        
        # Test with a sample image
        photos_dir = model_dir / "student_photos"
        if photos_dir.exists():
            # Find first student with photos
            for student_dir in photos_dir.iterdir():
                if student_dir.is_dir():
                    photo_files = list(student_dir.glob("*.jpg"))
                    if photo_files:
                        test_photo = photo_files[0]
                        print(f"\nTesting with: {test_photo}")
                        
                        # Load and process image
                        img = cv2.imread(str(test_photo))
                        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                        
                        # Detect faces
                        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
                        faces = face_cascade.detectMultiScale(gray, 1.05, 6, minSize=(50, 50))
                        
                        if len(faces) > 0:
                            x, y, w, h = faces[0]
                            face_roi = gray[y:y+h, x:x+w]
                            face_resized = cv2.resize(face_roi, (200, 200))
                            
                            # Predict
                            label_id, confidence = recognizer.predict(face_resized)
                            predicted_matric = id_to_matric.get(label_id, "Unknown")
                            
                            print(f"Prediction: Label ID {label_id} -> {predicted_matric}")
                            print(f"Confidence: {confidence}")
                            print(f"Expected: {student_dir.name}")
                            
                            if predicted_matric == student_dir.name:
                                print("✅ Recognition SUCCESSFUL!")
                            else:
                                print("❌ Recognition FAILED!")
                        else:
                            print("No faces detected in test image")
                        break
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_face_recognition()