#!/usr/bin/env python3
"""
Check Face Recognition Models and Training Data
"""

import os
import sys
import pickle
import cv2
from pathlib import Path

def check_face_models():
    """Check the status of face recognition models and training data"""
    print("=== Face Recognition Model Status ===")
    
    # Check model files
    model_dir = Path("ml_models")
    model_file = model_dir / "face_trainer.yml"
    labels_file = model_dir / "labels.pkl"
    
    print(f"Model directory: {model_dir.absolute()}")
    print(f"Model file exists: {model_file.exists()}")
    print(f"Labels file exists: {labels_file.exists()}")
    
    if labels_file.exists():
        try:
            with open(labels_file, "rb") as f:
                labels = pickle.load(f)
            
            print(f"\n✅ Labels loaded successfully!")
            print(f"Number of trained students: {len(labels)}")
            
            if len(labels) > 0:
                print("\nTrained students:")
                for matric, label_id in labels.items():
                    print(f"  {matric} -> Label ID: {label_id}")
            else:
                print("❌ No students trained in the model!")
                
        except Exception as e:
            print(f"❌ Error loading labels: {e}")
    else:
        print("❌ Labels file not found!")
    
    # Check student photos directory
    photos_dir = model_dir / "student_photos"
    print(f"\nStudent photos directory: {photos_dir}")
    print(f"Photos directory exists: {photos_dir.exists()}")
    
    if photos_dir.exists():
        student_dirs = [d for d in photos_dir.iterdir() if d.is_dir()]
        print(f"Number of student photo directories: {len(student_dirs)}")
        
        for student_dir in student_dirs:
            photo_files = list(student_dir.glob("*.jpg")) + list(student_dir.glob("*.png"))
            print(f"  {student_dir.name}: {len(photo_files)} photos")
    
    # Check face cascade
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    print(f"\nFace cascade loaded: {not cascade.empty()}")
    
    # Check if model can be loaded
    if model_file.exists():
        try:
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.read(str(model_file))
            print("✅ Face recognition model loaded successfully!")
        except Exception as e:
            print(f"❌ Error loading face recognition model: {e}")
    else:
        print("❌ Face recognition model file not found!")

if __name__ == "__main__":
    check_face_models()