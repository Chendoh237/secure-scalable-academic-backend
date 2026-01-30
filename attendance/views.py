from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from attendance.face_recognition import face_recognition_service
from attendance.services import mark_attendance
from attendance.compatibility import mark_attendance_enhanced
from attendance.notification_service import AttendanceNotificationService
import tempfile
import base64
import io
from PIL import Image
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def face_attendance(request):
    """
    Enhanced face attendance endpoint that integrates with student course selections
    """
    image = request.FILES.get("image")

    if not image:
        return Response({"error": "Image required"}, status=400)

    try:
        # Convert uploaded image to base64 for processing
        image_data = image.read()
        image_pil = Image.open(io.BytesIO(image_data))
        
        # Convert to base64 format expected by face recognition service
        buffer = io.BytesIO()
        image_pil.save(buffer, format='JPEG')
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        frame_data = f"data:image/jpeg;base64,{image_base64}"
        
        # Process the frame using our face recognition service
        results = face_recognition_service.process_frame(frame_data)
        
        if results.get('error'):
            return Response({"error": results['error']}, status=500)
        
        recognized_students = results.get('recognized_students', [])
        
        if not recognized_students:
            return Response({"error": "Face not recognized"}, status=400)
        
        # Use the first recognized student
        student = recognized_students[0]
        matric = student['matric_number']
        
        # Use enhanced attendance marking that considers course selections
        result = mark_attendance_enhanced(matric)
        
        if result['success']:
            # Create real-time notification for attendance marking
            try:
                if result.get('attendance') and hasattr(result['attendance'], 'id'):
                    from .models import Attendance
                    attendance_record = Attendance.objects.get(id=result['attendance'].id)
                    notification_result = AttendanceNotificationService.create_attendance_notification(
                        attendance_record=attendance_record,
                        notification_type='attendance'
                    )
                    logger.info(f"Attendance notification created: {notification_result.get('success', False)}")
            except Exception as e:
                logger.error(f"Error creating attendance notification: {e}")
                # Don't fail the attendance marking if notification fails
            
            return Response({
                "success": True,
                "student": result['student'],
                "attendance": result['attendance'],
                "validation": result.get('validation', {}),
                "message": result['message']
            })
        else:
            # Return detailed error information
            return Response({
                "success": False,
                "error": result['message'],
                "student": result.get('student'),
                "validation": result.get('validation', {}),
                "details": "Attendance validation failed - check course selections and level"
            }, status=400)
        
    except Exception as e:
        logger.error(f"Error in face_attendance: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def manual_attendance(request):
    """
    Manual attendance endpoint for testing and admin use
    """
    matric_number = request.data.get('matric_number')
    
    if not matric_number:
        return Response({"error": "Matric number required"}, status=400)
    
    try:
        # Use enhanced attendance marking
        result = mark_attendance_enhanced(matric_number)
        
        if result['success']:
            # Create real-time notification for manual attendance marking
            try:
                if result.get('attendance') and hasattr(result['attendance'], 'id'):
                    from .models import Attendance
                    attendance_record = Attendance.objects.get(id=result['attendance'].id)
                    notification_result = AttendanceNotificationService.create_attendance_notification(
                        attendance_record=attendance_record,
                        notification_type='attendance'
                    )
                    logger.info(f"Manual attendance notification created: {notification_result.get('success', False)}")
            except Exception as e:
                logger.error(f"Error creating manual attendance notification: {e}")
                # Don't fail the attendance marking if notification fails
            
            return Response({
                "success": True,
                "student": result['student'],
                "attendance": result['attendance'],
                "validation": result.get('validation', {}),
                "message": result['message']
            })
        else:
            return Response({
                "success": False,
                "error": result['message'],
                "student": result.get('student'),
                "validation": result.get('validation', {}),
            }, status=400)
            
    except Exception as e:
        logger.error(f"Error in manual_attendance: {e}")
        return Response({"error": str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def attendance_validation_info(request):
    """
    Get attendance validation information for debugging
    """
    matric_number = request.GET.get('matric_number')
    
    if not matric_number:
        return Response({"error": "Matric number required"}, status=400)
    
    try:
        from students.models import Student
        from attendance.enhanced_services import EnhancedAttendanceService
        
        # Get student
        try:
            student = Student.objects.select_related(
                'department', 'faculty'
            ).get(matric_number=matric_number)
        except Student.DoesNotExist:
            return Response({"error": "Student not found"}, status=404)
        
        # Get current timetable slot
        current_slot = EnhancedAttendanceService.get_current_timetable_slot_for_student(student)
        
        if not current_slot:
            return Response({
                "student": {
                    "matric_number": student.matric_number,
                    "full_name": student.full_name,
                    "department": student.department.name
                },
                "current_slot": None,
                "message": "No ongoing class found or student not offering current courses"
            })
        
        # Get validation info
        validation = EnhancedAttendanceService.validate_attendance_eligibility(student, current_slot)
        
        # Get offered courses
        offered_courses = EnhancedAttendanceService.get_student_offered_courses(student)
        
        return Response({
            "student": {
                "matric_number": student.matric_number,
                "full_name": student.full_name,
                "department": student.department.name
            },
            "current_slot": {
                "course_code": current_slot.course.code,
                "course_title": current_slot.course.title,
                "lecturer": current_slot.lecturer.user.get_full_name(),
                "day": current_slot.day_of_week,
                "start_time": current_slot.start_time.strftime('%H:%M'),
                "end_time": current_slot.end_time.strftime('%H:%M'),
                "venue": current_slot.venue
            },
            "validation": validation,
            "offered_courses": offered_courses
        })
        
    except Exception as e:
        logger.error(f"Error getting attendance validation info: {e}")
        return Response({"error": str(e)}, status=500)
