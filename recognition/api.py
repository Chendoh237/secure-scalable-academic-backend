from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import cv2
import numpy as np
import joblib
import pickle
from django.conf import settings
import os
import logging
from pathlib import Path
import face_recognition
from .face_utils import FaceProcessor

logger = logging.getLogger(__name__)

class FaceRecognitionAPI(APIView):
    """API endpoint for face recognition."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.face_processor = FaceProcessor()
        self.model = None
        self.label_encoder = None
        self._load_model()
    
    def _load_model(self):
        """Load the trained model and label encoder."""
        try:
            model_dir = Path("ml_models")
            
            # Load SVM model
            model_path = model_dir / "svm_face_classifier.pkl"
            if not model_path.exists():
                logger.error(f"Model file not found: {model_path}")
                return False
                
            self.model = joblib.load(str(model_path))
            
            # Load label encoder
            encoder_path = model_dir / "label_encoder.pkl"
            if not encoder_path.exists():
                logger.error(f"Label encoder file not found: {encoder_path}")
                return False
                
            with open(encoder_path, 'rb') as f:
                self.label_encoder = pickle.load(f)
                
            logger.info("Successfully loaded face recognition model")
            return True
            
        except Exception as e:
            logger.error(f"Error loading model: {e}")
            return False
    
    def post(self, request):
        """Handle face recognition request.
        Handle face recognition request.
        
        Expected request format:
        {
            "image": base64_encoded_image
        }
        """
        try:
            # Check if model is loaded
            if not self.model or not self.label_encoder:
                return Response(
                    {"error": "Face recognition model not loaded"}, 
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Get image from request
            if 'image' not in request.data:
                return Response(
                    {"error": "No image provided"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Convert base64 to OpenCV image
            try:
                import base64
                from django.core.files.base import ContentFile
                
                # Get base64 data
                image_data = request.data['image']
                if 'base64,' in image_data:
                    # Handle data URL format
                    image_data = image_data.split('base64,')[1]
                
                # Decode base64
                image_data = base64.b64decode(image_data)
                
                # Convert to numpy array
                nparr = np.frombuffer(image_data, np.uint8)
                image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if image is None:
                    raise ValueError("Could not decode image")
                    
            except Exception as e:
                logger.error(f"Error processing image: {e}")
                return Response(
                    {"error": "Invalid image format"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Enhance image
            enhanced = enhance_image(image)
            
            # # Detect faces
            # faces = self.face_processor.detect_faces(enhanced)
            faces = self.face_processor.detect_faces(image)

            
            if not faces:
                return Response({
                    "detected_faces": 0,
                    "recognized_faces": []
                })
            
            # Process each face
            results = []
            for face in faces:
                try:
                    # Get face bounding box
                    x, y, w, h = face['box']
                    x, y = max(0, x), max(0, y)  # Ensure coordinates are not negative
                    
                    # Extract face ROI
                    face_roi = enhanced[y:y+h, x:x+w]
                    
                    # Skip if face is too small
                    if face_roi.size == 0 or face_roi.shape[0] < 50 or face_roi.shape[1] < 50:
                        continue
                    
                    # Align face
                    aligned_face = self.face_processor.align_face(enhanced, (x, y, w, h))
                    
                    if aligned_face is None:
                        continue
                    
                    # Get face encoding
                    encoding = self.face_processor.get_face_encoding(aligned_face)
                    
                    if encoding is not None:
                        # Predict with SVM
                        prediction = self.model.predict_proba([encoding])
                        max_prob = np.max(prediction)
                        
                        # Only accept predictions with sufficient confidence
                        if max_prob > 0.6:  # Adjust threshold as needed
                            predicted_label = self.model.predict([encoding])[0]
                            student_id = self.label_encoder.inverse_transform([predicted_label])[0]
                            
                            results.append({
                                "student_id": student_id,
                                "confidence": float(max_prob),
                                "bounding_box": {
                                    "x": int(x),
                                    "y": int(y),
                                    "width": int(w),
                                    "height": int(h)
                                }
                            })
                            
                except Exception as e:
                    logger.error(f"Error processing face: {e}")
                    continue
            
            return Response({
                "detected_faces": len(faces),
                "recognized_faces": results
            })
            
        except Exception as e:
            logger.error(f"Unexpected error in face recognition: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class FaceRegistrationAPI(APIView):
    """API endpoint for registering new faces."""
    
    def post(self, request):
        """
        Register a new face.
        
        Expected request format:
        {
            "student_id": "student123",
            "images": [base64_encoded_image1, base64_encoded_image2, ...]
        }
        """
        try:
            student_id = request.data.get('student_id')
            images_data = request.data.get('images', [])
            
            if not student_id or not isinstance(images_data, list) or len(images_data) < 3:
                return Response(
                    {"error": "student_id and at least 3 images are required"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create student directory if it doesn't exist
            student_dir = Path("dataset") / str(student_id)
            student_dir.mkdir(parents=True, exist_ok=True)
            
            # Save each image
            saved_count = 0
            for i, img_data in enumerate(images_data):
                try:
                    # Skip if not a string
                    if not isinstance(img_data, str):
                        continue
                        
                    # Handle data URL format
                    if 'base64,' in img_data:
                        img_data = img_data.split('base64,')[1]
                    
                    # Decode base64
                    image_data = base64.b64decode(img_data)
                    
                    # Convert to OpenCV image
                    nparr = np.frombuffer(image_data, np.uint8)
                    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if image is None:
                        continue
                    
                    # Save image
                    img_path = student_dir / f"{student_id}_{i+1}.jpg"
                    cv2.imwrite(str(img_path), image)
                    saved_count += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing image {i+1}: {e}")
                    continue
            
            if saved_count == 0:
                return Response(
                    {"error": "Could not process any of the provided images"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response({
                "status": "success",
                "saved_images": saved_count,
                "student_id": student_id
            })
            
        except Exception as e:
            logger.error(f"Error in face registration: {e}", exc_info=True)
            return Response(
                {"error": "Internal server error"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
