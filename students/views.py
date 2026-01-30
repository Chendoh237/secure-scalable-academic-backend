from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError, AuthenticationFailed
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from .services.attendance_summary import get_attendance_summary
from rest_framework import status
from django.contrib.auth.models import User
from django.conf import settings
from pathlib import Path
from rest_framework.permissions import AllowAny
from .serializers import StudentRegistrationSerializer, StudentLoginSerializer, StudentDashboardOverviewSerializer, CourseRegistrationSerializer
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from .serializers import UserSerializer
from .utils import get_student_from_request
from datetime import datetime
from attendance.models import Attendance, CourseRegistration
from courses.models import CourseRegistration, TimetableEntry, TimetableSlot, Level
from academics.models import CourseOffering
from .models import Student, ApprovedMatricule
from institutions.models import Institution, Faculty, Department
from django.utils.timezone import now

import logging
logger = logging.getLogger(__name__)

User = get_user_model()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_student_status(request):
    """Check if student exists and is approved"""
    try:
        student = get_student_from_request(request)
        return Response({
            'exists': True,
            'approved': student.is_approved,
            'matricule': student.matric_number,
            'name': student.full_name
        })
    except Exception as e:
        return Response({
            'exists': False,
            'error': str(e)
        })
class UserProfileView(APIView):
    authentication_classes = [JWTAuthentication]  # Explicitly add JWT authentication
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        logger.info(f"User {request.user.username} is accessing profile")
        user = request.user
        serializer = UserSerializer(user)
        data = serializer.data
        
        # Handle student profile if it exists
        if hasattr(user, 'student_profile'):
            from .serializers import StudentSerializer
            try:
                data['student'] = StudentSerializer(user.student_profile).data
            except Exception as e:
                print(f"Error serializing student profile: {e}")
        
        return Response(data)

