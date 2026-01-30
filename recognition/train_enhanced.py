import os
import cv2
import pickle
import numpy as np
import logging
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from tqdm import tqdm
import dlib
import face_recognition
from concurrent.futures import ThreadPoolExecutor
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score
import joblib

# Local imports
from .face_utils import FaceProcessor, enhance_image

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# Configuration
# ---------------------------
BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "dataset"
MODEL_DIR = BASE_DIR.parent / "ml_models"
MODEL_DIR.mkdir(exist_ok=True)

# Model files
ENCODINGS_FILE = MODEL_DIR / "face_encodings.pkl"
LABEL_ENCODER_FILE = MODEL_DIR / "label_encoder.pkl"
SVM_MODEL_FILE = MODEL_DIR / "svm_face_classifier.pkl"

# Training parameters
TEST_SIZE = 0.2
RANDOM_STATE = 42
MIN_SAMPLES = 5  # Minimum number of face samples required per student

class FaceTrainer:
    def __init__(self):
        self.face_processor = FaceProcessor()
        self.known_face_encodings = []
        self.known_face_labels = []
        self.label_encoder = LabelEncoder()
        self.svm_classifier = SVC(probability=True, kernel='linear')
        
    def process_student_folder(self, student_folder):
        """Process all images for a single student."""
        student_id = student_folder.name
        image_paths = list(student_folder.glob("*.jpg")) + list(student_folder.glob("*.png"))
        
        if len(image_paths) < MIN_SAMPLES:
            logger.warning(f"Skipping {student_id}: Insufficient samples ({len(image_paths)} < {MIN_SAMPLES})")
            return []
            
        logger.info(f"Processing {len(image_paths)} images for student {student_id}")
        
        student_encodings = []
        
        for image_path in tqdm(image_paths, desc=f"Processing {student_id}"):
            try:
                # Load and enhance image
                image = cv2.imread(str(image_path))
                if image is None:
                    logger.warning(f"Could not read image: {image_path}")
                    continue
                    
                # Enhance image quality
                enhanced = enhance_image(image)
                
                # Detect faces
                faces = self.face_processor.detect_faces(enhanced)
                
                if not faces:
                    logger.warning(f"No faces detected in {image_path}")
                    continue
                    
                # Process each face
                for face in faces:
                    # Get face bounding box
                    x, y, w, h = face['box']
                    x, y = max(0, x), max(0, y)  # Ensure coordinates are not negative
                    
                    # Extract face ROI
                    face_roi = enhanced[y:y+h, x:x+w]
                    
                    # Assess face quality
                    quality = self.face_processor.assess_face_quality(face_roi)
                    
                    if quality and quality['is_good_quality']:
                        # Align face
                        aligned_face = self.face_processor.align_face(enhanced, (x, y, w, h))
                        
                        if aligned_face is not None:
                            # Get face encoding
                            encoding = self.face_processor.get_face_encoding(aligned_face)
                            
                            if encoding is not None:
                                student_encodings.append((student_id, encoding))
                                
            except Exception as e:
                logger.error(f"Error processing {image_path}: {e}")
                continue
                
        return student_encodings
    
    def train_model(self):
        """Train the face recognition model."""
        if not DATASET_PATH.exists():
            logger.error(f"Dataset directory not found: {DATASET_PATH}")
            return False
            
        # Get list of student folders
        student_folders = [f for f in DATASET_PATH.iterdir() if f.is_dir()]
        
        if not student_folders:
            logger.error(f"No student folders found in {DATASET_PATH}")
            return False
            
        logger.info(f"Found {len(student_folders)} student folders")
        
        # Process all student folders in parallel
        all_encodings = []
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(self.process_student_folder, student_folders))
            
        # Flatten results
        for result in results:
            all_encodings.extend(result)
            
        if not all_encodings:
            logger.error("No valid face encodings found in the dataset")
            return False
            
        # Separate labels and encodings
        labels, encodings = zip(*all_encodings)
        
        # Encode labels
        encoded_labels = self.label_encoder.fit_transform(labels)
        
        # Split data into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(
            encodings, encoded_labels, 
            test_size=TEST_SIZE, 
            random_state=RANDOM_STATE,
            stratify=encoded_labels
        )
        
        # Train SVM classifier
        logger.info("Training SVM classifier...")
        self.svm_classifier.fit(X_train, y_train)
        
        # Evaluate on test set
        y_pred = self.svm_classifier.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"Model accuracy: {accuracy:.2f}")
        
        return True
    
    def save_model(self):
        """Save the trained model and metadata."""
        try:
            # Save the SVM classifier
            joblib.dump(self.svm_classifier, str(SVM_MODEL_FILE))
            
            # Save the label encoder
            with open(LABEL_ENCODER_FILE, 'wb') as f:
                pickle.dump(self.label_encoder, f)
                
            logger.info(f"Model saved to {MODEL_DIR}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving model: {e}")
            return False

def main():
    """Main function to train the face recognition model."""
    logger.info("Starting face recognition model training...")
    
    # Initialize trainer
    trainer = FaceTrainer()
    
    # Train model
    if trainer.train_model():
        # Save model if training was successful
        if trainer.save_model():
            logger.info("Training completed successfully!")
        else:
            logger.error("Failed to save the trained model")
    else:
        logger.error("Model training failed")

if __name__ == "__main__":
    main()
