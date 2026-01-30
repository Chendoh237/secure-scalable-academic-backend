import cv2
import numpy as np
import dlib
from imutils.face_utils import FaceAligner
from imutils.face_utils import rect_to_bb
import imutils
import logging
import os

logger = logging.getLogger(__name__)

class FaceProcessor:
    def __init__(self):
        # Define model paths
        self.models_dir = "ml_models"
        self.shape_predictor_path = os.path.join(self.models_dir, "shape_predictor_68_face_landmarks.dat")
        self.face_recognition_model_path = os.path.join(self.models_dir, "dlib_face_recognition_resnet_model_v1.dat")
        
        # Initialize dlib's face detector and shape predictor for alignment
        self.detector = dlib.get_frontal_face_detector()
        
        # Check if model files exist
        if not os.path.exists(self.shape_predictor_path):
            raise FileNotFoundError(
                f"Shape predictor model not found at {self.shape_predictor_path}.\n"
                "Please run 'python download_models.py' to download the required models."
            )
            
        self.predictor = dlib.shape_predictor(self.shape_predictor_path)
        self.face_aligner = FaceAligner(self.predictor, desiredFaceWidth=200)
        
        # Load face recognition model
        if not os.path.exists(self.face_recognition_model_path):
            raise FileNotFoundError(
                f"Face recognition model not found at {self.face_recognition_model_path}.\n"
                "Please run 'python download_models.py' to download the required models."
            )
        self.face_recognizer = dlib.face_recognition_model_v1(self.face_recognition_model_path)
        
        # Initialize OpenCV's DNN face detector as a fallback
        self.dnn_prototxt = os.path.join(self.models_dir, "deploy.prototxt")
        self.dnn_model = os.path.join(self.models_dir, "res10_300x300_ssd_iter_140000.caffemodel")
        if os.path.exists(self.dnn_prototxt) and os.path.exists(self.dnn_model):
            self.dnn_net = cv2.dnn.readNetFromCaffe(self.dnn_prototxt, self.dnn_model)
        else:
            logger.warning("DNN model files not found. Some features may not work.")
            self.dnn_net = None

    def detect_faces(self, image):
        """Detect faces in an image using dlib with OpenCV DNN fallback."""
        try:
            # First try dlib
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self.detector(gray, 1)
            
            if not faces and self.dnn_net is not None:
                # Fall back to OpenCV DNN if no faces found with dlib
                return self._detect_faces_dnn(image)
                
            # Convert dlib rectangles to consistent format
            results = []
            for face in faces:
                (x, y, w, h) = rect_to_bb(face)
                results.append({
                    'box': [x, y, w, h],
                    'confidence': 1.0  # dlib doesn't provide confidence
                })
            return results
            
        except Exception as e:
            logger.error(f"Error in dlib face detection: {e}")
            if self.dnn_net is not None:
                return self._detect_faces_dnn(image)
            return []

    def _detect_faces_dnn(self, image):
        """Detect faces using OpenCV's DNN face detector."""
        try:
            (h, w) = image.shape[:2]
            blob = cv2.dnn.blobFromImage(
                cv2.resize(image, (300, 300)), 1.0,
                (300, 300), (104.0, 177.0, 123.0))
            
            self.dnn_net.setInput(blob)
            detections = self.dnn_net.forward()
            
            results = []
            for i in range(0, detections.shape[2]):
                confidence = detections[0, 0, i, 2]
                
                if confidence > 0.7:  # Confidence threshold
                    box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                    (startX, startY, endX, endY) = box.astype("int")
                    
                    # Ensure the bounding boxes fall within the dimensions of the frame
                    (startX, startY) = (max(0, startX), max(0, startY))
                    (endX, endY) = (min(w - 1, endX), min(h - 1, endY))
                    
                    results.append({
                        'box': [startX, startY, endX - startX, endY - startY],
                        'confidence': float(confidence)
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error in DNN face detection: {e}")
            return []

    def get_face_encodings(self, image, face_locations=None):
        """Get face encodings for all faces in the image."""
        if face_locations is None:
            face_locations = self.detect_faces(image)
            
        if not face_locations:
            return []
            
        # Convert the image from BGR to RGB (dlib uses RGB)
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        encodings = []
        for face in face_locations:
            # Convert to dlib rectangle
            (x, y, w, h) = face['box']
            rect = dlib.rectangle(left=x, top=y, right=x+w, bottom=y+h)
            
            # Get the face landmarks
            shape = self.predictor(rgb_image, rect)
            
            # Get the face encoding
            face_encoding = self.face_recognizer.compute_face_descriptor(rgb_image, shape)
            encodings.append(np.array(face_encoding))
            
        return encodings

    def compare_faces(self, known_encodings, face_encoding_to_check, tolerance=0.6):
        """Compare a face encoding to a list of known face encodings."""
        if not known_encodings:
            return []
            
        # Calculate face distances
        distances = np.linalg.norm(known_encodings - face_encoding_to_check, axis=1)
        return list(distances <= tolerance)