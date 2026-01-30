"""
Enhanced Face Recognition Engine with OpenCV Integration
Production-ready facial recognition system for attendance management
"""

import cv2
import numpy as np
import face_recognition
import pickle
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
import base64
from io import BytesIO
from PIL import Image
import threading
import time

from .models import Attendance, AttendanceDetection, CourseRegistration
from students.models import Student, StudentPhoto
from courses.models import ClassSession, TimetableSlot
from .presence_tracking_service import presence_tracking_service

logger = logging.getLogger(__name__)

class EnhancedFaceRecognitionEngine:
    """
    Production-ready face recognition engine with OpenCV and face_recognition library
    """
    
    def __init__(self):
        self.model_path = os.path.join(settings.BASE_DIR, 'ml_models')
        self.face_encodings_file = os.path.join(self.model_path, 'face_encodings.pkl')
        self.student_labels_file = os.path.join(self.model_path, 'student_labels.pkl')
        self.config_file = os.path.join(self.model_path, 'face_config.json')
        
        # Recognition parameters
        self.confidence_threshold = 0.6
        self.face_distance_threshold = 0.6
        self.detection_interval = 30  # seconds
        self.max_faces_per_frame = 10
        
        # Model state
        self.known_face_encodings = []
        self.known_student_ids = []
        self.student_id_to_info = {}
        self.model_loaded = False
        self.last_model_update = None
        
        # Performance tracking
        self.processing_stats = {
            'total_processed': 0,
            'successful_recognitions': 0,
            'failed_recognitions': 0,
            'avg_processing_time': 0.0,
            'last_reset': timezone.now()
        }
        
        # Thread safety
        self._lock = threading.Lock()
        
        # Initialize
        self._ensure_model_directory()
        self._load_configuration()
        self.load_models()
    
    def _ensure_model_directory(self):
        """Ensure model directory exists"""
        os.makedirs(self.model_path, exist_ok=True)
    
    def _load_configuration(self):
        """Load face recognition configuration"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.confidence_threshold = config.get('confidence_threshold', 0.6)
                    self.face_distance_threshold = config.get('face_distance_threshold', 0.6)
                    self.detection_interval = config.get('detection_interval', 30)
                    self.max_faces_per_frame = config.get('max_faces_per_frame', 10)
                    logger.info("Face recognition configuration loaded")
        except Exception as e:
            logger.warning(f"Could not load face recognition config: {e}")
    
    def save_configuration(self):
        """Save current configuration to file"""
        try:
            config = {
                'confidence_threshold': self.confidence_threshold,
                'face_distance_threshold': self.face_distance_threshold,
                'detection_interval': self.detection_interval,
                'max_faces_per_frame': self.max_faces_per_frame,
                'last_updated': timezone.now().isoformat()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            logger.info("Face recognition configuration saved")
        except Exception as e:
            logger.error(f"Could not save face recognition config: {e}")
    
    def load_models(self) -> Dict[str, Any]:
        """Load face recognition models and encodings"""
        try:
            with self._lock:
                if not os.path.exists(self.face_encodings_file) or not os.path.exists(self.student_labels_file):
                    logger.warning("Face recognition models not found. Please train models first.")
                    return {
                        'success': False,
                        'message': 'Models not found. Please train models first.',
                        'model_loaded': False
                    }
                
                # Load face encodings
                with open(self.face_encodings_file, 'rb') as f:
                    self.known_face_encodings = pickle.load(f)
                
                # Load student labels
                with open(self.student_labels_file, 'rb') as f:
                    self.known_student_ids = pickle.load(f)
                
                # Build student info mapping
                self._build_student_info_mapping()
                
                self.model_loaded = True
                self.last_model_update = timezone.now()
                
                logger.info(f"Face recognition models loaded successfully. "
                           f"Students: {len(self.known_student_ids)}, "
                           f"Encodings: {len(self.known_face_encodings)}")
                
                return {
                    'success': True,
                    'message': f'Models loaded successfully. {len(self.known_student_ids)} students registered.',
                    'model_loaded': True,
                    'student_count': len(self.known_student_ids),
                    'encoding_count': len(self.known_face_encodings)
                }
                
        except Exception as e:
            logger.error(f"Error loading face recognition models: {e}")
            self.model_loaded = False
            return {
                'success': False,
                'message': f'Error loading models: {str(e)}',
                'model_loaded': False
            }
    
    def _build_student_info_mapping(self):
        """Build mapping of student IDs to student information"""
        try:
            students = Student.objects.filter(
                id__in=self.known_student_ids,
                is_active=True,
                is_approved=True
            ).select_related('user')
            
            self.student_id_to_info = {}
            for student in students:
                self.student_id_to_info[student.id] = {
                    'matric_number': student.matric_number,
                    'full_name': student.full_name,
                    'department_id': student.department_id,
                    'user_id': student.user_id,
                    'face_consent_given': student.face_consent_given
                }
                
        except Exception as e:
            logger.error(f"Error building student info mapping: {e}")
    
    def train_models(self, force_retrain: bool = False) -> Dict[str, Any]:
        """Train face recognition models with all available student photos"""
        try:
            logger.info("Starting face recognition model training...")
            
            # Get all active students with face consent
            students = Student.objects.filter(
                is_active=True,
                is_approved=True,
                face_consent_given=True
            ).prefetch_related('photos')
            
            if not students.exists():
                return {
                    'success': False,
                    'message': 'No students with face consent found for training',
                    'student_count': 0
                }
            
            face_encodings = []
            student_ids = []
            processed_students = []
            failed_students = []
            
            for student in students:
                try:
                    student_encodings = self._process_student_photos(student)
                    if student_encodings:
                        face_encodings.extend(student_encodings)
                        student_ids.extend([student.id] * len(student_encodings))
                        processed_students.append({
                            'student_id': student.id,
                            'matric_number': student.matric_number,
                            'full_name': student.full_name,
                            'encoding_count': len(student_encodings)
                        })
                        logger.info(f"Processed {len(student_encodings)} encodings for {student.matric_number}")
                    else:
                        failed_students.append({
                            'student_id': student.id,
                            'matric_number': student.matric_number,
                            'reason': 'No valid face encodings generated'
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing student {student.matric_number}: {e}")
                    failed_students.append({
                        'student_id': student.id,
                        'matric_number': student.matric_number,
                        'reason': str(e)
                    })
            
            if not face_encodings:
                return {
                    'success': False,
                    'message': 'No valid face encodings generated from student photos',
                    'processed_students': processed_students,
                    'failed_students': failed_students
                }
            
            # Save encodings and labels
            with self._lock:
                with open(self.face_encodings_file, 'wb') as f:
                    pickle.dump(face_encodings, f)
                
                with open(self.student_labels_file, 'wb') as f:
                    pickle.dump(student_ids, f)
                
                # Update in-memory models
                self.known_face_encodings = face_encodings
                self.known_student_ids = student_ids
                self._build_student_info_mapping()
                self.model_loaded = True
                self.last_model_update = timezone.now()
            
            # Update student face_trained status
            Student.objects.filter(
                id__in=[s['student_id'] for s in processed_students]
            ).update(face_trained=True)
            
            logger.info(f"Face recognition training completed. "
                       f"Processed: {len(processed_students)}, "
                       f"Failed: {len(failed_students)}, "
                       f"Total encodings: {len(face_encodings)}")
            
            return {
                'success': True,
                'message': f'Training completed successfully. {len(processed_students)} students processed.',
                'student_count': len(processed_students),
                'total_encodings': len(face_encodings),
                'processed_students': processed_students,
                'failed_students': failed_students
            }
            
        except Exception as e:
            logger.error(f"Error training face recognition models: {e}")
            return {
                'success': False,
                'message': f'Training failed: {str(e)}',
                'error': str(e)
            }
    
    def _process_student_photos(self, student: Student) -> List[np.ndarray]:
        """Process all photos for a student and generate face encodings"""
        encodings = []
        
        photos = student.photos.all()
        if not photos.exists():
            logger.warning(f"No photos found for student {student.matric_number}")
            return encodings
        
        for photo in photos:
            try:
                if not photo.image or not os.path.exists(photo.image.path):
                    continue
                
                # Load and process image
                image = face_recognition.load_image_file(photo.image.path)
                
                # Find face locations
                face_locations = face_recognition.face_locations(image, model="hog")
                
                if not face_locations:
                    logger.warning(f"No faces found in photo {photo.id} for student {student.matric_number}")
                    continue
                
                # Generate encodings for all faces (usually just one per photo)
                face_encodings = face_recognition.face_encodings(image, face_locations)
                
                for encoding in face_encodings:
                    encodings.append(encoding)
                
                # Update photo quality score
                if face_encodings:
                    photo.quality_score = len(face_encodings) / len(face_locations)
                    photo.save()
                
            except Exception as e:
                logger.error(f"Error processing photo {photo.id} for student {student.matric_number}: {e}")
                continue
        
        return encodings
    
    def process_frame(self, frame_data: str, session_id: Optional[str] = None, 
                     department_id: Optional[str] = None) -> Dict[str, Any]:
        """Process a single frame for face recognition"""
        start_time = time.time()
        
        try:
            if not self.model_loaded:
                return {
                    'success': False,
                    'message': 'Face recognition models not loaded',
                    'recognized_students': [],
                    'unknown_faces': 0
                }
            
            # Decode frame data
            image = self._decode_frame_data(frame_data)
            if image is None:
                return {
                    'success': False,
                    'message': 'Invalid frame data',
                    'recognized_students': [],
                    'unknown_faces': 0
                }
            
            # Find faces in the frame
            face_locations = face_recognition.face_locations(image, model="hog")
            
            if not face_locations:
                return {
                    'success': True,
                    'message': 'No faces detected in frame',
                    'recognized_students': [],
                    'unknown_faces': 0,
                    'processing_time': time.time() - start_time
                }
            
            # Limit number of faces processed
            if len(face_locations) > self.max_faces_per_frame:
                face_locations = face_locations[:self.max_faces_per_frame]
            
            # Generate encodings for detected faces
            face_encodings = face_recognition.face_encodings(image, face_locations)
            
            recognized_students = []
            unknown_faces = 0
            
            # Process each face
            for i, face_encoding in enumerate(face_encodings):
                recognition_result = self._recognize_face(face_encoding, face_locations[i])
                
                if recognition_result['recognized']:
                    student_info = recognition_result['student_info']
                    
                    # Record attendance if this is a valid session
                    if session_id or department_id:
                        self._record_attendance(
                            student_info, 
                            recognition_result['confidence'],
                            session_id,
                            department_id
                        )
                    
                    recognized_students.append({
                        'student_id': student_info['student_id'],
                        'matric_number': student_info['matric_number'],
                        'full_name': student_info['full_name'],
                        'confidence': recognition_result['confidence'],
                        'face_location': face_locations[i],
                        'timestamp': timezone.now().isoformat()
                    })
                else:
                    unknown_faces += 1
            
            # Update processing stats
            self._update_processing_stats(time.time() - start_time, len(recognized_students))
            
            return {
                'success': True,
                'message': f'Processed {len(face_locations)} faces, recognized {len(recognized_students)} students',
                'recognized_students': recognized_students,
                'unknown_faces': unknown_faces,
                'total_faces': len(face_locations),
                'processing_time': time.time() - start_time
            }
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return {
                'success': False,
                'message': f'Frame processing error: {str(e)}',
                'recognized_students': [],
                'unknown_faces': 0,
                'error': str(e)
            }
    
    def _decode_frame_data(self, frame_data: str) -> Optional[np.ndarray]:
        """Decode base64 frame data to numpy array"""
        try:
            # Remove data URL prefix if present
            if frame_data.startswith('data:image'):
                frame_data = frame_data.split(',')[1]
            
            # Decode base64
            image_data = base64.b64decode(frame_data)
            
            # Convert to PIL Image
            pil_image = Image.open(BytesIO(image_data))
            
            # Convert to RGB (face_recognition expects RGB)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Convert to numpy array
            return np.array(pil_image)
            
        except Exception as e:
            logger.error(f"Error decoding frame data: {e}")
            return None
    
    def _recognize_face(self, face_encoding: np.ndarray, face_location: Tuple) -> Dict[str, Any]:
        """Recognize a single face encoding"""
        try:
            if not self.known_face_encodings:
                return {'recognized': False, 'confidence': 0.0}
            
            # Compare with known faces
            face_distances = face_recognition.face_distance(self.known_face_encodings, face_encoding)
            
            # Find best match
            best_match_index = np.argmin(face_distances)
            best_distance = face_distances[best_match_index]
            
            # Check if match is good enough
            if best_distance <= self.face_distance_threshold:
                student_id = self.known_student_ids[best_match_index]
                confidence = 1.0 - best_distance  # Convert distance to confidence
                
                if student_id in self.student_id_to_info:
                    student_info = self.student_id_to_info[student_id].copy()
                    student_info['student_id'] = student_id
                    
                    return {
                        'recognized': True,
                        'student_info': student_info,
                        'confidence': confidence,
                        'face_distance': best_distance
                    }
            
            return {'recognized': False, 'confidence': 0.0, 'face_distance': best_distance}
            
        except Exception as e:
            logger.error(f"Error recognizing face: {e}")
            return {'recognized': False, 'confidence': 0.0, 'error': str(e)}
    
    def _record_attendance(self, student_info: Dict, confidence: float, 
                          session_id: Optional[str], department_id: Optional[str]):
        """Record attendance for recognized student"""
        try:
            student_id = student_info['student_id']
            student = Student.objects.get(id=student_id)
            
            # Get current active class sessions for this student
            current_sessions = self._get_current_class_sessions(student, department_id)
            
            for session_info in current_sessions:
                course_registration = session_info['course_registration']
                class_session = session_info.get('class_session')
                
                # Get or create attendance record
                attendance = presence_tracking_service.start_presence_tracking(
                    student=student,
                    course_registration=course_registration,
                    timetable_entry=session_info.get('timetable_entry')
                )
                
                # Record presence detection
                presence_tracking_service.record_presence_detection(attendance)
                
                # Create detailed detection record
                AttendanceDetection.objects.create(
                    attendance=attendance,
                    confidence_score=confidence,
                    session_context={
                        'session_id': session_id,
                        'department_id': department_id,
                        'recognition_method': 'face_recognition'
                    }
                )
                
                logger.debug(f"Recorded attendance for {student_info['matric_number']} "
                           f"in {course_registration.course.code}")
                
        except Exception as e:
            logger.error(f"Error recording attendance: {e}")
    
    def _get_current_class_sessions(self, student: Student, department_id: Optional[str]) -> List[Dict]:
        """Get current active class sessions for a student"""
        try:
            now = timezone.now()
            current_day = now.strftime('%a').upper()[:3]  # MON, TUE, etc.
            current_time = now.time()
            
            # Get student's course registrations
            registrations = CourseRegistration.objects.filter(
                student=student,
                status__in=['approved', 'auto_approved']
            ).select_related('course', 'semester')
            
            current_sessions = []
            
            for registration in registrations:
                # Find active timetable slots for this course
                from courses.models import TimetableSlot
                active_slots = TimetableSlot.objects.filter(
                    course=registration.course,
                    day_of_week=current_day,
                    start_time__lte=current_time,
                    end_time__gte=current_time
                ).select_related('timetable')
                
                if department_id:
                    active_slots = active_slots.filter(timetable__department_id=department_id)
                
                for slot in active_slots:
                    # Check if there's an active class session
                    try:
                        class_session = ClassSession.objects.get(
                            timetable_slot=slot,
                            date=now.date(),
                            state='active'
                        )
                        
                        current_sessions.append({
                            'course_registration': registration,
                            'class_session': class_session,
                            'timetable_slot': slot
                        })
                        
                    except ClassSession.DoesNotExist:
                        # No active session, but still record for timetable entry
                        current_sessions.append({
                            'course_registration': registration,
                            'timetable_slot': slot
                        })
            
            return current_sessions
            
        except Exception as e:
            logger.error(f"Error getting current class sessions: {e}")
            return []
    
    def _update_processing_stats(self, processing_time: float, recognized_count: int):
        """Update processing statistics"""
        try:
            self.processing_stats['total_processed'] += 1
            self.processing_stats['successful_recognitions'] += recognized_count
            
            # Update average processing time
            current_avg = self.processing_stats['avg_processing_time']
            total_processed = self.processing_stats['total_processed']
            self.processing_stats['avg_processing_time'] = (
                (current_avg * (total_processed - 1) + processing_time) / total_processed
            )
            
        except Exception as e:
            logger.error(f"Error updating processing stats: {e}")
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get current model status and statistics"""
        return {
            'model_loaded': self.model_loaded,
            'student_count': len(self.known_student_ids),
            'encoding_count': len(self.known_face_encodings),
            'last_model_update': self.last_model_update.isoformat() if self.last_model_update else None,
            'configuration': {
                'confidence_threshold': self.confidence_threshold,
                'face_distance_threshold': self.face_distance_threshold,
                'detection_interval': self.detection_interval,
                'max_faces_per_frame': self.max_faces_per_frame
            },
            'processing_stats': self.processing_stats.copy(),
            'model_files_exist': {
                'face_encodings': os.path.exists(self.face_encodings_file),
                'student_labels': os.path.exists(self.student_labels_file),
                'config': os.path.exists(self.config_file)
            }
        }
    
    def update_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update face recognition configuration"""
        try:
            if 'confidence_threshold' in config:
                self.confidence_threshold = float(config['confidence_threshold'])
            
            if 'face_distance_threshold' in config:
                self.face_distance_threshold = float(config['face_distance_threshold'])
            
            if 'detection_interval' in config:
                self.detection_interval = int(config['detection_interval'])
            
            if 'max_faces_per_frame' in config:
                self.max_faces_per_frame = int(config['max_faces_per_frame'])
            
            # Save configuration
            self.save_configuration()
            
            return {
                'success': True,
                'message': 'Configuration updated successfully',
                'configuration': {
                    'confidence_threshold': self.confidence_threshold,
                    'face_distance_threshold': self.face_distance_threshold,
                    'detection_interval': self.detection_interval,
                    'max_faces_per_frame': self.max_faces_per_frame
                }
            }
            
        except Exception as e:
            logger.error(f"Error updating configuration: {e}")
            return {
                'success': False,
                'message': f'Configuration update failed: {str(e)}',
                'error': str(e)
            }
    
    def reset_processing_stats(self):
        """Reset processing statistics"""
        self.processing_stats = {
            'total_processed': 0,
            'successful_recognitions': 0,
            'failed_recognitions': 0,
            'avg_processing_time': 0.0,
            'last_reset': timezone.now()
        }


# Global enhanced face recognition engine instance
enhanced_face_recognition_engine = EnhancedFaceRecognitionEngine()