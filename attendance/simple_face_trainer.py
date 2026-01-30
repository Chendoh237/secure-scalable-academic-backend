#!/usr/bin/env python3
"""
Simple Face Trainer - Based on working implementation
Integrates with Django models and dynamic configuration
"""

import os
import cv2
import pickle
import numpy as np
from pathlib import Path
from PIL import Image
import django

# Django setup
BASE_DIR = Path(__file__).resolve().parent.parent
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
django.setup()

from students.models import Student
from .face_config import face_config

# Paths and constants
MODEL_DIR = BASE_DIR / "ml_models"
STUDENT_PHOTOS_DIR = MODEL_DIR / "student_photos"
MODEL_FILE = MODEL_DIR / "face_trainer.yml"
LABELS_FILE = MODEL_DIR / "labels.pkl"

# Face detection
cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(cascade_path)

def train_face_recognition():
    """Train face recognition model using dynamic configuration"""
    
    # Get current configuration
    config = face_config.get_optimized_config()
    IMG_SIZE = config["img_size"]
    
    print(f"🔧 Using configuration for {config['student_count']} students:")
    print(f"   📏 Image size: {IMG_SIZE}")
    print(f"   🎯 Confidence threshold: {config['confidence_threshold']}")
    print(f"   📊 Scale factor: {config['scale_factor']}")
    print(f"   👥 Min neighbors: {config['min_neighbors']}")
    print(f"   🔄 Data augmentation: {config['data_augmentation_level']}")
    
    # Create recognizer with your proven approach
    recognizer = cv2.face.LBPHFaceRecognizer_create()
    
    label_ids = {}
    current_id = 0
    x_train = []
    y_labels = []
    
    print(f"\n🔍 Scanning student photos: {STUDENT_PHOTOS_DIR}")
    
    if not STUDENT_PHOTOS_DIR.exists():
        raise SystemExit(f"❌ Student photos directory not found: {STUDENT_PHOTOS_DIR}")
    
    # Process each student directory
    for student_dir in STUDENT_PHOTOS_DIR.iterdir():
        if not student_dir.is_dir():
            continue
            
        matric_number = student_dir.name
        print(f"📸 Processing student: {matric_number}")
        
        # Verify student exists in database
        try:
            student = Student.objects.get(matric_number=matric_number)
            print(f"   ✅ Found in database: {student.full_name}")
        except Student.DoesNotExist:
            print(f"   ⚠️  Student {matric_number} not found in database - skipping")
            continue
        
        # Assign label ID
        if matric_number not in label_ids:
            label_ids[matric_number] = current_id
            current_id += 1
        
        id_ = label_ids[matric_number]
        student_faces = 0
        
        # Process all images for this student
        for img_path in student_dir.glob("*"):
            if img_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
                continue
                
            try:
                # Load image as grayscale (your approach)
                img = Image.open(img_path).convert("L")
                img_array = np.array(img, "uint8")
                
                # Detect faces using dynamic parameters
                faces = face_cascade.detectMultiScale(
                    img_array, 
                    scaleFactor=config["scale_factor"], 
                    minNeighbors=config["min_neighbors"]
                )
                
                if len(faces) == 0:
                    print(f"     ⚠️  No face found in {img_path.name} - skipping")
                    continue
                
                # Process each detected face
                for (x, y, w, h) in faces:
                    roi = img_array[y:y+h, x:x+w]
                    roi_resized = cv2.resize(roi, IMG_SIZE)
                    
                    # Add original face
                    x_train.append(roi_resized)
                    y_labels.append(id_)
                    student_faces += 1
                    
                    # Add data augmentation based on configuration
                    augmentation_config = face_config.get_augmentation_config()
                    
                    # Add rotations
                    for angle in augmentation_config["rotations"]:
                        rows, cols = roi_resized.shape
                        rotation_matrix = cv2.getRotationMatrix2D((cols/2, rows/2), angle, 1)
                        rotated_face = cv2.warpAffine(roi_resized, rotation_matrix, (cols, rows))
                        x_train.append(rotated_face)
                        y_labels.append(id_)
                        student_faces += 1
                    
                    # Add brightness variations
                    for brightness in augmentation_config["brightness_variations"]:
                        bright_face = cv2.convertScaleAbs(roi_resized, alpha=brightness, beta=0)
                        x_train.append(bright_face)
                        y_labels.append(id_)
                        student_faces += 1
                    
                    # Add horizontal flip if enabled
                    if augmentation_config["enable_flipping"]:
                        flipped_face = cv2.flip(roi_resized, 1)
                        x_train.append(flipped_face)
                        y_labels.append(id_)
                        student_faces += 1
                    
                    # Add noise if enabled
                    if augmentation_config["enable_noise"]:
                        noise = np.random.randint(0, 25, roi_resized.shape, dtype=np.uint8)
                        noisy_face = cv2.add(roi_resized, noise)
                        x_train.append(noisy_face)
                        y_labels.append(id_)
                        student_faces += 1
                    
            except Exception as e:
                print(f"     ❌ Error processing {img_path.name}: {e}")
                continue
        
        print(f"   📊 Generated {student_faces} training samples (including augmentation)")
    
    if len(x_train) == 0:
        raise SystemExit("❌ No training data found. Add images to ml_models/student_photos/<matric_number>/ and re-run.")
    
    # Update student count in configuration
    actual_student_count = len(label_ids)
    if actual_student_count != config["student_count"]:
        print(f"🔄 Updating configuration: detected {actual_student_count} students")
        face_config.update_student_count(actual_student_count)
        config = face_config.get_optimized_config()
    
    print(f"\n🎯 Training model...")
    print(f"   📊 {len(x_train)} samples from {len(label_ids)} students")
    print(f"   👥 Students: {list(label_ids.keys())}")
    
    # Train the model
    recognizer.train(x_train, np.array(y_labels))
    
    # Save model and labels
    MODEL_DIR.mkdir(exist_ok=True)
    recognizer.write(str(MODEL_FILE))
    
    with open(LABELS_FILE, "wb") as f:
        pickle.dump(label_ids, f)
    
    print(f"\n✅ Training complete!")
    print(f"   💾 Model saved to: {MODEL_FILE}")
    print(f"   🏷️  Labels saved to: {LABELS_FILE}")
    print(f"   📋 Label mapping: {label_ids}")
    print(f"   ⚙️  Configuration optimized for {actual_student_count} students")
    
    return {
        'success': True,
        'total_students': len(label_ids),
        'total_samples': len(x_train),
        'label_mapping': label_ids,
        'model_file': str(MODEL_FILE),
        'labels_file': str(LABELS_FILE),
        'configuration': config
    }

if __name__ == "__main__":
    try:
        result = train_face_recognition()
        print(f"\n🎉 Success! Trained {result['total_students']} students with {result['total_samples']} samples")
    except Exception as e:
        print(f"❌ Training failed: {e}")
        import traceback
        traceback.print_exc()