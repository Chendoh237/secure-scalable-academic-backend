#!/usr/bin/env python3
"""
Retrain Face Recognition Models
"""

import os
import sys
import django
import cv2
import numpy as np
import pickle
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from students.models import Student

def retrain_face_models():
    """Retrain face recognition models with all available student photos"""
    print("=== Retraining Face Recognition Models ===")
    
    model_dir = Path("ml_models")
    photos_dir = model_dir / "student_photos"
    
    if not photos_dir.exists():
        print("❌ Student photos directory not found!")
        return
    
    # Initialize face detector
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    
    # Prepare training data
    faces = []
    labels = []
    label_map = {}
    current_label = 0
    
    print("Processing student photos...")
    
    # Process each student directory
    for student_dir in photos_dir.iterdir():
        if not student_dir.is_dir():
            continue
            
        matric_number = student_dir.name
        print(f"Processing student: {matric_number}")
        
        # Check if student exists in database
        try:
            student = Student.objects.get(matric_number=matric_number)
            print(f"  ✅ Found in database: {student.full_name}")
        except Student.DoesNotExist:
            print(f"  ⚠️  Not found in database, skipping...")
            continue
        
        # Assign label
        label_map[matric_number] = current_label
        student_faces = 0
        
        # Process all photos for this student
        for photo_file in student_dir.glob("*.jpg"):
            try:
                # Read image
                img = cv2.imread(str(photo_file))
                if img is None:
                    continue
                    
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Detect faces
                detected_faces = face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.05,
                    minNeighbors=6,
                    minSize=(50, 50),
                    maxSize=(300, 300)
                )
                
                # Process each detected face
                for (x, y, w, h) in detected_faces:
                    # Extract face region with padding
                    padding = 10
                    x_start = max(0, x - padding)
                    y_start = max(0, y - padding)
                    x_end = min(gray.shape[1], x + w + padding)
                    y_end = min(gray.shape[0], y + h + padding)
                    
                    face_roi = gray[y_start:y_end, x_start:x_end]
                    
                    if face_roi.size > 0:
                        # Resize to standard size
                        face_resized = cv2.resize(face_roi, (200, 200))
                        
                        # Apply histogram equalization
                        face_resized = cv2.equalizeHist(face_resized)
                        
                        faces.append(face_resized)
                        labels.append(current_label)
                        student_faces += 1
                        
            except Exception as e:
                print(f"    Error processing {photo_file}: {e}")
                continue
        
        print(f"  Processed {student_faces} faces")
        current_label += 1
    
    print(f"\nTotal students: {len(label_map)}")
    print(f"Total face samples: {len(faces)}")
    
    if len(faces) == 0:
        print("❌ No face samples found!")
        return
    
    # Train the recognizer
    print("Training face recognizer...")
    recognizer = cv2.face.LBPHFaceRecognizer_create(
        radius=1,
        neighbors=8,
        grid_x=8,
        grid_y=8,
        threshold=100.0
    )
    
    recognizer.train(faces, np.array(labels))
    
    # Save the model
    model_file = model_dir / "face_trainer.yml"
    recognizer.save(str(model_file))
    print(f"✅ Model saved to: {model_file}")
    
    # Save label mappings
    labels_file = model_dir / "labels.pkl"
    with open(labels_file, "wb") as f:
        pickle.dump(label_map, f)
    print(f"✅ Labels saved to: {labels_file}")
    
    print("\nLabel mappings:")
    for matric, label_id in label_map.items():
        print(f"  {matric} -> {label_id}")
    
    print("\n🎉 Face recognition model training completed!")
    print("You can now use the face tracking system.")

if __name__ == "__main__":
    retrain_face_models()