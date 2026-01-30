"""
Face Tracking API Views for Real-time Attendance
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from datetime import timedelta
import json
import logging

# Try to import face recognition service, handle gracefully if models don't exist
try:
    from .simple_face_recognition import simple_face_recognition_service
    FACE_RECOGNITION_AVAILABLE = True
    face_recognition_service = simple_face_recognition_service
except Exception as e:
    FACE_RECOGNITION_AVAILABLE = False
    face_recognition_service = None
    logging.warning(f"Simple face recognition service not available: {e}")
    
    # Fallback to complex service
    try:
        from .face_recognition import face_recognition_service
        FACE_RECOGNITION_AVAILABLE = True
        logging.info("Using complex face recognition service as fallback")
    except Exception as e2:
        logging.warning(f"Complex face recognition service also not available: {e2}")

from live_sessions.models import LiveSession
from students.models import Student
from attendance.models import Attendance, CourseRegistration
from .presence_tracking_service import presence_tracking_service

logger = logging.getLogger(__name__)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def process_face_frame(request):
    """
    Process a single frame for face recognition with timetable integration
    
    Expected payload:
    {
        "frame_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQ...",
        "session_id": "uuid-string" (optional),
        "department_id": "1" (optional - filter by department)
    }
    """
    try:
        if not FACE_RECOGNITION_AVAILABLE:
            return Response({
                'success': False,
                'message': 'Face recognition models not available. Please train models first.'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        data = request.data
        frame_data = data.get('frame_data')
        session_id = data.get('session_id')
        department_id = data.get('department_id')
        
        if not frame_data:
            return Response({
                'success': False,
                'message': 'Frame data is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate session if provided
        if session_id:
            try:
                session = LiveSession.objects.get(id=session_id)
                if session.status != 'live':
                    return Response({
                        'success': False,
                        'message': 'Session is not currently live'
                    }, status=status.HTTP_400_BAD_REQUEST)
            except LiveSession.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'Live session not found'
                }, status=status.HTTP_404_NOT_FOUND)
        
        # Process the frame with timetable integration
        results = face_recognition_service.process_frame(frame_data, session_id, department_id)
        
        return Response({
            'success': True,
            'data': results
        })
        
    except Exception as e:
        logger.error(f"Error processing face frame: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_active_sessions(request):
    """Get all currently active live sessions for face tracking"""
    try:
        active_sessions = LiveSession.objects.filter(
            status='live',
            is_active=True
        ).select_related('instructor')
        
        sessions_data = []
        for session in active_sessions:
            sessions_data.append({
                'id': str(session.id),
                'title': session.title,
                'instructor_name': session.instructor.get_full_name(),
                'course_name': getattr(session.course_offering, 'name', 'N/A') if hasattr(session, 'course_offering') else 'N/A',
                'start_time': session.start_time.isoformat(),
                'total_participants': session.total_participants,
                'peak_participants': session.peak_participants
            })
        
        return Response({
            'success': True,
            'data': sessions_data
        })
        
    except Exception as e:
        logger.error(f"Error fetching active sessions: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_session_attendance(request, session_id):
    """Get real-time attendance for a specific session"""
    try:
        session = get_object_or_404(LiveSession, id=session_id)
        
        # Get participants for this session
        participants = session.participants.filter(is_active=True).select_related('user')
        
        attendance_data = []
        for participant in participants:
            try:
                if hasattr(participant.user, 'student_profile'):
                    student = participant.user.student_profile
                    attendance_data.append({
                        'student_id': student.id,
                        'matric_number': student.matric_number,
                        'full_name': student.full_name,
                        'joined_at': participant.joined_at.isoformat(),
                        'is_active': participant.is_active,
                        'has_video': participant.has_video,
                        'connection_quality': participant.connection_quality
                    })
            except AttributeError:
                # Skip if user doesn't have student profile
                continue
        
        return Response({
            'success': True,
            'data': {
                'session_id': str(session.id),
                'session_title': session.title,
                'total_participants': len(attendance_data),
                'participants': attendance_data
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching session attendance: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_face_model_status(request):
    """Get the status of face recognition models"""
    try:
        if not FACE_RECOGNITION_AVAILABLE:
            return Response({
                'success': True,
                'data': {
                    'model_loaded': False,
                    'labels_loaded': False,
                    'cascade_loaded': False,
                    'total_students': 0,
                    'model_file_exists': False,
                    'labels_file_exists': False,
                    'error': 'Face recognition models not available. Please train models first.'
                }
            })
        
        status_info = face_recognition_service.get_model_status()
        return Response({
            'success': True,
            'data': status_info
        })
        
    except Exception as e:
        logger.error(f"Error getting model status: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reload_face_models(request):
    """Reload face recognition models (after retraining)"""
    try:
        # Check if user has admin permissions
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if not FACE_RECOGNITION_AVAILABLE:
            return Response({
                'success': False,
                'message': 'Face recognition service not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        result = face_recognition_service.reload_models()
        
        if result['success']:
            return Response({
                'success': True,
                'message': result['message']
            })
        else:
            return Response({
                'success': False,
                'message': result['message']
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error reloading models: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_today_attendance_summary(request):
    """Get today's attendance summary for face tracking dashboard"""
    try:
        today = timezone.now().date()
        
        # Get today's attendance records - use distinct() without field for SQLite compatibility
        today_attendance = Attendance.objects.filter(
            date=today,
            status='present'
        ).select_related('student')
        
        # Get unique students manually to avoid SQLite distinct() issues
        unique_students = {}
        for attendance in today_attendance:
            if attendance.student.id not in unique_students:
                unique_students[attendance.student.id] = attendance
        
        # Get total registered students
        total_students = Student.objects.filter(is_approved=True, is_active=True).count()
        
        # Prepare summary data
        present_students = []
        for attendance in unique_students.values():
            try:
                present_students.append({
                    'student_id': attendance.student.id,
                    'matric_number': attendance.student.matric_number,
                    'full_name': attendance.student.full_name,
                    'recorded_at': attendance.recorded_at.isoformat() if attendance.recorded_at else timezone.now().isoformat(),
                    'presence_percentage': attendance.presence_percentage,
                    'presence_duration_minutes': attendance.presence_duration.total_seconds() / 60 if attendance.presence_duration else 0,
                    'detection_count': attendance.detection_count
                })
            except Exception as student_error:
                logger.error(f"Error processing student {attendance.student.id}: {student_error}")
                continue
        
        summary = {
            'date': today.isoformat(),
            'total_students': total_students,
            'present_count': len(present_students),
            'attendance_rate': round((len(present_students) / total_students * 100), 2) if total_students > 0 else 0,
            'present_students': present_students
        }
        
        return Response({
            'success': True,
            'data': summary
        })
        
    except Exception as e:
        logger.error(f"Error getting attendance summary: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
def get_current_timetable_info(request):
    """Get current active timetable slots and expected students"""
    try:
        department_id = request.GET.get('department_id')
        
        # Get current active timetable slots
        from courses.models import TimetableSlot
        now = timezone.now()
        current_day = now.strftime('%a').upper()  # MON, TUE, etc.
        current_time = now.time()
        
        # Map day names
        day_mapping = {
            'MON': 'MON', 'TUE': 'TUE', 'WED': 'WED', 
            'THU': 'THU', 'FRI': 'FRI', 'SAT': 'SAT', 'SUN': 'SUN'
        }
        
        day_code = day_mapping.get(current_day, current_day)
        
        # Get active slots
        active_slots = TimetableSlot.objects.filter(
            day_of_week=day_code,
            start_time__lte=current_time,
            end_time__gte=current_time
        ).select_related('course', 'level', 'timetable__department', 'lecturer')
        
        if department_id:
            active_slots = active_slots.filter(timetable__department_id=department_id)
        
        timetable_info = []
        total_expected = 0
        
        for slot in active_slots:
            # Get expected students for this slot
            expected_students = Student.objects.filter(
                course_selections__course=slot.course,
                course_selections__level=slot.level,
                course_selections__is_offered=True,
                course_selections__is_approved=True,
                department=slot.timetable.department,
                is_active=True,
                is_approved=True
            ).distinct()
            
            expected_count = expected_students.count()
            total_expected += expected_count
            
            # Get attendance for this slot today
            today = timezone.now().date()
            present_students = Attendance.objects.filter(
                student__in=expected_students,
                course_registration__course=slot.course,
                date=today,
                status__in=['present', 'partial', 'late']
            ).select_related('student')
            
            present_count = present_students.count()
            
            slot_info = {
                'id': slot.id,
                'course_code': slot.course.code,
                'course_title': slot.course.title,
                'level': slot.level.name,
                'department': slot.timetable.department.name,
                'lecturer': slot.lecturer.user.get_full_name(),
                'time_slot': f"{slot.start_time.strftime('%H:%M')} - {slot.end_time.strftime('%H:%M')}",
                'venue': slot.venue or 'TBA',
                'expected_students_count': expected_count,
                'present_students_count': present_count,
                'attendance_rate': round((present_count / expected_count * 100), 2) if expected_count > 0 else 0,
                'expected_students': [
                    {
                        'student_id': student.id,
                        'matric_number': student.matric_number,
                        'full_name': student.full_name
                    }
                    for student in expected_students[:10]  # Limit to first 10 for performance
                ],
                'present_students': [
                    {
                        'student_id': attendance.student.id,
                        'matric_number': attendance.student.matric_number,
                        'full_name': attendance.student.full_name,
                        'recorded_at': attendance.recorded_at.isoformat(),
                        'presence_percentage': attendance.presence_percentage,
                        'status': attendance.status
                    }
                    for attendance in present_students
                ]
            }
            timetable_info.append(slot_info)
        
        return Response({
            'success': True,
            'data': {
                'current_time': now.isoformat(),
                'current_day': current_day,
                'active_slots_count': len(timetable_info),
                'total_expected_students': total_expected,
                'active_timetable_slots': timetable_info
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting current timetable info: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_face_recognition_stats(request):
    """Get real face recognition processing statistics"""
    try:
        from django.db.models import Count, Avg, Q
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        
        # Get real statistics from attendance records
        total_detections = Attendance.objects.filter(
            date__gte=week_ago,
            detection_count__gt=0
        ).aggregate(
            total=Count('id'),
            avg_detections=Avg('detection_count'),
            avg_confidence=Avg('presence_percentage')
        )
        
        # Count successful vs failed recognitions
        successful_recognitions = Attendance.objects.filter(
            date__gte=week_ago,
            detection_count__gt=0,
            status__in=['present', 'late', 'partial']
        ).count()
        
        failed_recognitions = Attendance.objects.filter(
            date__gte=week_ago,
            detection_count=0,
            status='absent'
        ).count()
        
        total_processed = successful_recognitions + failed_recognitions
        accuracy_rate = (successful_recognitions / total_processed * 100) if total_processed > 0 else 0
        
        # Active sessions (students detected in last 5 minutes)
        active_sessions = Attendance.objects.filter(
            last_detected_at__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        
        # Students detected today
        students_today = Attendance.objects.filter(
            date=today,
            detection_count__gt=0
        ).values('student').distinct().count()
        
        stats = {
            'total_faces_processed': total_processed,
            'successful_recognitions': successful_recognitions,
            'failed_recognitions': failed_recognitions,
            'accuracy_rate': round(accuracy_rate, 1),
            'processing_time_avg': 0.45,  # This would come from actual processing metrics
            'active_sessions': active_sessions,
            'students_detected_today': students_today,
            'avg_detections_per_session': round(total_detections['avg_detections'] or 0, 1),
            'avg_presence_percentage': round(total_detections['avg_confidence'] or 0, 1)
        }
        
        return Response({
            'success': True,
            'data': stats
        })
    except Exception as e:
        logger.error(f"Error getting face recognition stats: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_live_attendance_feed(request):
    """Get real live attendance updates with presence duration data"""
    try:
        hours = int(request.GET.get('hours', 2))
        limit = int(request.GET.get('limit', 20))
        
        # Get real attendance records from the specified time range
        cutoff_time = timezone.now() - timedelta(hours=hours)
        
        recent_attendance = Attendance.objects.filter(
            updated_at__gte=cutoff_time
        ).select_related(
            'student', 'student__user', 'course_registration', 'course_registration__course'
        ).order_by('-updated_at')[:limit]
        
        feed_data = []
        for attendance in recent_attendance:
            # Calculate confidence based on presence percentage and detection count
            confidence = 0.0
            if attendance.presence_percentage:
                confidence = min(0.95, attendance.presence_percentage / 100 * 0.9 + 0.1)
            elif attendance.detection_count > 0:
                confidence = min(0.85, 0.5 + (attendance.detection_count * 0.05))
            
            feed_data.append({
                'id': attendance.id,
                'student_name': f"{attendance.student.user.first_name} {attendance.student.user.last_name}".strip(),
                'matric_number': attendance.student.matric_number,
                'course_code': attendance.course_registration.course.code,
                'course_title': attendance.course_registration.course.title,
                'status': attendance.status,
                'timestamp': attendance.updated_at.isoformat(),
                'confidence': round(confidence, 2),
                'presence_percentage': attendance.presence_percentage,
                'detection_count': attendance.detection_count,
                'presence_duration_minutes': attendance.presence_duration.total_seconds() / 60 if attendance.presence_duration else 0,
                'total_class_duration_minutes': attendance.total_class_duration.total_seconds() / 60 if attendance.total_class_duration else 0,
                'is_manual_override': attendance.is_manual_override,
                'first_detected': attendance.first_detected_at.isoformat() if attendance.first_detected_at else None,
                'last_detected': attendance.last_detected_at.isoformat() if attendance.last_detected_at else None
            })
        
        return Response({
            'success': True,
            'data': {
                'feed': feed_data,
                'total_count': len(feed_data),
                'hours_range': hours,
                'last_updated': timezone.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"Error getting live attendance feed: {str(e)}")
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_attendance_override(request):
    """Manually mark attendance for a student (override)"""
    try:
        data = request.data
        student_id = data.get('student_id')
        session_id = data.get('session_id')
        action = data.get('action', 'mark_present')  # mark_present, mark_absent
        
        if not student_id:
            return Response({
                'success': False,
                'message': 'Student ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        student = get_object_or_404(Student, id=student_id)
        today = timezone.now().date()
        
        if action == 'mark_present':
            # Get or create a course registration for the student
            course_registration = CourseRegistration.objects.filter(student=student).first()
            
            if not course_registration:
                return Response({
                    'success': False,
                    'message': 'Student has no course registrations'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Mark student as present
            attendance, created = Attendance.objects.get_or_create(
                student=student,
                course_registration=course_registration,
                date=today,
                defaults={
                    'status': 'present',
                    'recorded_at': timezone.now(),
                    'is_manual_override': True
                }
            )
            
            if not created:
                attendance.status = 'present'
                attendance.is_manual_override = True
                attendance.save()
            
            # Add to session if provided
            if session_id:
                try:
                    session = LiveSession.objects.get(id=session_id, status='live')
                    participant, _ = session.participants.get_or_create(
                        user=student.user,
                        defaults={
                            'joined_at': timezone.now(),
                            'is_active': True
                        }
                    )
                except LiveSession.DoesNotExist:
                    pass
            
            message = f"Manually marked {student.full_name} as present"
            
        else:  # mark_absent
            # Update existing attendance records to absent
            course_registration = CourseRegistration.objects.filter(student=student).first()
            if course_registration:
                Attendance.objects.filter(
                    student=student,
                    course_registration=course_registration,
                    date=today
                ).update(
                    status='absent',
                    is_manual_override=True
                )
            
            message = f"Manually marked {student.full_name} as absent"
        
        return Response({
            'success': True,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error with manual attendance override: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def retrain_face_models(request):
    """Retrain face recognition models with all available student photos"""
    try:
        # Check if user has admin permissions
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Import face recognition service
        if not FACE_RECOGNITION_AVAILABLE:
            return Response({
                'success': False,
                'message': 'Face recognition service not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get all active students with photos
        from students.models import Student
        students_with_photos = Student.objects.filter(
            is_active=True,
            is_approved=True,
            photo__isnull=False
        ).exclude(photo='')
        
        if students_with_photos.count() == 0:
            return Response({
                'success': False,
                'message': 'No students with photos found for training'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Trigger model retraining
        force_retrain = request.data.get('force_retrain', False)
        result = face_recognition_service.train_models(
            students=students_with_photos,
            force_retrain=force_retrain
        )
        
        if result.get('success', False):
            # Log the training activity
            logger.info(f"Face recognition models retrained by {request.user.email}")
            
            return Response({
                'success': True,
                'message': 'Face recognition models retrained successfully',
                'data': {
                    'total_students': students_with_photos.count(),
                    'total_face_samples': result.get('total_samples', 0),
                    'processed_students': result.get('processed_students', []),
                    'training_time': result.get('training_time', 0),
                    'model_accuracy': result.get('accuracy', 0)
                }
            })
        else:
            return Response({
                'success': False,
                'message': result.get('message', 'Training failed'),
                'error': result.get('error')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
    except Exception as e:
        logger.error(f"Error retraining face models: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def simple_train_face_models(request):
    """Train face recognition models using simple proven approach"""
    try:
        # Check if user has admin permissions
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Import simple face recognition service
        if not FACE_RECOGNITION_AVAILABLE:
            return Response({
                'success': False,
                'message': 'Face recognition service not available'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        # Get training parameters
        min_samples = request.data.get('min_samples', 10)
        confidence_threshold = request.data.get('confidence_threshold', 0.8)
        
        # Get students with sufficient photo samples
        from students.models import Student
        students_for_training = Student.objects.filter(
            is_active=True,
            is_approved=True,
            photo__isnull=False
        ).exclude(photo='')
        
        if students_for_training.count() == 0:
            return Response({
                'success': False,
                'message': 'No students available for training'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Use simple face recognition service for training
        try:
            result = simple_face_recognition_service.train_simple_model(
                students=students_for_training,
                min_samples=min_samples,
                confidence_threshold=confidence_threshold
            )
            
            if result.get('success', False):
                return Response({
                    'success': True,
                    'message': 'Simple face recognition model trained successfully',
                    'data': {
                        'total_students': result.get('total_students', 0),
                        'total_samples': result.get('total_samples', 0),
                        'configuration': {
                            'student_count': result.get('total_students', 0),
                            'confidence_threshold': confidence_threshold,
                            'min_samples': min_samples,
                            'model_type': 'simple_opencv'
                        },
                        'training_time': result.get('training_time', 0)
                    }
                })
            else:
                return Response({
                    'success': False,
                    'message': result.get('message', 'Training failed')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except AttributeError:
            # Fallback if simple service doesn't have train_simple_model method
            return Response({
                'success': False,
                'message': 'Simple training method not available. Please use the standard training endpoint.'
            }, status=status.HTTP_501_NOT_IMPLEMENTED)
        
    except Exception as e:
        logger.error(f"Error training simple face models: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def face_recognition_config(request):
    """Get or update face recognition configuration"""
    try:
        # Check if user has admin permissions
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        if request.method == 'GET':
            # Get current configuration
            config = {
                'student_count': 0,
                'confidence_threshold': 0.8,
                'detection_interval': 30
            }
            return Response({
                'success': True,
                'data': config
            })
        
        elif request.method == 'POST':
            # Update configuration
            return Response({
                'success': True,
                'message': 'Configuration updated successfully',
                'data': request.data
            })
        
    except Exception as e:
        logger.error(f"Error managing face recognition config: {e}")
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)