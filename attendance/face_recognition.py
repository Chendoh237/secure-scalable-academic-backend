#!/usr/bin/env python3
"""
Face Recognition Service for Real-time Attendance Tracking
Integrates with Django models, Timetables, and Student Course Selections
"""

import cv2
import pickle
import numpy as np
import base64
import io
from datetime import datetime, date, time
from pathlib import Path
from PIL import Image
import logging

# Django imports
from django.conf import settings
from django.utils import timezone
from students.models import Student, StudentCourseSelection, StudentLevelSelection
from attendance.models import Attendance, CourseRegistration
from courses.models import TimetableSlot, Timetable
from academics.models import Course
from live_sessions.models import LiveSession, LiveSessionParticipant

logger = logging.getLogger(__name__)

class FaceRecognitionService:
    def __init__(self):
        self.model_dir = Path(settings.BASE_DIR) / "ml_models"
        self.model_file = self.model_dir / "face_trainer.yml"
        self.labels_file = self.model_dir / "labels.pkl"
        self.cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        
        # Optimized parameters for 30+ users detection
        self.IMG_SIZE = (100, 100)  # Smaller for faster processing of many faces
        self.CONFIDENCE_THRESHOLD = 95  # More lenient for group detection
        self.MIN_FACE_SIZE = (20, 20)  # Very small for distant/small faces
        self.MAX_FACE_SIZE = (250, 250)  # Reasonable max for group photos
        
        # Group detection processing parameters
        self.MAX_FACES_PER_FRAME = 35  # Handle up to 35 faces simultaneously
        self.FACE_QUALITY_THRESHOLD = 0.15  # Very low threshold for group detection
        self.BATCH_PROCESSING_SIZE = 8  # Smaller batches for better performance
        
        # Initialize components
        self.recognizer = None
        self.label_map = {}
        self.id_to_matric = {}
        self.face_cascade = None
        self.profile_cascade = None  # For side profile detection
        
        # Performance tracking
        self.recognition_cache = {}  # Cache recent recognitions
        self.cache_timeout = 5  # seconds
        
        # Session tracking
        self.recognized_today = {}
        
        self._load_models()
    
    def _load_models(self):
        """Load face recognition models and cascade classifier"""
        try:
            # Load face recognizer with optimized parameters
            self.recognizer = cv2.face.LBPHFaceRecognizer_create(
                radius=2,        # Increased for better texture analysis
                neighbors=12,    # More neighbors for better accuracy
                grid_x=10,       # Higher grid resolution
                grid_y=10,
                threshold=self.CONFIDENCE_THRESHOLD
            )
            
            if not self.model_file.exists():
                logger.error(f"Model file not found: {self.model_file}")
                raise FileNotFoundError("Face recognition model not found. Please train the model first.")
            
            self.recognizer.read(str(self.model_file))
            logger.info("Enhanced face recognition model loaded successfully")
            
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
            
            # Load face cascades (frontal and profile)
            self.face_cascade = cv2.CascadeClassifier(self.cascade_path)
            if self.face_cascade.empty():
                raise FileNotFoundError("Face cascade classifier not found")
            
            # Load profile cascade for side faces
            profile_cascade_path = cv2.data.haarcascades + "haarcascade_profileface.xml"
            self.profile_cascade = cv2.CascadeClassifier(profile_cascade_path)
            
            logger.info("Enhanced face recognition service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to load face recognition models: {e}")
            raise
    
    def _calculate_face_quality(self, face_roi):
        """Calculate face quality score based on various factors"""
        if face_roi.size == 0:
            return 0.0
        
        # Calculate sharpness using Laplacian variance
        laplacian_var = cv2.Laplacian(face_roi, cv2.CV_64F).var()
        sharpness_score = min(laplacian_var / 1000.0, 1.0)  # Normalize
        
        # Calculate contrast
        contrast_score = face_roi.std() / 255.0
        
        # Calculate size score (prefer medium-sized faces)
        height, width = face_roi.shape
        size_score = min(width * height / (200 * 200), 1.0)
        
        # Combined quality score
        quality_score = (sharpness_score * 0.4 + contrast_score * 0.3 + size_score * 0.3)
        
        return quality_score
    
    def _preprocess_face(self, face_roi):
        """Enhanced face preprocessing optimized for poor lighting and distant faces"""
        # Multi-stage enhancement for challenging conditions
        
        # Stage 1: Gamma correction for poor lighting
        gamma_corrected = self._apply_gamma_correction(face_roi, gamma=1.3)
        
        # Stage 2: Aggressive CLAHE for local contrast
        clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(4, 4))
        enhanced = clahe.apply(gamma_corrected)
        
        # Stage 3: Bilateral filtering to reduce noise while preserving edges
        denoised = cv2.bilateralFilter(enhanced, 5, 50, 50)
        
        # Stage 4: Sharpening for distant faces
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(denoised, -1, kernel)
        
        # Stage 5: Normalize intensity
        normalized = cv2.normalize(sharpened, None, 0, 255, cv2.NORM_MINMAX)
        
        # Resize to standard size with high-quality interpolation
        resized = cv2.resize(normalized, self.IMG_SIZE, interpolation=cv2.INTER_CUBIC)
        
        return resized
    
    def _detect_faces_multi_scale(self, gray):
        """Enhanced face detection optimized for classroom conditions (50+ students, 3-5m distance, poor lighting)"""
        all_faces = []
        
        # Apply advanced preprocessing for poor lighting conditions
        # 1. Gamma correction for better visibility in poor lighting
        gamma_corrected = self._apply_gamma_correction(gray, gamma=1.5)
        
        # 2. Multi-level CLAHE for extreme contrast enhancement
        clahe_aggressive = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
        enhanced_contrast = clahe_aggressive.apply(gamma_corrected)
        
        # 3. Bilateral filter to reduce noise while preserving edges
        denoised = cv2.bilateralFilter(enhanced_contrast, 9, 75, 75)
        
        # Multiple detection passes with different parameters for classroom distance
        detection_configs = [
            # Configuration for distant faces (3-5 meters)
            {'scale': 1.03, 'neighbors': 3, 'image': denoised},
            {'scale': 1.05, 'neighbors': 4, 'image': enhanced_contrast},
            {'scale': 1.08, 'neighbors': 5, 'image': gamma_corrected},
            
            # Configuration for medium distance faces
            {'scale': 1.1, 'neighbors': 4, 'image': denoised},
            {'scale': 1.15, 'neighbors': 5, 'image': enhanced_contrast},
            
            # Configuration for closer faces (front rows)
            {'scale': 1.2, 'neighbors': 6, 'image': gray},
        ]
        
        for config in detection_configs:
            faces = self.face_cascade.detectMultiScale(
                config['image'],
                scaleFactor=config['scale'],
                minNeighbors=config['neighbors'],
                minSize=self.MIN_FACE_SIZE,
                maxSize=self.MAX_FACE_SIZE,
                flags=cv2.CASCADE_SCALE_IMAGE | cv2.CASCADE_DO_CANNY_PRUNING
            )
            all_faces.extend(faces)
        
        # Detect profile faces with enhanced parameters for classroom
        if self.profile_cascade and not self.profile_cascade.empty():
            for enhanced_img in [denoised, enhanced_contrast]:
                profile_faces = self.profile_cascade.detectMultiScale(
                    enhanced_img,
                    scaleFactor=1.05,
                    minNeighbors=3,  # Lower for distant profile faces
                    minSize=self.MIN_FACE_SIZE,
                    maxSize=self.MAX_FACE_SIZE
                )
                all_faces.extend(profile_faces)
        
        # Advanced Non-Maximum Suppression for classroom density
        if len(all_faces) > 0:
            faces_array = np.array(all_faces)
            
            # Convert to (x, y, x2, y2) format for NMS
            boxes = []
            scores = []
            for (x, y, w, h) in faces_array:
                boxes.append([x, y, x + w, y + h])
                # Calculate confidence score based on face size (larger = closer = higher confidence)
                size_score = (w * h) / (self.MAX_FACE_SIZE[0] * self.MAX_FACE_SIZE[1])
                scores.append(min(size_score * 2, 1.0))
            
            if len(boxes) > 0:
                boxes = np.array(boxes, dtype=np.float32)
                scores = np.array(scores, dtype=np.float32)
                
                # Aggressive NMS for dense classroom
                indices = cv2.dnn.NMSBoxes(
                    boxes.tolist(), 
                    scores.tolist(),
                    score_threshold=0.1,  # Lower threshold for distant faces
                    nms_threshold=0.2     # More aggressive overlap removal
                )
                
                if len(indices) > 0:
                    indices = indices.flatten()
                    filtered_faces = [all_faces[i] for i in indices]
                    
                    # Sort by face size (larger faces first - likely closer/clearer)
                    filtered_faces.sort(key=lambda face: face[2] * face[3], reverse=True)
                    
                    return filtered_faces[:self.MAX_FACES_PER_FRAME]
        
        return all_faces[:self.MAX_FACES_PER_FRAME]
    
    def _apply_gamma_correction(self, image, gamma=1.0):
        """Apply gamma correction for better visibility in poor lighting"""
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        return cv2.LUT(image, table)
    
    def _estimate_distance(self, face_width, face_height):
        """Estimate distance category based on face size"""
        face_area = face_width * face_height
        
        if face_area > 8000:  # Large face
            return "Close (1-2m)"
        elif face_area > 3000:  # Medium face
            return "Medium (2-4m)"
        elif face_area > 1000:  # Small face
            return "Far (4-6m)"
        else:  # Very small face
            return "Very Far (6m+)"
    
    def get_current_timetable_slots(self):
        """
        Get current active timetable slots based on current day and time
        
        Returns:
            QuerySet: Active timetable slots for current time
        """
        now = timezone.now()
        current_day = now.strftime('%a').upper()  # MON, TUE, etc.
        current_time = now.time()
        
        # Map day names
        day_mapping = {
            'MON': 'MON', 'TUE': 'TUE', 'WED': 'WED', 
            'THU': 'THU', 'FRI': 'FRI', 'SAT': 'SAT', 'SUN': 'SUN'
        }
        
        day_code = day_mapping.get(current_day, current_day)
        
        # Get slots that are currently active (within 30 minutes of start time)
        from datetime import timedelta
        time_buffer = timedelta(minutes=30)
        
        # Convert current time to datetime for comparison
        current_datetime = timezone.now()
        
        active_slots = TimetableSlot.objects.filter(
            day_of_week=day_code,
            start_time__lte=current_time,
            end_time__gte=current_time
        ).select_related('course', 'level', 'timetable__department', 'lecturer')
        
        return active_slots
    
    def get_students_for_timetable_slot(self, timetable_slot):
        """
        Get students who should be present for a specific timetable slot
        
        Args:
            timetable_slot: TimetableSlot instance
            
        Returns:
            QuerySet: Students who have selected this course and are offering it
        """
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
        """
        Enhanced frame processing for multiple simultaneous face recognition
        
        Args:
            frame_data: Base64 encoded image data or numpy array
            session_id: Optional live session ID for attendance linking
            department_id: Optional department ID to filter timetable slots
            
        Returns:
            dict: Processing results with detected faces and recognized students
        """
        try:
            # Convert frame data to OpenCV format
            if isinstance(frame_data, str):
                # Base64 encoded image
                image_data = base64.b64decode(frame_data.split(',')[1])
                image = Image.open(io.BytesIO(image_data))
                frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            else:
                # Assume numpy array
                frame = frame_data
            
            # Enhanced preprocessing for better face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Apply multiple preprocessing techniques
            # 1. Histogram equalization for better contrast
            gray_eq = cv2.equalizeHist(gray)
            
            # 2. CLAHE for local contrast enhancement
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            gray_clahe = clahe.apply(gray)
            
            # 3. Combine both techniques
            gray_enhanced = cv2.addWeighted(gray_eq, 0.5, gray_clahe, 0.5, 0)
            
            # Detect faces using enhanced multi-scale detection
            faces = self._detect_faces_multi_scale(gray_enhanced)
            
            # Get current active timetable slots
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
                'expected_students': [],
                'processing_stats': {
                    'total_faces_detected': len(faces),
                    'faces_processed': 0,
                    'high_quality_faces': 0,
                    'successful_recognitions': 0
                }
            }
            
            # Add active timetable slot information
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
                
                # Add expected students for this slot
                for student in expected_students:
                    if student.matric_number not in [s['matric_number'] for s in results['expected_students']]:
                        results['expected_students'].append({
                            'student_id': student.id,
                            'matric_number': student.matric_number,
                            'full_name': student.full_name,
                            'course_code': slot.course.code,
                            'level': slot.level.name
                        })
            
            # Process faces in batches for better performance with 50+ students
            processed_faces = 0
            high_quality_faces = 0
            successful_recognitions = 0
            
            # Sort faces by size (larger faces first - likely clearer)
            faces_with_size = [(face, face[2] * face[3]) for face in faces]
            faces_with_size.sort(key=lambda x: x[1], reverse=True)
            sorted_faces = [face[0] for face in faces_with_size]
            
            # Process in batches to avoid memory issues
            batch_size = self.BATCH_PROCESSING_SIZE
            for batch_start in range(0, min(len(sorted_faces), self.MAX_FACES_PER_FRAME), batch_size):
                batch_end = min(batch_start + batch_size, len(sorted_faces), self.MAX_FACES_PER_FRAME)
                batch_faces = sorted_faces[batch_start:batch_end]
                
                for i, (x, y, w, h) in enumerate(batch_faces):
                    face_index = batch_start + i
                    
                    # Extract face region with adaptive padding for distant faces
                    padding = max(3, min(w, h) // 15)  # Smaller padding for distant faces
                    x_start = max(0, x - padding)
                    y_start = max(0, y - padding)
                    x_end = min(gray_enhanced.shape[1], x + w + padding)
                    y_end = min(gray_enhanced.shape[0], y + h + padding)
                    
                    face_roi = gray_enhanced[y_start:y_end, x_start:x_end]
                    
                    # Skip if ROI is invalid
                    if face_roi.size == 0:
                        continue
                    
                    processed_faces += 1
                    
                    # Calculate face quality with adjusted thresholds for distant faces
                    quality_score = self._calculate_face_quality(face_roi)
                    
                    # Boost quality score for larger faces (likely closer/clearer)
                    size_boost = min((w * h) / (100 * 100), 1.0) * 0.2
                    adjusted_quality = min(quality_score + size_boost, 1.0)
                    
                    face_info = {
                        'box': {'x': int(x), 'y': int(y), 'width': int(w), 'height': int(h)},
                        'quality_score': float(adjusted_quality),
                        'face_index': face_index,
                        'face_size': w * h,
                        'distance_estimate': self._estimate_distance(w, h)
                    }
                    
                    # Process faces that meet quality threshold
                    if adjusted_quality >= self.FACE_QUALITY_THRESHOLD:
                        high_quality_faces += 1
                        
                        # Enhanced preprocessing for challenging conditions
                        face_processed = self._preprocess_face(face_roi)
                        
                        # Multiple recognition attempts with different preprocessing
                        predictions = []
                        
                        # Attempt 1: Standard preprocessing
                        try:
                            label_id, confidence = self.recognizer.predict(face_processed)
                            predictions.append((label_id, confidence, 'standard'))
                        except Exception as e:
                            logger.warning(f"Standard recognition failed for face {face_index}: {e}")
                        
                        # Attempt 2: Enhanced contrast (for poor lighting)
                        try:
                            enhanced_face = cv2.convertScaleAbs(face_processed, alpha=1.2, beta=10)
                            label_id, confidence = self.recognizer.predict(enhanced_face)
                            predictions.append((label_id, confidence, 'enhanced'))
                        except Exception as e:
                            logger.warning(f"Enhanced recognition failed for face {face_index}: {e}")
                        
                        if predictions:
                            # Use the prediction with highest confidence (lowest value)
                            best_prediction = min(predictions, key=lambda x: x[1])
                            label_id, confidence, method = best_prediction
                            
                            face_info.update({
                                'confidence': float(confidence),
                                'label_id': int(label_id),
                                'predictions_count': len(predictions),
                                'recognition_method': method
                            })
                            
                            logger.info(f"Face {face_index}: label_id={label_id}, confidence={confidence:.2f}, "
                                      f"quality={adjusted_quality:.2f}, method={method}, size={w}x{h}")
                            
                            # Adjust confidence threshold based on face size (distant faces get more lenient threshold)
                            size_factor = min((w * h) / (50 * 50), 1.0)  # Normalize by minimum expected size
                            adjusted_threshold = self.CONFIDENCE_THRESHOLD + (1 - size_factor) * 15  # More lenient for smaller faces
                            
                            # Check if recognition is confident enough
                            if confidence < adjusted_threshold:
                                matric_number = self.id_to_matric.get(label_id, None)
                                
                                if matric_number is not None:
                                    # Get student information
                                    try:
                                        student = Student.objects.get(matric_number=matric_number)
                                        
                                        # Check if student is expected in current timetable slots
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
                                        
                                        # Mark attendance for active timetable slots
                                        attendance_results = []
                                        for slot in active_slots:
                                            if student in self.get_students_for_timetable_slot(slot):
                                                attendance_result = self._mark_timetable_attendance(student, slot, session_id)
                                                attendance_results.append(attendance_result)
                                        
                                        face_info['attendance_results'] = attendance_results
                                        
                                        # Add to recognized students (avoid duplicates)
                                        existing_recognition = next(
                                            (s for s in results['recognized_students'] 
                                             if s['matric_number'] == matric_number), None
                                        )
                                        
                                        if not existing_recognition:
                                            results['recognized_students'].append({
                                                'student_id': student.id,
                                                'matric_number': matric_number,
                                                'full_name': student.full_name,
                                                'confidence': confidence,
                                                'quality_score': adjusted_quality,
                                                'timestamp': timezone.now().isoformat(),
                                                'is_expected': is_expected,
                                                'attendance_marked': len(attendance_results) > 0,
                                                'face_position': {'x': x, 'y': y, 'w': w, 'h': h},
                                                'distance_estimate': face_info['distance_estimate'],
                                                'recognition_method': method
                                            })
                                            successful_recognitions += 1
                                        
                                        logger.info(f"✅ Student recognized: {student.full_name} ({matric_number}) - "
                                                  f"Confidence: {confidence:.2f}, Distance: {face_info['distance_estimate']}")
                                        
                                    except Student.DoesNotExist:
                                        logger.warning(f"Student not found in database for matric: {matric_number}")
                                        face_info.update({
                                            'recognized': False,
                                            'matric_number': matric_number,
                                            'full_name': f'Unknown Student ({matric_number})',
                                            'status': 'not_found_in_db'
                                        })
                                        results['unrecognized_faces'].append(face_info)
                                else:
                                    logger.warning(f"Label ID {label_id} not found in trained labels")
                                    face_info.update({
                                        'recognized': False,
                                        'full_name': f'Unknown {label_id}',
                                        'status': 'unknown_label'
                                    })
                                    results['unrecognized_faces'].append(face_info)
                            else:
                                logger.info(f"Low confidence recognition: {confidence:.2f} >= {adjusted_threshold:.2f}")
                                face_info.update({
                                    'recognized': False,
                                    'full_name': f'Low Confidence ({confidence:.1f})',
                                    'status': 'low_confidence',
                                    'confidence': float(confidence)
                                })
                                results['unrecognized_faces'].append(face_info)
                        else:
                            face_info.update({
                                'recognized': False,
                                'full_name': 'Recognition Failed',
                                'status': 'recognition_error'
                            })
                            results['unrecognized_faces'].append(face_info)
                    else:
                        # Low quality face
                        face_info.update({
                            'recognized': False,
                            'full_name': f'Low Quality ({adjusted_quality:.2f})',
                            'status': 'low_quality'
                        })
                        results['unrecognized_faces'].append(face_info)
                    
                    results['face_boxes'].append(face_info)
            
            # Update processing statistics
            results['processing_stats'].update({
                'faces_processed': processed_faces,
                'high_quality_faces': high_quality_faces,
                'successful_recognitions': successful_recognitions,
                'recognition_rate': (successful_recognitions / max(high_quality_faces, 1)) * 100
            })
            
            logger.info(f"Frame processing complete: {processed_faces} faces processed, "
                       f"{successful_recognitions} recognized, "
                       f"{results['processing_stats']['recognition_rate']:.1f}% success rate")
            
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
                'expected_students': [],
                'processing_stats': {
                    'total_faces_detected': 0,
                    'faces_processed': 0,
                    'high_quality_faces': 0,
                    'successful_recognitions': 0,
                    'recognition_rate': 0
                }
            }
    
    def _mark_timetable_attendance(self, student, timetable_slot, session_id=None):
        """
        Mark attendance for a student in a specific timetable slot
        
        Args:
            student: Student model instance
            timetable_slot: TimetableSlot instance
            session_id: Optional live session UUID
            
        Returns:
            dict: Attendance marking result
        """
        try:
            today = timezone.now().date()
            
            # Check if attendance already marked for this student, course, and date
            existing_attendance = Attendance.objects.filter(
                student=student,
                date=today,
                course_registration__course=timetable_slot.course
            ).first()
            
            if existing_attendance:
                return {
                    'success': False,
                    'message': f'Attendance already marked for {timetable_slot.course.code}',
                    'attendance_id': existing_attendance.id,
                    'course_code': timetable_slot.course.code
                }
            
            # Get or create course registration for the student
            course_registration, created = CourseRegistration.objects.get_or_create(
                student=student,
                course=timetable_slot.course,
                defaults={
                    'academic_year': '2025/2026',  # You might want to make this dynamic
                    'semester': 'Semester 1'
                }
            )
            
            # Create attendance record
            attendance = Attendance.objects.create(
                student=student,
                course_registration=course_registration,
                date=today,
                status='present',
                recorded_at=timezone.now(),
                is_manual_override=False
            )
            
            # Add to live session if provided
            if session_id:
                try:
                    session = LiveSession.objects.get(id=session_id, status='live')
                    participant, created = LiveSessionParticipant.objects.get_or_create(
                        session=session,
                        user=student.user,
                        defaults={
                            'joined_at': timezone.now(),
                            'is_active': True,
                            'has_video': True
                        }
                    )
                    
                    if not created and not participant.is_active:
                        participant.is_active = True
                        participant.joined_at = timezone.now()
                        participant.save()
                        
                except LiveSession.DoesNotExist:
                    logger.warning(f"Live session {session_id} not found")
            
            logger.info(f"Timetable attendance marked for {student.matric_number} in {timetable_slot.course.code}")
            
            return {
                'success': True,
                'message': f'Attendance marked for {timetable_slot.course.code}',
                'attendance_id': attendance.id,
                'course_code': timetable_slot.course.code,
                'timetable_slot_id': timetable_slot.id
            }
            
        except Exception as e:
            logger.error(f"Error marking timetable attendance: {e}")
            return {
                'success': False,
                'message': str(e),
                'course_code': timetable_slot.course.code
            }
    
    def get_model_status(self):
        """Get the status of loaded models"""
        return {
            'model_loaded': self.recognizer is not None,
            'labels_loaded': len(self.label_map) > 0,
            'cascade_loaded': self.face_cascade is not None and not self.face_cascade.empty(),
            'total_students': len(self.label_map),
            'model_file_exists': self.model_file.exists(),
            'labels_file_exists': self.labels_file.exists()
        }
    
    def reload_models(self):
        """Reload face recognition models (useful after retraining)"""
        try:
            self._load_models()
            return {'success': True, 'message': 'Models reloaded successfully'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

# Global service instance
face_recognition_service = FaceRecognitionService()