from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Student, StudentPhoto
from .serializers import StudentSerializer, StudentPhotoSerializer
from attendance.models import CourseRegistration, Attendance
from courses.models import Course
from academics.models import CourseOffering
from django.db.models import Count, F, Q
from datetime import datetime, timedelta

class StudentCoursesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        student = request.user.student_profile
        
        # Get all course registrations for the student
        registrations = CourseRegistration.objects.filter(
            student=student,
            is_active=True
        ).select_related('course_offering__course')

        # Calculate attendance for each course
        results = []
        for reg in registrations:
            course = reg.course_offering.course
            total_classes = Attendance.objects.filter(
                course_offering=reg.course_offering
            ).count()
            
            attended_classes = Attendance.objects.filter(
                course_offering=reg.course_offering,
                student=student,
                is_present=True
            ).count()
            
            attendance_percentage = 0
            if total_classes > 0:
                attendance_percentage = int((attended_classes / total_classes) * 100)
            
            results.append({
                "id": str(course.id),
                "course_code": course.code,
                "title": course.title,
                "credits": course.credit_units,
                "attendance_percentage": attendance_percentage,
                "exam_eligible": attendance_percentage >= course.attendance_threshold,
                "status": "approved" if reg.is_approved else "pending"
            })
        
        return Response(results)

class AvailableCoursesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Return empty list for now to avoid errors
        return Response([])

class RegisterCourseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        student = request.user.student_profile
        course_id = request.data.get('course_id')
        
        if not course_id:
            return Response(
                {"error": "Course ID is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"error": "Course not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already registered
        if CourseRegistration.objects.filter(
            student=student, 
            course_offering__course=course,
            is_active=True
        ).exists():
            return Response(
                {"error": "Already registered for this course"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get current semester offering
        current_semester = get_current_semester()
        offering = CourseOffering.objects.filter(
            course=course,
            semester=current_semester
        ).first()
        
        if not offering:
            return Response(
                {"error": "No offering available for this course"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check prerequisites
        for prereq in course.prerequisites.all():
            if not CourseRegistration.objects.filter(
                student=student,
                course_offering__course=prereq,
                is_approved=True
            ).exists():
                return Response(
                    {"error": f"Prerequisite not met: {prereq.code}"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Register for the course
        registration = CourseRegistration.objects.create(
            student=student,
            course_offering=offering,
            registered_at=datetime.now(),
            is_approved=not course.needs_approval  # Auto-approve if no approval needed
        )
        
        # Update enrollment count
        offering.current_enrollment += 1
        offering.save()
        
        return Response(
            {"message": "Course registration successful"}, 
            status=status.HTTP_201_CREATED
        )

def get_current_semester():
    # Return None for now since we don't have semester data
    return None
