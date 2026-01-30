"""
Student Course Registration API Views

Provides REST API endpoints for students to:
- Browse available courses for registration
- Register for courses (direct registration)
- View their approved courses (My Courses)
- View pending registrations
- Cancel pending registrations
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied

from students.models import Student
from courses.models import Course, Level
from students.course_selection_service import (
    get_available_courses_for_registration,
    get_my_courses,
    get_pending_registrations
)
from students.direct_registration_service import (
    register_course_directly,
    cancel_pending_registration
)


class AvailableCoursesView(APIView):
    """
    GET /api/students/courses/available/
    Lists all courses in student's department available for registration.
    Excludes courses already in "My Courses" (approved or pending).
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Student profile not found")
        
        # Debug logging
        print(f"[DEBUG] AvailableCoursesView - Student: {student.matric_number}")
        print(f"[DEBUG] Department: {student.department.name if student.department else 'None'}")
        
        available_courses = get_available_courses_for_registration(student)
        
        print(f"[DEBUG] Available courses count: {available_courses.count()}")
        
        courses_data = [
            {
                'id': course.id,
                'code': course.code,
                'title': course.title,
                'description': getattr(course, 'description', ''),
                'level': course.level,  # level is a CharField, not ForeignKey
                'department': course.department.name,
                'credits': course.credit_units  # Use credit_units from Course model
            }
            for course in available_courses
        ]
        
        print(f"[DEBUG] Returning {len(courses_data)} courses")
        
        return Response({'courses': courses_data})


class CourseRegistrationView(APIView):
    """
    POST /api/students/courses/register/
    Creates a pending course registration (requires admin approval).
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Student profile not found")
        
        course_id = request.data.get('course_id')
        if not course_id:
            raise ValidationError({'course_id': 'This field is required'})
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            raise NotFound("Course not found")
        
        # Determine the Level (ForeignKey) for the course registration
        # Use the student's current level selection
        level = None
        if hasattr(student, 'level_selection') and student.level_selection:
            level = student.level_selection.level
        else:
            # Fallback: try to find a level in the student's department
            level = Level.objects.filter(department=student.department).first()
        
        if not level:
            raise ValidationError("Unable to determine course level. Please select your level first.")
        
        try:
            selection = register_course_directly(student, course, level)
            
            return Response({
                'id': selection.id,
                'course': {
                    'id': course.id,
                    'code': course.code,
                    'title': course.title,
                    'credits': course.credit_units  # Use credit_units from Course model
                },
                'status': 'pending',
                'message': 'Registration submitted successfully. Awaiting admin approval.',
                'created_at': selection.created_at.isoformat()
            }, status=status.HTTP_201_CREATED)
            
        except DjangoValidationError as e:
            raise ValidationError({'error': str(e), 'code': 'DUPLICATE_REGISTRATION'})


class MyCoursesView(APIView):
    """
    GET /api/students/courses/
    Retrieves all approved courses (My Courses view).
    Combines timetable courses (is_offered=True, is_approved=True) 
    and approved direct registrations (is_approved=True).
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Student profile not found")
        
        # Debug logging
        print(f"[DEBUG] MyCoursesView - Student: {student.matric_number}")
        
        my_courses = get_my_courses(student)
        
        print(f"[DEBUG] My courses count: {my_courses.count()}")
        
        courses_data = []
        for selection in my_courses:
            # Determine source: timetable if from student's selected level, otherwise direct registration
            source = 'timetable'
            if hasattr(student, 'level_selection') and student.level_selection:
                if selection.level.id != student.level_selection.level.id:
                    source = 'registration'
            else:
                source = 'registration'
            
            courses_data.append({
                'id': selection.course.id,
                'course_id': selection.course.id,
                'code': selection.course.code,
                'course_code': selection.course.code,
                'title': selection.course.title,
                'course_title': selection.course.title,
                'credits': selection.course.credit_units,  # Use credit_units from Course model
                'level': selection.level.name,
                'source': source,
                'is_approved': selection.is_approved,
                'approved_at': selection.updated_at.isoformat()
            })
        
        print(f"[DEBUG] Returning {len(courses_data)} courses")
        
        return Response({'courses': courses_data})


class PendingRegistrationsView(APIView):
    """
    GET /api/students/courses/pending/
    Retrieves pending registrations (direct registrations awaiting admin approval).
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Student profile not found")
        
        pending = get_pending_registrations(student)
        
        pending_data = [
            {
                'id': selection.id,
                'course_id': selection.course.id,
                'code': selection.course.code,
                'course_code': selection.course.code,
                'title': selection.course.title,
                'course_title': selection.course.title,
                'credits': selection.course.credit_units,  # Use credit_units from Course model
                'level': selection.level.name,
                'submitted_at': selection.created_at.isoformat(),
                'status': 'pending'
            }
            for selection in pending
        ]
        
        return Response({'pending_registrations': pending_data})


class CancelRegistrationView(APIView):
    """
    DELETE /api/students/courses/registration/{id}/
    Cancels a pending registration.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    
    def delete(self, request, registration_id):
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Student profile not found")
        
        try:
            result = cancel_pending_registration(student, registration_id)
            return Response(result)
            
        except DjangoValidationError as e:
            error_msg = str(e)
            if 'approved' in error_msg.lower():
                raise ValidationError({'error': error_msg, 'code': 'ALREADY_APPROVED'})
            else:
                raise ValidationError({'error': error_msg})
