from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import TimetableEntry
from academics.models import Course, CourseOffering
from .serializers import CourseSerializer, CourseOfferingSerializer, TimetableEntrySerializer
from students.models import Student
from attendance.models import Attendance
import logging

logger = logging.getLogger(__name__)

class CourseListView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        courses = Course.objects.select_related('department').all()
        
        data = []
        for course in courses:
            # Get enrollment count
            total_enrolled = sum(
                offering.students.count() 
                for offering in CourseOffering.objects.filter(course=course)
            )
            
            data.append({
                'id': course.id,
                'code': course.code,
                'title': course.title,
                'description': course.description,
                'creditUnits': course.credit_units,
                'department': course.department.name,
                'attendanceThreshold': course.attendance_threshold,
                'enrolledCount': total_enrolled,
            })
        
        return Response(data)

class CourseDetailView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request, course_id):
        course = get_object_or_404(Course, id=course_id)
        
        # Get course offerings
        offerings = CourseOffering.objects.filter(course=course)
        
        # Calculate stats
        total_enrolled = sum(offering.students.count() for offering in offerings)
        
        # Get attendance stats
        course_attendance = Attendance.objects.filter(
            course_registration__course_offering__course=course
        )
        present_count = course_attendance.filter(status='present').count()
        total_count = course_attendance.count()
        avg_attendance = round((present_count / total_count * 100), 1) if total_count > 0 else 0
        
        data = {
            'id': course.id,
            'code': course.code,
            'title': course.title,
            'description': course.description,
            'creditUnits': course.credit_units,
            'department': course.department.name,
            'attendanceThreshold': course.attendance_threshold,
            'enrolledCount': total_enrolled,
            'averageAttendance': avg_attendance,
            'offerings': [
                {
                    'id': offering.id,
                    'semester': offering.get_semester_display(),
                    'academicYear': offering.academic_year,
                    'instructorName': offering.instructor_name,
                    'enrolledStudents': offering.students.count(),
                }
                for offering in offerings
            ]
        }
        
        return Response(data)

class CourseTimetableView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        course_id = request.query_params.get('course_id')
        
        if course_id:
            # Get timetable for specific course
            entries = TimetableEntry.objects.filter(
                course_offering__course_id=course_id
            ).select_related('course_offering__course')
        else:
            # Get all timetable entries
            entries = TimetableEntry.objects.select_related(
                'course_offering__course'
            ).all()
        
        data = []
        for entry in entries:
            data.append({
                'id': entry.id,
                'courseCode': entry.course_offering.course.code,
                'courseName': entry.course_offering.course.title,
                'dayOfWeek': entry.day_of_week,
                'dayName': entry.get_day_of_week_display(),
                'startTime': entry.start_time.strftime('%H:%M'),
                'endTime': entry.end_time.strftime('%H:%M'),
                'room': entry.room,
                'instructor': entry.course_offering.instructor_name,
            })
        
        return Response(data)