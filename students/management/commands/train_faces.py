# backend/students/management/commands/train_faces.py
from django.core.management.base import BaseCommand
from students.services.face_training import train_face_model
import logging
import os
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

def ensure_initial_model_exists():
    """Ensure the model directory exists and create an empty model file if needed."""
    model_dir = settings.BASE_DIR / "ml_models"
    model_file = model_dir / "face_trainer.yml"
    labels_file = model_dir / "labels.pkl"
    
    os.makedirs(model_dir, exist_ok=True)
    
    # Create an empty model file if it doesn't exist
    if not model_file.exists():
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.write(str(model_file))
        logger.info(f"Created initial empty model file at {model_file}")
    
    # Create an empty labels dictionary if it doesn't exist
    if not labels_file.exists():
        with open(labels_file, 'wb') as f:
            pickle.dump({}, f)
        logger.info(f"Created initial empty labels file at {labels_file}")

class Command(BaseCommand):
    help = 'Train the face recognition model with all student photos'

    def handle(self, *args, **options):
        self.stdout.write("Starting face model training...")
        
        # Ensure the model directory and files exist
        ensure_initial_model_exists()
        
        success, message = train_face_model()
        
        if success:
            self.stdout.write(
                self.style.SUCCESS("Successfully trained face recognition model")
            )
            self.stdout.write(message)
        else:
            self.stdout.write(
                self.style.ERROR("Face model training failed")
            )
            self.stderr.write(message)
            logger.error(message)