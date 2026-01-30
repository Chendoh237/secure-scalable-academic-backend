# backend/recognition/train_model.py
import os
import cv2
import pickle
import numpy as np
import logging
from pathlib import Path
from PIL import Image, UnidentifiedImageError

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------
# Configuration
# ---------------------------
BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "dataset"
MODEL_FILE = Path("ml_models/face_trainer.yml")  # Changed to project root
LABELS_FILE = Path("ml_models/labels.pkl")      # Changed to project root
IMG_SIZE = (200, 200)
MIN_SAMPLES = 5  # Minimum number of face samples required per student

# Ensure output directories exist
Path("ml_models").mkdir(exist_ok=True)

# ---------------------------
# Initialize face detector and recognizer
# ---------------------------
try:
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        raise ValueError("Failed to load face cascade classifier")
    recognizer = cv2.face.LBPHFaceRecognizer_create()
except Exception as e:
    logger.error(f"Error initializing OpenCV components: {e}")
    raise

def load_and_preprocess_image(image_path):
    """Load and preprocess an image for face detection."""
    try:
        image = Image.open(image_path).convert("L")  # Convert to grayscale
        return np.array(image, "uint8")
    except UnidentifiedImageError:
        logger.warning(f"Could not identify image {image_path}")
        return None
    except Exception as e:
        logger.warning(f"Error processing {image_path}: {e}")
        return None

def process_student_images(student_dir, label_id, x_train, y_labels):
    """Process all images for a single student."""
    student_samples = 0
    
    for image_path in student_dir.glob("*"):
        if image_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
            continue

        logger.debug(f"Processing {image_path}")

        # Load and preprocess image
        image_np = load_and_preprocess_image(image_path)
        if image_np is None:
            continue

        # Detect faces
        faces = face_cascade.detectMultiScale(
            image_np,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )

        if len(faces) == 0:
            logger.warning(f"No face detected in {image_path}")
            continue

        # Use the first face found
        x, y, w, h = faces[0]
        roi = image_np[y:y + h, x:x + w]
        roi_resized = cv2.resize(roi, IMG_SIZE)

        x_train.append(roi_resized)
        y_labels.append(label_id)
        student_samples += 1
    
    return student_samples

def main():
    logger.info("Starting face recognition training...")
    
    if not DATASET_PATH.exists():
        error_msg = f"Dataset folder not found: {DATASET_PATH}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    label_ids = {}
    current_id = 0
    x_train = []
    y_labels = []
    student_stats = {}

    # Process each student's directory
    for student_dir in sorted(DATASET_PATH.iterdir()):
        if not student_dir.is_dir():
            continue

        matric_number = student_dir.name
        if matric_number not in label_ids:
            label_ids[matric_number] = current_id
            current_id += 1

        label_id = label_ids[matric_number]
        samples = process_student_images(
            student_dir, label_id, x_train, y_labels
        )
        student_stats[matric_number] = samples
        logger.info(f"Processed {samples} samples for {matric_number}")

    # Validate we have enough training data
    if len(x_train) == 0:
        error_msg = "No valid face data found in dataset"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Check for students with insufficient samples
    for matric, samples in student_stats.items():
        if samples < MIN_SAMPLES:
            logger.warning(
                f"Student {matric} has only {samples} samples (minimum {MIN_SAMPLES} recommended)"
            )

    # Train the model
    logger.info(f"Training model with {len(x_train)} total samples...")
    recognizer.train(x_train, np.array(y_labels))
    
    # Save the model and labels
    recognizer.save(str(MODEL_FILE))
    with open(LABELS_FILE, "wb") as f:
        pickle.dump(label_ids, f)

    logger.info(f"Model trained and saved to {MODEL_FILE}")
    logger.info(f"Label mapping: {label_ids}")

    return {
        "status": "success",
        "samples_processed": len(x_train),
        "students_trained": len(label_ids),
        "model_path": str(MODEL_FILE),
        "labels_path": str(LABELS_FILE)
    }

if __name__ == "__main__":
    main()