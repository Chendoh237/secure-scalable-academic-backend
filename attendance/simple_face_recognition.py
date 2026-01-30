#!/usr/bin/env python3
"""
Simple Face Recognition Service - Based on working implementation
Integrates with Django models and timetable system
"""

import cv2
import pickle
import numpy as np
import base64
import io
from datetime import datetime, date
from pathlib import Path
from PIL import Image
import logging
import csv

# Django imports
from django.conf import settings
from django.utils import timezone
from students.models import Student, StudentCourseSelection
from attendance.models import Attendance, CourseRegistration
from courses.models import TimetableSlot
from live_sessions.models import LiveSession, LiveSessionParticipant

logger = logging.getLogger(__name__)

from .face_config import face_config

class SimpleFaceRecognitionService:
    def __init__(self):
        self.model_dir = Path(settings.BASE_DIR) / "ml_models"
        self.model_file = self.model_dir / "face_trainer.yml"
        self.labels_file = self.model_dir / "labels.pkl"
        self.cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        
        # Load dynamic configuration
        self.config = face_config.get_optimized_config()
        
        # Your proven parameters (now dynamic)
        self.IMG_SIZE = self.config["img_size"]
        self.CONFIDENCE_THRESHOLD = self.config["confidence_threshold"]
        self.SCALE_FACTOR = self.config["scale_factor"]
        self.MIN_NEIGHBORS = self.config["min_neighbors"]
        self.MAX_FACES_PER_FRAME = self.config["max_faces_per_frame"]
        
        # Initialize components
        self.recognizer = None
        self.label_map = {}
        self.id_to_matric = {}
        self.face_cascade = None
        
        # Daily attendance tracking (like your logged_today)
        self.logged_today = {}
        
        self._load_models()
    
    def reload_config(self):
        """Reload configuration and update parameters"""
        self.config = face_config.get_optimized_config()
        self.IMG_SIZE = self.config["img_size"]
        self.CONFIDENCE_THRESHOLD = self.config["confidence_threshold"]
        self.SCALE_FACTOR = self.config["scale_factor"]
        self.MIN_NEIGHBORS = self.config["min_neighbors"]
        self.MAX_FACES_PER_FRAME = self.config["max_faces_per_frame"]
        logger.info(f"Configuration reloaded for {self.config['student_count']} students")
    
    def _load_models(self):
        """Load face recognition models using your proven approach"""
        try:
            # Create recognizer
            self.recognizer = cv2.face.LBPHFaceRecognizer_create()
            
            if not self.model_file.exists():
                logger.error(f"Model file not found: {self.model_file}")
                raise FileNotFoundError("Face recognition model not found. Please train the model first.")
            
            self.recognizer.read(str(self.model_file))
            logger.info("Simple face recognition model loaded successfully")
            
            # Load label mappings
            if not self.labels_file.exists():
                logger.error(f"Labels file not found: {self.labels_file}")
                raise FileNotFoundError("Labels file not found. Please train the model first.")
            
            with open(self.labels_file, "rb") as f:
                self.label_map = pickle.load(f)
            
            # Create reverse mapping (label_id -> matric_number)
            self.id_to_matric = {v: k for k, v in self.label_map.items()}
            
            logger.info(f"Loaded {len(self.label_map)} student labels")
            logger.info(f"Label mappings: {self.label_map}")
            
            # Load face cascade
            self.face_cascade = cv2.CascadeClassifier(self.cascade_path)
            if self.face_cascade.empty():
                raise FileNotFoundError("Face cascade classifier not found")
            
            logger.info("Simple face recognition service initialized successfully")
            logger.info(f"Using configuration: {self.config}")
            
        except Exception as e:
            logger.error(f"Failed to load face recognition models: {e}")
            raise
    
    def _mark_attendance(self, matric_number, course_code=None, timetable_slot_id=None):
        """Mark attendance using existing database approach"""
        today = timezone.now().date()
        
        # Check if already logged today
        cache_key = f"{matric_number}_{course_code or 'general'}"
        last_logged = self.logged_today.get(cache_key)
        if last_logged == today:
            return {
                'success': False,
                'message': f'Already marked today for {matric_number}',
                'already_marked': True
            }
        
        timestamp = timezone.now()
        
        try:
            # Get student
            student = Student.objects.get(matric_number=matric_number)
            
            # Write to database using existing approach
            if course_code:
                # Find course registration
                course_registration = CourseRegistration.objects.filter(
                    student=student,
                    course__code=course_code
                ).first()
                
                if not course_registration:
                    # Create basic course registration if needed
                    from courses.models import Course
                    course = Course.objects.filter(code=course_code).first()
                    if course:
                        course_registration = CourseRegistration.objects.create(
                            student=student,
                            course=course,
                            academic_year='2025/2026',
                            semester='Semester 1'
                        )
            else:
                # General attendance - use first available course registration
                course_registration = CourseRegistration.objects.filter(student=student).first()
            
            if course_registration:
                # Check if attendance already exists
                existing_attendance = Attendance.objects.filter(
                    student=student,
                    course_registration=course_registration,
                    date=today
                ).first()
                
                if not existing_attendance:
                    Attendance.objects.create(
                        student=student,
                        course_registration=course_registration,
                        date=today,
                        status='present',
                        recorded_at=timestamp,
                        is_manual_override=False
                    )
            
            # Update cache
            self.logged_today[cache_key] = today
            
            logger.info(f"[{timestamp.strftime('%Y-%m-%d %H:%M:%S')}] MARKED: {matric_number} ({student.full_name})")
            
            return {
                'success': True,
                'message': f'Attendance marked for {student.full_name}',
                'student_name': student.full_name,
                'timestamp': timestamp.isoformat()
            }
            
        except Student.DoesNotExist:
            logger.warning(f"Student not found: {matric_number}")
            return {
                'success': False,
                'message': f'Student {matric_number} not found in database'
            }
        except Exception as e:
            logger.error(f"Error marking attendance for {matric_number}: {e}")
            return {
                'success': False,
                'message': str(e)
            }
    
    def get_current_timetable_slots(self):
        """Get current active timetable slots"""
        now = timezone.now()
        current_day = now.strftime('%a').upper()
        current_time = now.time()
        
        day_mapping = {
            'MON': 'MON', 'TUE': 'TUE', 'WED': 'WED', 
            'THU': 'THU', 'FRI': 'FRI', 'SAT': 'SAT', 'SUN': 'SUN'
        }
        
        day_code = day_mapping.get(current_day, current_day)
        
        active_slots = TimetableSlot.objects.filter(
            day_of_week=day_code,
            start_time__lte=current_time,
            end_time__gte=current_time
        ).select_related('course', 'level', 'timetable__department', 'lecturer')
        
        return active_slots
    
    def get_students_for_timetable_slot(self, timetable_slot):
        """Get students expected for a timetable slot"""
        return Student.objects.filter(
            course_selections__course=timetable_slot.course,
            course_selections__level=timetable_slot.level,
            course_selections__is_offered=True,
            course_selections__is_approved=True,
            department=timetable_slot.timetable.department,
            is_active=True,
            is_approved=True
        ).distinct()
    
    def process_frame(self, frame_data, session_id=None, department_id=None):
        """Process frame using your proven recognition approach"""
        try:
            # Convert frame data to OpenCV format
            if isinstance(frame_data, str):
                image_data = base64.b64decode(frame_data.split(',')[1])
                image = Image.open(io.BytesIO(image_data))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            else:
                frame = frame_data
            
            # Convert to grayscale (your approach)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Detect faces using your proven parameters
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=self.SCALE_FACTOR,
                minNeighbors=self.MIN_NEIGHBORS
            )
            
            # Limit faces for performance with 30+ users
            if len(faces) > self.MAX_FACES_PER_FRAME:
                # Sort by face size (larger faces first)
                faces_with_size = [(face, face[2] * face[3]) for face in faces]
                faces_with_size.sort(key=lambda x: x[1], reverse=True)
                faces = [face[0] for face in faces_with_size[:self.MAX_FACES_PER_FRAME]]
            
            # Get current timetable information
            active_slots = self.get_current_timetable_slots()
            if department_id:
                active_slots = active_slots.filter(timetable__department_id=department_id)
            
            results = {
                'timestamp': timezone.now().isoformat(),
                'faces_detected': len(faces),
                'recognized_students': [],
                'unrecognized_faces': [],
                'face_boxes': [],
                'active_timetable_slots': [],
                'expected_students': []
            }
            
            # Add timetable information
            for slot in active_slots:
                expected_students = self.get_students_for_timetable_slot(slot)
                slot_info = {
                    'id': slot.id,
                    'course_code': slot.course.code,
                    'course_title': slot.course.title,
                    'level': slot.level.name,
                    'department': slot.timetable.department.name,
                    'lecturer': slot.lecturer.user.get_full_name(),
                    'time_slot': f"{slot.start_time} - {slot.end_time}",
                    'venue': slot.venue,
                    'expected_students_count': expected_students.count()
                }
                results['active_timetable_slots'].append(slot_info)
                
                # Add expected students
                for student in expected_students:
                    if student.matric_number not in [s['matric_number'] for s in results['expected_students']]:
                        results['expected_students'].append({
                            'student_id': student.id,
                            'matric_number': student.matric_number,
                            'full_name': student.full_name,
                            'course_code': slot.course.code,
                            'level': slot.level.name
                        })
            
            # Process each detected face
            for i, (x, y, w, h) in enumerate(faces):
                # Extract and resize face ROI (your approach)
                roi = gray[y:y+h, x:x+w]
                roi_resized = cv2.resize(roi, self.IMG_SIZE)
                
                # Predict using your proven approach
                label_id, confidence = self.recognizer.predict(roi_resized)
                
                face_info = {
                    'box': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                    'confidence': float(confidence),
                    'face_index': i
                }
                
                # Check confidence using your proven threshold
                if confidence < self.CONFIDENCE_THRESHOLD:
                    matric_number = self.id_to_matric.get(label_id, "Unknown")
                    
                    if matric_number != "Unknown":
                        try:
                            student = Student.objects.get(matric_number=matric_number)
                            
                            # Check if student is expected in current timetable
                            is_expected = any(
                                student in self.get_students_for_timetable_slot(slot) 
                                for slot in active_slots
                            )
                            
                            face_info.update({
                                'recognized': True,
                                'student_id': student.id,
                                'matric_number': matric_number,
                                'full_name': student.full_name,
                                'status': 'expected' if is_expected else 'recognized_but_not_expected',
                                'is_expected': is_expected
                            })
                            
                            # Mark attendance for active slots
                            attendance_results = []
                            for slot in active_slots:
                                if student in self.get_students_for_timetable_slot(slot):
                                    result = self._mark_attendance(
                                        matric_number, 
                                        slot.course.code, 
                                        slot.id
                                    )
                                    attendance_results.append(result)
                            
                            # Add to recognized students (avoid duplicates)
                            existing = next(
                                (s for s in results['recognized_students'] 
                                 if s['matric_number'] == matric_number), None
                            )
                            
                            if not existing:
                                results['recognized_students'].append({
                                    'student_id': student.id,
                                    'matric_number': matric_number,
                                    'full_name': student.full_name,
                                    'confidence': confidence,
                                    'timestamp': timezone.now().isoformat(),
                                    'is_expected': is_expected,
                                    'attendance_marked': len(attendance_results) > 0
                                })
                            
                            logger.info(f"✅ Recognized: {student.full_name} ({matric_number}) - Confidence: {confidence:.1f}")
                            
                        except Student.DoesNotExist:
                            face_info.update({
                                'recognized': False,
                                'full_name': f'Unknown Student ({matric_number})',
                                'status': 'not_found_in_db'
                            })
                            results['unrecognized_faces'].append(face_info)
                    else:
                        face_info.update({
                            'recognized': False,
                            'full_name': f'Unknown {label_id}',
                            'status': 'unknown_label'
                        })
                        results['unrecognized_faces'].append(face_info)
                else:
                    # Low confidence
                    face_info.update({
                        'recognized': False,
                        'full_name': f'Low Confidence ({confidence:.1f})',
                        'status': 'low_confidence'
                    })
                    results['unrecognized_faces'].append(face_info)
                
                results['face_boxes'].append(face_info)
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing frame: {e}")
            return {
                'error': str(e),
                'timestamp': timezone.now().isoformat(),
                'faces_detected': 0,
                'recognized_students': [],
                'unrecognized_faces': [],
                'face_boxes': [],
                'active_timetable_slots': [],
                'expected_students': []
            }
    
    def get_model_status(self):
        """Get model status with configuration info"""
        return {
            'model_loaded': self.recognizer is not None,
            'labels_loaded': len(self.label_map) > 0,
            'cascade_loaded': self.face_cascade is not None and not self.face_cascade.empty(),
            'total_students': len(self.label_map),
            'model_file_exists': self.model_file.exists(),
            'labels_file_exists': self.labels_file.exists(),
            'configuration': self.config
        }
    
    def reload_models(self):
        """Reload models and configuration"""
        try:
            self.reload_config()
            self._load_models()
            return {'success': True, 'message': 'Models and configuration reloaded successfully'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

# Global service instance
simple_face_recognition_service = SimpleFaceRecognitionService()