class StudentRegistrationView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        try:
            # Handle both DRF request.data and regular request.POST
            data = getattr(request, 'data', request.POST)
            files = getattr(request, 'FILES', {})
            
            print(f"Registration request data: {data}")
            print(f"Registration request FILES: {files}")
            
            # Create mutable copy of request.data
            if hasattr(data, 'copy'):
                data = data.copy()
            else:
                data = dict(data)
            
            # Handle photo uploads - check both 'photos' and 'photos[]'
            if 'photos' in files:
                photos = files.getlist('photos') if hasattr(files, 'getlist') else files.get('photos', [])
                if hasattr(data, 'setlist'):
                    data.setlist('photos', photos)
                else:
                    data['photos'] = photos
                print(f"Found {len(photos)} photos")
            elif 'photos[]' in files:
                photos = files.getlist('photos[]') if hasattr(files, 'getlist') else files.get('photos[]', [])
                if hasattr(data, 'setlist'):
                    data.setlist('photos', photos)
                else:
                    data['photos'] = photos
                print(f"Found {len(photos)} photos with [] notation")
            
            print(f"Final data for serializer: {dict(data)}")
            
            serializer = StudentRegistrationSerializer(data=data)
            
            if serializer.is_valid():
                try:
                    student = serializer.save()
                    return Response(
                        {"detail": "Registration successful"},
                        status=status.HTTP_201_CREATED
                    )
                except Exception as e:
                    error_msg = str(e)
                    print(f"Error creating student: {e}")
                    
                    # Handle specific database errors with user-friendly messages
                    if "UNIQUE constraint failed: users_user.username" in error_msg:
                        return Response(
                            {"error": "This matricule number is already registered. Please use a different matricule number."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    elif "UNIQUE constraint failed: users_user.email" in error_msg:
                        return Response(
                            {"error": "This email address is already registered. Please use a different email."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    elif "FOREIGN KEY constraint failed" in error_msg:
                        return Response(
                            {"error": "Invalid academic selection. Please refresh the page and try again."},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    else:
                        return Response(
                            {"error": "Registration failed. Please try again later."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
            
            print(f"Serializer errors: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Exception as e:
            print(f"Unexpected error in registration view: {e}")
            import traceback
            traceback.print_exc()
            return Response(
                {"error": "Registration failed. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# @api_view(['POST'])
# @permission_classes([AllowAny])
# def student_register(request):
#     serializer = StudentRegistrationSerializer(data=request.data)
#     if serializer.is_valid():
#         student = serializer.save()
#         return Response(
#             {"detail": "Registration successful"},
#             status=status.HTTP_201_CREATED
#         )
#     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)        

class StudentLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = StudentLoginSerializer(data=request.data)
        if serializer.is_valid():
            # Get the student from the validated data
            user = serializer.validated_data.get('user')
            if user and hasattr(user, 'student_profile'):
                # Auto-sync courses on login
                from .course_sync_service import auto_sync_on_login
                try:
                    sync_result = auto_sync_on_login(user.student_profile)
                    logger.info(f"Login sync for {user.student_profile.matric_number}: {sync_result}")
                except Exception as e:
                    logger.error(f"Login sync failed for {user.username}: {str(e)}")
            
            return Response(serializer.validated_data)

        return Response(
            serializer.errors,
            status=status.HTTP_401_UNAUTHORIZED
        )
        
class StudentProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = get_student_from_request(request)

        initials = "".join([p[0] for p in student.full_name.split()[:2]]).upper()

        data = {
            "full_name": student.full_name,
            "initials": initials,
            "matric_number": student.matric_number,
            "program": student.program.name,
            "role": "Student",
        }
        return Response(data)
    
class DashboardOverviewView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Import here to avoid circular imports
        from .models_settings import SystemSettings
        from attendance.models import Attendance
        
        student = get_student_from_request(request)
        today = datetime.today()
        weekday = today.strftime('%a').upper()[:3]

        # Get real attendance data
        total_days = Attendance.objects.filter(student=student).count()
        present_days = Attendance.objects.filter(
            student=student, 
            status__in=['present', 'late']
        ).count()

        attendance_percentage = int((present_days / total_days) * 100) if total_days else 0

        # Use the same query as StudentCoursesView
        enrolled_courses = CourseRegistration.objects.filter(student=student, status__in=['approved', 'auto_approved'])
        print(f"[DEBUG] DashboardOverviewView - Student: {student.matric_number}")
        print(f"[DEBUG] Dashboard enrolled courses count: {enrolled_courses.count()}")

        classes_today = TimetableEntry.objects.filter(
            course_offering__students__student=student,
            day_of_week=weekday
        ).count()

        # Get attendance threshold from admin settings
        attendance_threshold = SystemSettings.get_attendance_threshold()
        
        # Get institution info from admin settings
        institution_info = SystemSettings.get_institution_info()

        exam_eligible = 0
        for enrollment in enrolled_courses:
            # Use admin-configured threshold instead of course-specific threshold
            if attendance_percentage >= attendance_threshold:
                exam_eligible += 1

        return Response({
            "overall_attendance_percentage": attendance_percentage,
            "total_courses": enrolled_courses.count(),
            "classes_today": classes_today,
            "exam_eligible_courses": exam_eligible,
            "attendance_threshold": attendance_threshold,  # Include threshold for frontend
            "institution_info": institution_info,  # Include institution info
            "is_exam_eligible": attendance_percentage >= attendance_threshold
        })
        
# students/views.py
class StudentCoursesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student = get_student_from_request(request)
            print(f"[DEBUG] MyCoursesView - Student: {student.matric_number}")
            
            # Get enrollments from CourseRegistration model
            try:
                enrollments = CourseRegistration.objects.filter(
                    student=student,
                    status__in=['approved', 'auto_approved']
                ).select_related(
                    'course_offering__course'
                )
                print(f"[DEBUG] My courses count: {enrollments.count()}")
            except Exception as e:
                print(f"[DEBUG] Error getting enrollments: {e}")
                return Response([])

            results = []
            for enrollment in enrollments:
                try:
                    course = enrollment.course_offering.course
                    
                    # Get real attendance data from attendance app
                    from attendance.models import Attendance, CourseRegistration
                    
                    # Find course registration for this student and course
                    try:
                        course_registration = CourseRegistration.objects.get(
                            student=student,
                            course=course
                        )
                        
                        # Get real attendance records
                        total_classes = Attendance.objects.filter(
                            student=student,
                            course_registration=course_registration
                        ).count()
                        
                        attended_classes = Attendance.objects.filter(
                            student=student,
                            course_registration=course_registration,
                            status__in=['present', 'late']
                        ).count()
                        
                    except CourseRegistration.DoesNotExist:
                        # No course registration found, use zeros
                        total_classes = 0
                        attended_classes = 0
                    
                    # Calculate real attendance percentage
                    attendance_percentage = int((attended_classes / total_classes) * 100) if total_classes > 0 else 0

                    results.append({
                        "id": enrollment.id,
                        "course_code": course.code,
                        "title": course.title,
                        "credits": course.credit_units,
                        "semester": enrollment.course_offering.get_semester_display(),
                        "instructor": enrollment.course_offering.instructor_name,
                        "attendance_percentage": attendance_percentage,
                        "exam_eligible": attendance_percentage >= course.attendance_threshold,
                        "enrollment_date": enrollment.registered_at.strftime("%Y-%m-%d")
                    })
                except Exception as e:
                    print(f"[DEBUG] Error processing enrollment: {e}")
                    continue

            print(f"[DEBUG] Returning {len(results)} courses")
            return Response(results)
        except Exception as e:
            print(f"[DEBUG] StudentCoursesView error: {e}")
            return Response([])
# students/views.py
class StudentTimetableView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student = get_student_from_request(request)
            
            try:
                entries = TimetableEntry.objects.filter(
                    course_offering__students__student=student
                ).select_related(
                    'course_offering__course'
                )
            except:
                return Response([])

            data = []
            for entry in entries:
                try:
                    data.append({
                        "id": entry.id,
                        "day": entry.get_day_of_week_display(),
                        "course": entry.course_offering.course.code,
                        "start": entry.start_time.strftime("%H:%M"),
                        "end": entry.end_time.strftime("%H:%M"),
                        "room": entry.room,
                        "instructor": entry.course_offering.instructor_name,
                    })
                except Exception as e:
                    continue

            return Response(data)
        except Exception as e:
            return Response([])

# New Student Timetable View for the new Department Timetable system
class NewStudentTimetableView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student = get_student_from_request(request)

            # Auto-sync courses to ensure consistency
            from .course_sync_service import full_course_sync
            try:
                sync_result = full_course_sync(student)
                logger.info(f"Timetable sync for {student.matric_number}: {sync_result}")
            except Exception as e:
                logger.error(f"Timetable sync failed for {student.matric_number}: {str(e)}")

            # Get student's department to find relevant timetable
            if not student.department:
                return Response([])

            # Find the department timetable
            try:
                department_timetable = DepartmentTimetable.objects.get(department=student.department)
            except DepartmentTimetable.DoesNotExist:
                return Response([])

            # Get all timetable slots for this department that are associated with the student's enrolled courses
            # First, get all courses the student is enrolled in from BOTH systems
            enrolled_course_ids = set()
            
            # From CourseRegistration (direct registration system)
            course_registration_ids = CourseRegistration.objects.filter(
                student=student,
                status__in=['approved', 'auto_approved']
            ).values_list('course_offering__course__id', flat=True)
            enrolled_course_ids.update(course_registration_ids)
            
            # From StudentCourseSelection (timetable system)
            course_selection_ids = StudentCourseSelection.objects.filter(
                student=student,
                is_offered=True,
                is_approved=True
            ).values_list('course__id', flat=True)
            enrolled_course_ids.update(course_selection_ids)

            # Get timetable slots that match the student's enrolled courses
            slots = TimetableSlot.objects.filter(
                timetable=department_timetable,
                course__in=enrolled_course_ids
            ).select_related(
                'course', 'lecturer', 'lecturer__user', 'level'
            )

            data = []
            for slot in slots:
                data.append({
                    "id": slot.id,
                    "day": slot.get_day_of_week_display(),
                    "course_code": slot.course.code,
                    "course_title": slot.course.title,
                    "start_time": slot.start_time.strftime("%H:%M"),
                    "end_time": slot.end_time.strftime("%H:%M"),
                    "venue": slot.venue,
                    "lecturer_name": f"{slot.lecturer.user.first_name} {slot.lecturer.user.last_name}".strip(),
                    "lecturer_employee_id": slot.lecturer.employee_id,
                    "level_name": slot.level.name
                })

            return Response(data)
        except Exception as e:
            logger.error(f"Error in NewStudentTimetableView: {str(e)}")
            return Response([], status=500)

# Student Timetable View by Level
class StudentTimetableByLevelView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, level_id):
        try:
            student = get_student_from_request(request)

            # Verify that the level belongs to the student's department
            try:
                level = Level.objects.get(id=level_id, department=student.department)
            except Level.DoesNotExist:
                return Response({"error": "Level not found or doesn't belong to your department"}, status=404)

            # Find the department timetable
            try:
                department_timetable = DepartmentTimetable.objects.get(department=student.department)
            except DepartmentTimetable.DoesNotExist:
                return Response([])

            # Get timetable slots for this specific level
            slots = TimetableSlot.objects.filter(
                timetable=department_timetable,
                level=level
            ).select_related(
                'course', 'lecturer', 'lecturer__user'
            )

            data = []
            for slot in slots:
                data.append({
                    "id": slot.id,
                    "day": slot.get_day_of_week_display(),
                    "course_code": slot.course.code,
                    "course_title": slot.course.title,
                    "start_time": slot.start_time.strftime("%H:%M"),
                    "end_time": slot.end_time.strftime("%H:%M"),
                    "venue": slot.venue,
                    "lecturer_name": f"{slot.lecturer.user.first_name} {slot.lecturer.user.last_name}".strip(),
                    "lecturer_employee_id": slot.lecturer.employee_id,
                    "level_name": slot.level.name
                })

            return Response(data)
        except Exception as e:
            logger.error(f"Error in StudentTimetableByLevelView: {str(e)}")
            return Response([], status=500)

# Student Timetable View by Department
class StudentTimetableByDepartmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, department_id):
        try:
            student = get_student_from_request(request)

            # Verify that the department matches the student's department
            if str(student.department.id) != department_id:
                return Response({"error": "Unauthorized access to department timetable"}, status=403)

            # Find the department timetable
            try:
                department_timetable = DepartmentTimetable.objects.get(department_id=department_id)
            except DepartmentTimetable.DoesNotExist:
                return Response([])

            # Get all timetable slots for this department
            slots = TimetableSlot.objects.filter(
                timetable=department_timetable
            ).select_related(
                'course', 'lecturer', 'lecturer__user', 'level'
            )

            data = []
            for slot in slots:
                data.append({
                    "id": slot.id,
                    "day": slot.get_day_of_week_display(),
                    "course_code": slot.course.code,
                    "course_title": slot.course.title,
                    "start_time": slot.start_time.strftime("%H:%M"),
                    "end_time": slot.end_time.strftime("%H:%M"),
                    "venue": slot.venue,
                    "lecturer_name": f"{slot.lecturer.user.first_name} {slot.lecturer.user.last_name}".strip(),
                    "lecturer_employee_id": slot.lecturer.employee_id,
                    "level_name": slot.level.name
                })

            return Response(data)
        except Exception as e:
            logger.error(f"Error in StudentTimetableByDepartmentView: {str(e)}")
            return Response([], status=500)

class AttendanceSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            student = get_student_from_request(request)
            
            # Import the correct Attendance model from attendance app
            from attendance.models import Attendance
            
            try:
                total = Attendance.objects.filter(student=student).count()
                present = Attendance.objects.filter(student=student, status='present').count()
                late = Attendance.objects.filter(student=student, status='late').count()
                absent = Attendance.objects.filter(student=student, status='absent').count()
            except Exception as query_error:
                # If no attendance records, return zeros
                total = present = late = absent = 0

            percentage = int((present + late) / total * 100) if total else 0

            return Response({
                "present": present,
                "late": late,
                "absent": absent,
                "overall_percentage": percentage
            })
        except Exception as e:
            return Response({
                "present": 0,
                "late": 0,
                "absent": 0,
                "overall_percentage": 0
            })
        
class AvailableCoursesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = get_student_from_request(request)
        print(f"[DEBUG] AvailableCoursesView - Student: {student.matric_number}")
        print(f"[DEBUG] Department: {student.department.name}")

        registered_ids = CourseRegistration.objects.filter(
            student=student
        ).values_list('course_id', flat=True)

        offerings = CourseOffering.objects.filter(
            course__department=student.department
        ).exclude(id__in=registered_ids).select_related('course')
        
        print(f"[DEBUG] Available courses count: {offerings.count()}")

        data = []
        for o in offerings:
            data.append({
                "id": o.id,
                "course_code": o.course.code,
                "title": o.course.title,
                "credits": o.course.credit_units,
                "semester": o.get_semester_display(),
                "instructor": o.instructor_name,
            })

        return Response(data)        

class RegisterCourseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        student = get_student_from_request(request)
        offering_id = request.data.get("course_offering_id")

        if not offering_id:
            raise ValidationError("course_offering_id is required.")

        offering = CourseOffering.objects.filter(
            id=offering_id,
            course__department=student.department
        ).first()

        if not offering:
            raise ValidationError("Invalid course offering.")

        obj, created = CourseRegistration.objects.get_or_create(
            student=student,
            course=offering
        )

        if not created:
            raise ValidationError("Already registered for this course.")

        return Response(
            {"message": "Course registered successfully."},
            status=201
        )        
        
class AttendanceHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = get_student_from_request(request)
        course_code = request.query_params.get("course_code")
        month = request.query_params.get("month")  # YYYY-MM

        if not course_code:
            raise ValidationError("course_code is required.")

        # Get real attendance data from attendance app
        from attendance.models import Attendance, CourseRegistration
        
        try:
            # Find the course
            from courses.models import Course
            course = Course.objects.get(code=course_code)
            
            # Find course registration
            course_registration = CourseRegistration.objects.get(
                student=student,
                course=course
            )
            
            # Get attendance records
            attendance_qs = Attendance.objects.filter(
                student=student,
                course_registration=course_registration
            )

            if month:
                start = datetime.strptime(month + "-01", "%Y-%m-%d")
                attendance_qs = attendance_qs.filter(
                    date__year=start.year,
                    date__month=start.month
                )

            logs = []
            for att in attendance_qs:
                logs.append({
                    "date": att.date,
                    "status": att.status
                })

            total_records = attendance_qs.count()
            attended_records = attendance_qs.filter(status__in=['present', 'late']).count()
            percentage = int((attended_records / total_records) * 100) if total_records > 0 else 0

            return Response({
                "course": course_code,
                "percentage": percentage,
                "logs": logs
            })
            
        except (Course.DoesNotExist, CourseRegistration.DoesNotExist):
            return Response({
                "course": course_code,
                "percentage": 0,
                "logs": []
            })  
        
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def attendance_summary(request):
    try:
        data = get_attendance_summary(request.user.student_profile)
        return Response(data)
    except Exception as e:
        # Return empty summary if service fails
        return Response([])
    
        
        
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def attendance_history(request):
    from attendance.models import Attendance
    
    records = Attendance.objects.filter(
        student=request.user.student_profile
    ).select_related(
        "course_registration__course",
        "timetable_entry"
    )

    data = []
    for a in records:
        try:
            course_code = a.course_registration.course.code if a.course_registration and a.course_registration.course else 'N/A'
            time_info = 'N/A'
            if a.timetable_entry:
                time_info = f"{a.timetable_entry.start_time} - {a.timetable_entry.end_time}"
            
            data.append({
                "course": course_code,
                "date": a.date,
                "status": a.status,
                "time": time_info
            })
        except Exception:
            continue

    return Response(data)    


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def exam_eligibility(request):
    try:
        summary = get_attendance_summary(request.user.student_profile)
        
        return Response([
            {
                "course": s["course_code"],
                "eligible": s["eligible_for_exam"]
            }
            for s in summary
        ])
    except Exception as e:
        # Return empty eligibility if service fails
        return Response([])

@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def admin_settings(request):
    """Get or update system settings"""
    
    # Import here to avoid circular imports
    from .models_settings import SystemSettings
    
    if request.method == 'GET':
        try:
            settings = SystemSettings.get_settings()
            return Response(settings)
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    
    elif request.method == 'PUT':
        try:
            # Check if user is admin
            if not request.user.is_staff:
                return Response({'error': 'Admin permissions required'}, status=403)
            
            # Update settings
            success = SystemSettings.update_settings(request.data, updated_by=request.user)
            
            if success:
                # Get updated settings
                updated_settings = SystemSettings.get_settings()
                return Response({
                    'message': 'Settings updated successfully',
                    'settings': updated_settings
                })
            else:
                return Response({'error': 'Failed to update settings'}, status=500)
                
        except Exception as e:
            return Response({'error': str(e)}, status=500)
    
    

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def detailed_attendance_history(request):
    """Get detailed attendance history for student"""
    try:
        student = get_student_from_request(request)
        course_code = request.GET.get('course_code')
        month = request.GET.get('month')  # YYYY-MM format
        
        # Import the correct Attendance model from attendance app
        from attendance.models import Attendance
        
        # Start with all attendance records for the student
        attendance_qs = Attendance.objects.filter(
            student=student
        ).select_related(
            'course_registration__course',
            'timetable_entry'
        ).order_by('-date', '-recorded_at')
        
        # Filter by course if specified
        if course_code:
            attendance_qs = attendance_qs.filter(
                course_registration__course__code=course_code
            )
        
        # Filter by month if specified
        if month:
            try:
                from datetime import datetime
                year, month_num = month.split('-')
                attendance_qs = attendance_qs.filter(
                    date__year=int(year),
                    date__month=int(month_num)
                )
            except (ValueError, IndexError):
                pass  # Invalid month format, ignore filter
        
        # Build response data
        records = []
        for attendance in attendance_qs:
            try:
                # Get course info safely
                course = attendance.course_registration.course if attendance.course_registration else None
                
                # Get timetable info if available
                timetable_info = None
                if attendance.timetable_entry:
                    timetable_info = {
                        'start_time': attendance.timetable_entry.start_time.strftime('%H:%M'),
                        'end_time': attendance.timetable_entry.end_time.strftime('%H:%M'),
                        'venue': getattr(attendance.timetable_entry, 'room', 'TBA')  # Use 'room' field from TimetableEntry
                    }
                
                records.append({
                    'id': attendance.id,
                    'date': attendance.date.strftime('%Y-%m-%d'),
                    'course_code': course.code if course else 'N/A',
                    'course_title': course.title if course else 'Unknown Course',
                    'status': attendance.status,
                    'recorded_at': attendance.recorded_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'is_manual_override': getattr(attendance, 'is_manual_override', False),
                    'timetable': timetable_info
                })
            except Exception as record_error:
                # Skip problematic records but continue processing
                continue
        
        # Calculate summary stats
        total_records = len(records)
        present_count = len([r for r in records if r['status'] == 'present'])
        late_count = len([r for r in records if r['status'] == 'late'])
        absent_count = len([r for r in records if r['status'] == 'absent'])
        
        attendance_percentage = int((present_count + late_count) / total_records * 100) if total_records > 0 else 0
        
        return Response({
            'records': records,
            'summary': {
                'total': total_records,
                'present': present_count,
                'late': late_count,
                'absent': absent_count,
                'attendance_percentage': attendance_percentage
            },
            'filters': {
                'course_code': course_code,
                'month': month
            }
        })
        
    except Exception as e:
        return Response({
            'records': [],
            'summary': {
                'total': 0,
                'present': 0,
                'late': 0,
                'absent': 0,
                'attendance_percentage': 0
            },
            'error': str(e)
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_settings(request):
    """Get system settings relevant to students (read-only)"""
    
    # Import here to avoid circular imports
    from .models_settings import SystemSettings
    
    try:
        # Get full settings
        all_settings = SystemSettings.get_settings()
        
        # Return only settings relevant to students
        student_relevant_settings = {
            'institution': {
                'name': all_settings['general']['institutionName'],
                'code': all_settings['general']['institutionCode'],
                'academicYear': all_settings['general']['academicYear'],
                'semester': all_settings['general']['semester'],
            },
            'attendance': {
                'threshold': all_settings['attendance']['attendanceThreshold'],
                'lateThreshold': all_settings['attendance']['lateThreshold'],
                'requireFaceRecognition': all_settings['attendance']['requireFaceRecognition'],
            },
            'notifications': {
                'emailEnabled': all_settings['notifications']['emailNotifications'],
                'pushEnabled': all_settings['notifications']['pushNotifications'],
                'lowAttendanceAlerts': all_settings['notifications']['lowAttendanceAlerts'],
                'sessionReminders': all_settings['notifications']['sessionReminders'],
            }
        }
        
        return Response(student_relevant_settings)
        
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_timetable_simple(request):
    """Simple timetable endpoint for students"""
    try:
        student = get_student_from_request(request)
        logger.info(f"Student timetable request from: {student.matric_number}")
        
        # Auto-sync courses to ensure consistency
        from .course_sync_service import full_course_sync
        try:
            sync_result = full_course_sync(student)
            logger.info(f"Simple timetable sync for {student.matric_number}: {sync_result}")
        except Exception as e:
            logger.error(f"Simple timetable sync failed for {student.matric_number}: {str(e)}")
        
        # Get student's department to find relevant timetable
        if not student.department:
            return Response({
                'timetable': [],
                'message': 'No department assigned to student',
                'sync_performed': True
            })

        # Find the department timetable
        try:
            department_timetable = DepartmentTimetable.objects.get(department=student.department)
        except DepartmentTimetable.DoesNotExist:
            return Response({
                'timetable': [],
                'message': 'No timetable available for your department',
                'sync_performed': True
            })

        # Get all courses the student is enrolled in from BOTH systems
        enrolled_course_ids = set()
        
        # From CourseRegistration (direct registration system)
        course_registration_ids = CourseRegistration.objects.filter(
            student=student,
            status__in=['approved', 'auto_approved']
        ).values_list('course_offering__course__id', flat=True)
        enrolled_course_ids.update(course_registration_ids)
        
        # From StudentCourseSelection (timetable system)
        from .models import StudentCourseSelection
        course_selection_ids = StudentCourseSelection.objects.filter(
            student=student,
            is_offered=True,
            is_approved=True
        ).values_list('course__id', flat=True)
        enrolled_course_ids.update(course_selection_ids)

        # Get timetable slots that match the student's enrolled courses
        slots = TimetableSlot.objects.filter(
            timetable=department_timetable,
            course__in=enrolled_course_ids
        ).select_related(
            'course', 'lecturer', 'lecturer__user', 'level'
        )

        timetable_data = []
        for slot in slots:
            timetable_data.append({
                "id": slot.id,
                "day": slot.get_day_of_week_display(),
                "course_code": slot.course.code,
                "course_title": slot.course.title,
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
                "venue": slot.venue,
                "lecturer_name": f"{slot.lecturer.user.first_name} {slot.lecturer.user.last_name}".strip(),
                "lecturer_employee_id": slot.lecturer.employee_id,
                "level_name": slot.level.name
            })
        
        return Response({
            'timetable': timetable_data,
            'message': f'Found {len(timetable_data)} timetable entries',
            'sync_performed': True
        })
        
    except AuthenticationFailed as e:
        # Let DRF handle authentication errors properly
        raise e
    except Exception as e:
        logger.error(f"Error in get_student_timetable_simple: {str(e)}")
        return Response({
            'timetable': [],
            'error': str(e),
            'sync_performed': False
        }, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sync_student_courses(request):
    """Manual course synchronization endpoint for students"""
    try:
        student = get_student_from_request(request)
        
        from .course_sync_service import full_course_sync
        sync_result = full_course_sync(student)
        
        return Response({
            'message': 'Course synchronization completed',
            'sync_result': sync_result,
            'student': student.matric_number
        })
        
    except Exception as e:
        logger.error(f"Manual course sync failed: {str(e)}")
        return Response({
            'error': f'Course synchronization failed: {str(e)}'
        }, status=500)