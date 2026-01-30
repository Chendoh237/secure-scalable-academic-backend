# # backend/students/services/face_training.py
# import os
# import subprocess
# import logging
# from pathlib import Path
# from django.conf import settings
# from students.models import Student

# logger = logging.getLogger(__name__)

# def ensure_directories_exist():
#     """Ensure all required directories exist."""
#     dirs = [
#         settings.MEDIA_ROOT / "student_photos",
#         Path("backend/ml_models"),
#         Path("backend/recognition/dataset")
#     ]
#     for directory in dirs:
#         directory.mkdir(parents=True, exist_ok=True)
#         logger.info(f"Ensured directory exists: {directory}")

# def train_face_model(student_ids=None):
#     """
#     Train the face recognition model with approved student photos.
    
#     Args:
#         student_ids: Optional list of specific student IDs to train. If None, trains all approved students.
    
#     Returns:
#         tuple: (success: bool, message: str)
#     """
#     try:
#         ensure_directories_exist()
#         BASE_DIR = settings.BASE_DIR
#         script_path = BASE_DIR / "recognition" / "train_model.py"

#         if not script_path.exists():
#             error_msg = f"train_model.py not found at {script_path}"
#             logger.error(error_msg)
#             return False, error_msg

#         # Get approved students that need training
#         students_query = Student.objects.filter(is_approved=True)
        
#         if student_ids is not None:
#             students_query = students_query.filter(id__in=student_ids)
        
#         students = students_query.filter(face_trained=False)
#         student_count = students.count()
        
#         if student_count == 0:
#             msg = "No approved students found that need face training"
#             logger.info(msg)
#             return True, msg
            
#         logger.info(f"Starting face model training for {student_count} approved students...")
        
#         # Run the training script
#         result = subprocess.run(
#             ["python", str(script_path)],
#             cwd=str(BASE_DIR),  # Run from project root
#             capture_output=True,
#             text=True,
#             check=True
#         )
        
#         # Log the output
#         if result.stdout:
#             logger.info(f"Training output: {result.stdout}")
#         if result.stderr:
#             logger.warning(f"Training warnings: {result.stderr}")

#         # Update student records
#         updated = students.update(face_trained=True)
#         logger.info(f"Updated {updated} approved students with trained faces")
        
#         return True, f"Successfully trained face model for {updated} approved students"
        
#     except subprocess.CalledProcessError as e:
#         error_msg = f"Training failed: {str(e)}\nOutput: {e.output}\nError: {e.stderr}"
#         logger.error(error_msg)
#         return False, error_msg
#     except Exception as e:
#         error_msg = f"Unexpected error in train_face_model: {str(e)}"
#         logger.error(error_msg, exc_info=True)
#         return False, error_msg



# backend/students/services/face_training.py
import os
import subprocess
import logging
from pathlib import Path
from django.conf import settings
from students.models import Student

logger = logging.getLogger(__name__)

def ensure_directories_exist():
    dirs = [
        settings.MEDIA_ROOT / "student_photos",
        Path("backend/ml_models"),
        Path("backend/recognition/dataset")
    ]
    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Ensured directory exists: {directory}")

def train_face_model(student_ids=None):
    """
    Train the face recognition model with approved student photos.
    """
    try:
        ensure_directories_exist()
        BASE_DIR = settings.BASE_DIR
        script_path = BASE_DIR / "recognition" / "train_model.py"

        if not script_path.exists():
            error_msg = f"train_model.py not found at {script_path}"
            logger.error(error_msg)
            return False, error_msg

        students_query = Student.objects.filter(is_approved=True)
        if student_ids is not None:
            students_query = students_query.filter(id__in=student_ids)
        students = students_query.filter(face_trained=False)

        if students.count() == 0:
            msg = "No approved students found that need face training"
            logger.info(msg)
            return True, msg

        result = subprocess.run(
            ["python", str(script_path)],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            check=True
        )

        if result.stdout:
            logger.info(f"Training output: {result.stdout}")
        if result.stderr:
            logger.warning(f"Training warnings: {result.stderr}")

        updated = students.update(face_trained=True)
        return True, f"Successfully trained face model for {updated} approved students"

    except subprocess.CalledProcessError as e:
        return False, f"Training failed: {str(e)}\nOutput: {e.output}\nError: {e.stderr}"
    except Exception as e:
        return False, f"Unexpected error in train_face_model: {str(e)}"
