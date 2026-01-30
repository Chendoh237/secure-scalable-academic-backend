"""
Student Dashboard with Course Selection and Notifications
Comprehensive student interface for attendance management system
"""

from django.db.models import Count, Avg, Q, F, Sum, Max, Min
from django.utils import timezone
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
import logging

from users.models import User
from students.models import Student
from academics.models import Department, Course, AcademicYear, Semester
from courses.models import CourseRegistration, ClassSession, TimetableSlot, Level
from attendance.models import Attendance, ExamEligibility
from administration.system_config import system_config_service

logger = logging.getLogger(__name__)

class StudentDashboardService:
    """
    Service for student dashboard functionality
    """
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def get_student_overview(self, student: Student) -> Dict[str, Any]:
        """Get student dashboard overview"""
        try:
            current_semester = Semester.get_current()
            if not current_semester:
                return {'error': 'No current semester found'}
            
            # Basic student info
            student_info = {
                'student_id': str(student.id),
                'matric_number': student.matric_number,
                'full_name': student.full_name,
                'department': student.department.name,
                'department_code': student.department.code,
                'current_level': getattr(student, 'current_level', 100),
                'enrollment_status': getattr(student, 'enrollment_status', 'active'),
                'face_consent_given': getattr(student, 'face_consent_given', False)
            }
            
            # Current semester registrations
            current_registrations = CourseRegistration.objects.filter(
                student=student,
                semester=current_semester
            ).select_related('course')
            
            total_courses = current_registrations.count()
            approved_courses = current_registrations.filter(status__in=['approved', 'auto_approved']).count()
            pending_courses = current_registrations.filter(status='pending').count()
            
            # Attendance summary
            attendance_summary = self._get_student_attendance_summary(student, current_semester)
            
            # Exam eligibility
            exam_eligibility = self._get_exam_eligibility_status(student, current_semester)
            
            # Today's schedule
            today_schedule = self._get_today_schedule(student)
            
            # Recent notifications
            recent_notifications = self._get_recent_notifications(student, limit=5)
            
            return {
                'student_info': student_info,
                'current_semester': {
                    'name': current_semester.name,
                    'start_date': current_semester.start_date.isoformat(),
                    'end_date': current_semester.end_date.isoformat(),
                    'is_current': current_semester.is_current
                },
                'course_summary': {
                    'total_courses': total_courses,
                    'approved_courses': approved_courses,
                    'pending_courses': pending_courses,
                    'registration_status': 'complete' if pending_courses == 0 else 'pending'
                },
                'attendance_summary': attendance_summary,
                'exam_eligibility': exam_eligibility,
                'today_schedule': today_schedule,
                'recent_notifications': recent_notifications,
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting student overview for {student.id}: {e}")
            return {}
    
    def get_student_courses(self, student: Student, semester: Optional[Semester] = None) -> Dict[str, Any]:
        """Get student's course registrations and available courses"""
        try:
            if not semester:
                semester = Semester.get_current()
            
            if not semester:
                return {'error': 'No semester specified'}
            
            # Current registrations
            registrations = CourseRegistration.objects.filter(
                student=student,
                semester=semester
            ).select_related('course', 'approved_by').order_by('course__code')
            
            registered_courses = []
            for reg in registrations:
                course_data = {
                    'registration_id': str(reg.id),
                    'course_id': str(reg.course.id),
                    'course_code': reg.course.code,
                    'course_title': reg.course.title,
                    'credit_units': reg.course.credit_units,
                    'level': reg.course.level,
                    'department': reg.course.department.name,
                    'status': reg.status,
                    'registered_at': reg.registered_at.isoformat(),
                    'approved_at': reg.approved_at.isoformat() if reg.approved_at else None,
                    'approved_by': reg.approved_by.get_full_name() if reg.approved_by else None,
                    'rejection_reason': reg.rejection_reason,
                    'attendance_rate': self._get_course_attendance_rate(student, reg.course, semester)
                }
                registered_courses.append(course_data)
            
            # Available courses for registration
            available_courses = self._get_available_courses_for_student(student, semester)
            
            return {
                'semester': {
                    'name': semester.name,
                    'start_date': semester.start_date.isoformat(),
                    'end_date': semester.end_date.isoformat()
                },
                'registered_courses': registered_courses,
                'available_courses': available_courses,
                'registration_summary': {
                    'total_registered': len(registered_courses),
                    'approved': len([c for c in registered_courses if c['status'] in ['approved', 'auto_approved']]),
                    'pending': len([c for c in registered_courses if c['status'] == 'pending']),
                    'rejected': len([c for c in registered_courses if c['status'] == 'rejected'])
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting student courses for {student.id}: {e}")
            return {}
    
    def get_student_timetable(self, student: Student) -> Dict[str, Any]:
        """Get student's weekly timetable"""
        try:
            current_semester = Semester.get_current()
            if not current_semester:
                return {'error': 'No current semester found'}
            
            # Get approved course registrations
            registrations = CourseRegistration.objects.filter(
                student=student,
                semester=current_semester,
                status__in=['approved', 'auto_approved']
            ).select_related('course')
            
            # Get timetable slots for registered courses
            course_ids = [reg.course.id for reg in registrations]
            timetable_slots = TimetableSlot.objects.filter(
                course_id__in=course_ids,
                timetable__semester=current_semester
            ).select_related('course', 'lecturer', 'level').order_by('day_of_week', 'start_time')
            
            # Organize by day of week
            days_of_week = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
            timetable = {}
            
            for day in days_of_week:
                day_slots = timetable_slots.filter(day_of_week=day)
                timetable[day] = []
                
                for slot in day_slots:
                    slot_data = {
                        'slot_id': str(slot.id),
                        'course_code': slot.course.code,
                        'course_title': slot.course.title,
                        'start_time': slot.start_time.strftime('%H:%M'),
                        'end_time': slot.end_time.strftime('%H:%M'),
                        'duration_minutes': slot.get_duration_minutes(),
                        'venue': slot.venue or 'TBA',
                        'lecturer': slot.lecturer.get_full_name() if slot.lecturer else 'TBA',
                        'session_type': slot.session_type,
                        'level': slot.level.name if slot.level else None
                    }
                    timetable[day].append(slot_data)
            
            # Get today's classes with status
            today = timezone.now().date()
            today_day = timezone.now().strftime('%a').upper()[:3]
            
            today_classes = []
            if today_day in timetable:
                for slot_data in timetable[today_day]:
                    # Check if there's an active session
                    try:
                        slot = TimetableSlot.objects.get(id=slot_data['slot_id'])
                        class_session = ClassSession.objects.get(
                            timetable_slot=slot,
                            date=today
                        )
                        slot_data['session_status'] = class_session.state
                        slot_data['session_id'] = str(class_session.id)
                    except ClassSession.DoesNotExist:
                        slot_data['session_status'] = 'scheduled'
                        slot_data['session_id'] = None
                    
                    # Check attendance status
                    try:
                        attendance = Attendance.objects.get(
                            student=student,
                            course_registration__course_id=slot_data['course_code'].split()[0],  # Extract course from code
                            date=today
                        )
                        slot_data['attendance_status'] = attendance.status
                        slot_data['presence_percentage'] = attendance.presence_percentage
                    except Attendance.DoesNotExist:
                        slot_data['attendance_status'] = 'not_recorded'
                        slot_data['presence_percentage'] = None
                    
                    today_classes.append(slot_data)
            
            return {
                'semester': current_semester.name,
                'timetable': timetable,
                'today_classes': today_classes,
                'total_weekly_hours': sum(
                    sum(slot['duration_minutes'] for slot in day_slots) 
                    for day_slots in timetable.values()
                ) / 60,
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting student timetable for {student.id}: {e}")
            return {}
    
    def get_attendance_history(self, student: Student, days: int = 30) -> Dict[str, Any]:
        """Get student's attendance history"""
        try:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Get attendance records
            attendance_records = Attendance.objects.filter(
                student=student,
                date__range=[start_date, end_date]
            ).select_related('course_registration__course').order_by('-date')
            
            # Organize by date
            daily_attendance = {}
            course_summary = {}
            
            for record in attendance_records:
                date_str = record.date.isoformat()
                course_code = record.course_registration.course.code
                
                # Daily attendance
                if date_str not in daily_attendance:
                    daily_attendance[date_str] = []
                
                daily_attendance[date_str].append({
                    'course_code': course_code,
                    'course_title': record.course_registration.course.title,
                    'status': record.status,
                    'presence_percentage': record.presence_percentage,
                    'presence_duration_minutes': record.presence_duration.total_seconds() / 60 if record.presence_duration else 0,
                    'detection_count': record.detection_count,
                    'recorded_at': record.recorded_at.isoformat(),
                    'is_manual_override': record.is_manual_override
                })
                
                # Course summary
                if course_code not in course_summary:
                    course_summary[course_code] = {
                        'course_title': record.course_registration.course.title,
                        'total_classes': 0,
                        'present': 0,
                        'partial': 0,
                        'late': 0,
                        'absent': 0,
                        'avg_presence_percentage': 0
                    }
                
                course_summary[course_code]['total_classes'] += 1
                course_summary[course_code][record.status] += 1
            
            # Calculate course averages
            for course_code, summary in course_summary.items():
                course_records = attendance_records.filter(course_registration__course__code=course_code)
                avg_presence = course_records.exclude(presence_percentage__isnull=True).aggregate(
                    avg=Avg('presence_percentage')
                )['avg'] or 0
                
                summary['avg_presence_percentage'] = round(avg_presence, 2)
                summary['attendance_rate'] = round(
                    (summary['present'] + summary['partial'] + summary['late']) / summary['total_classes'] * 100, 2
                ) if summary['total_classes'] > 0 else 0
            
            # Overall statistics
            total_classes = attendance_records.count()
            present_classes = attendance_records.filter(status__in=['present', 'partial', 'late']).count()
            overall_rate = round((present_classes / total_classes * 100), 2) if total_classes > 0 else 0
            
            return {
                'period': f'{start_date.isoformat()} to {end_date.isoformat()}',
                'daily_attendance': daily_attendance,
                'course_summary': course_summary,
                'overall_statistics': {
                    'total_classes': total_classes,
                    'present_classes': present_classes,
                    'attendance_rate': overall_rate,
                    'avg_presence_percentage': round(
                        attendance_records.exclude(presence_percentage__isnull=True).aggregate(
                            avg=Avg('presence_percentage')
                        )['avg'] or 0, 2
                    )
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting attendance history for {student.id}: {e}")
            return {}
    
    def register_for_course(self, student: Student, course_id: str, semester: Optional[Semester] = None) -> Dict[str, Any]:
        """Register student for a course"""
        try:
            if not semester:
                semester = Semester.get_current()
            
            if not semester:
                return {'success': False, 'message': 'No current semester found'}
            
            # Get course
            try:
                course = Course.objects.get(id=course_id, is_active=True)
            except Course.DoesNotExist:
                return {'success': False, 'message': 'Course not found'}
            
            # Check if student can register for this course
            if course.department != student.department:
                return {'success': False, 'message': 'Course not available for your department'}
            
            # Check if already registered
            if CourseRegistration.objects.filter(
                student=student,
                course=course,
                semester=semester
            ).exists():
                return {'success': False, 'message': 'Already registered for this course'}
            
            # Check prerequisites
            for prerequisite in course.prerequisites.all():
                if not CourseRegistration.objects.filter(
                    student=student,
                    course=prerequisite,
                    status__in=['approved', 'auto_approved']
                ).exists():
                    return {
                        'success': False, 
                        'message': f'Prerequisite course {prerequisite.code} not completed'
                    }
            
            # Create registration
            registration = CourseRegistration.objects.create(
                student=student,
                course=course,
                semester=semester,
                status='pending'  # Default to pending approval
            )
            
            # Check if should auto-approve
            auto_approve = system_config_service.get_setting('course_registration.auto_approve', True)
            if auto_approve:
                registration.auto_approve()
            
            return {
                'success': True,
                'message': 'Course registration successful',
                'data': {
                    'registration_id': str(registration.id),
                    'course_code': course.code,
                    'course_title': course.title,
                    'status': registration.status,
                    'registered_at': registration.registered_at.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error registering student {student.id} for course {course_id}: {e}")
            return {'success': False, 'message': 'Registration failed due to server error'}
    
    def withdraw_from_course(self, student: Student, registration_id: str) -> Dict[str, Any]:
        """Withdraw student from a course"""
        try:
            # Get registration
            try:
                registration = CourseRegistration.objects.get(
                    id=registration_id,
                    student=student
                )
            except CourseRegistration.DoesNotExist:
                return {'success': False, 'message': 'Registration not found'}
            
            # Check if withdrawal is allowed
            if registration.status == 'withdrawn':
                return {'success': False, 'message': 'Already withdrawn from this course'}
            
            # Update status
            registration.status = 'withdrawn'
            registration.save()
            
            return {
                'success': True,
                'message': 'Successfully withdrawn from course',
                'data': {
                    'registration_id': str(registration.id),
                    'course_code': registration.course.code,
                    'status': registration.status
                }
            }
            
        except Exception as e:
            logger.error(f"Error withdrawing student {student.id} from registration {registration_id}: {e}")
            return {'success': False, 'message': 'Withdrawal failed due to server error'}
    
    def _get_student_attendance_summary(self, student: Student, semester: Semester) -> Dict[str, Any]:
        """Get attendance summary for student in semester"""
        try:
            attendance_records = Attendance.objects.filter(
                student=student,
                course_registration__semester=semester,
                date__range=[semester.start_date, semester.end_date]
            )
            
            total_classes = attendance_records.count()
            if total_classes == 0:
                return {
                    'total_classes': 0,
                    'present': 0,
                    'partial': 0,
                    'late': 0,
                    'absent': 0,
                    'attendance_rate': 0.0,
                    'avg_presence_percentage': 0.0
                }
            
            present = attendance_records.filter(status='present').count()
            partial = attendance_records.filter(status='partial').count()
            late = attendance_records.filter(status='late').count()
            absent = attendance_records.filter(status='absent').count()
            
            attendance_rate = round(((present + partial + late) / total_classes) * 100, 2)
            avg_presence = attendance_records.exclude(presence_percentage__isnull=True).aggregate(
                avg=Avg('presence_percentage')
            )['avg'] or 0
            
            return {
                'total_classes': total_classes,
                'present': present,
                'partial': partial,
                'late': late,
                'absent': absent,
                'attendance_rate': attendance_rate,
                'avg_presence_percentage': round(avg_presence, 2)
            }
            
        except Exception as e:
            logger.error(f"Error getting attendance summary for student {student.id}: {e}")
            return {}
    
    def _get_exam_eligibility_status(self, student: Student, semester: Semester) -> Dict[str, Any]:
        """Get exam eligibility status for student"""
        try:
            threshold = system_config_service.get_setting('attendance.exam_eligibility_threshold', 75.0)
            
            # Get course registrations
            registrations = CourseRegistration.objects.filter(
                student=student,
                semester=semester,
                status__in=['approved', 'auto_approved']
            )
            
            eligibility_status = []
            eligible_courses = 0
            total_courses = registrations.count()
            
            for registration in registrations:
                attendance_rate = self._get_course_attendance_rate(student, registration.course, semester)
                is_eligible = attendance_rate >= threshold
                
                if is_eligible:
                    eligible_courses += 1
                
                eligibility_status.append({
                    'course_code': registration.course.code,
                    'course_title': registration.course.title,
                    'attendance_rate': attendance_rate,
                    'is_eligible': is_eligible,
                    'required_rate': threshold
                })
            
            return {
                'threshold': threshold,
                'total_courses': total_courses,
                'eligible_courses': eligible_courses,
                'ineligible_courses': total_courses - eligible_courses,
                'overall_eligibility_rate': round((eligible_courses / total_courses * 100), 2) if total_courses > 0 else 0,
                'course_eligibility': eligibility_status
            }
            
        except Exception as e:
            logger.error(f"Error getting exam eligibility for student {student.id}: {e}")
            return {}
    
    def _get_course_attendance_rate(self, student: Student, course: Course, semester: Semester) -> float:
        """Get attendance rate for specific course"""
        try:
            course_attendance = Attendance.objects.filter(
                student=student,
                course_registration__course=course,
                course_registration__semester=semester
            )
            
            total = course_attendance.count()
            if total == 0:
                return 0.0
            
            present = course_attendance.filter(status__in=['present', 'partial', 'late']).count()
            return round((present / total) * 100, 2)
            
        except Exception as e:
            logger.error(f"Error getting course attendance rate: {e}")
            return 0.0
    
    def _get_available_courses_for_student(self, student: Student, semester: Semester) -> List[Dict[str, Any]]:
        """Get courses available for student registration"""
        try:
            # Get courses in student's department
            available_courses = Course.objects.filter(
                department=student.department,
                is_active=True
            ).exclude(
                # Exclude already registered courses
                id__in=CourseRegistration.objects.filter(
                    student=student,
                    semester=semester
                ).values_list('course_id', flat=True)
            )
            
            courses_data = []
            for course in available_courses:
                # Check prerequisites
                prerequisites_met = True
                missing_prerequisites = []
                
                for prerequisite in course.prerequisites.all():
                    if not CourseRegistration.objects.filter(
                        student=student,
                        course=prerequisite,
                        status__in=['approved', 'auto_approved']
                    ).exists():
                        prerequisites_met = False
                        missing_prerequisites.append(prerequisite.code)
                
                courses_data.append({
                    'course_id': str(course.id),
                    'course_code': course.code,
                    'course_title': course.title,
                    'credit_units': course.credit_units,
                    'level': course.level,
                    'description': course.description,
                    'prerequisites_met': prerequisites_met,
                    'missing_prerequisites': missing_prerequisites,
                    'can_register': prerequisites_met
                })
            
            return courses_data
            
        except Exception as e:
            logger.error(f"Error getting available courses for student {student.id}: {e}")
            return []
    
    def _get_today_schedule(self, student: Student) -> List[Dict[str, Any]]:
        """Get today's class schedule for student"""
        try:
            today = timezone.now().date()
            current_day = timezone.now().strftime('%a').upper()[:3]
            current_semester = Semester.get_current()
            
            if not current_semester:
                return []
            
            # Get approved registrations
            registrations = CourseRegistration.objects.filter(
                student=student,
                semester=current_semester,
                status__in=['approved', 'auto_approved']
            ).select_related('course')
            
            course_ids = [reg.course.id for reg in registrations]
            
            # Get today's timetable slots
            today_slots = TimetableSlot.objects.filter(
                course_id__in=course_ids,
                day_of_week=current_day
            ).select_related('course', 'lecturer').order_by('start_time')
            
            schedule = []
            for slot in today_slots:
                # Check session status
                try:
                    class_session = ClassSession.objects.get(
                        timetable_slot=slot,
                        date=today
                    )
                    session_status = class_session.state
                    session_id = str(class_session.id)
                except ClassSession.DoesNotExist:
                    session_status = 'scheduled'
                    session_id = None
                
                # Check attendance
                try:
                    attendance = Attendance.objects.get(
                        student=student,
                        course_registration__course=slot.course,
                        date=today
                    )
                    attendance_status = attendance.status
                    presence_percentage = attendance.presence_percentage
                except Attendance.DoesNotExist:
                    attendance_status = 'not_recorded'
                    presence_percentage = None
                
                schedule.append({
                    'slot_id': str(slot.id),
                    'course_code': slot.course.code,
                    'course_title': slot.course.title,
                    'start_time': slot.start_time.strftime('%H:%M'),
                    'end_time': slot.end_time.strftime('%H:%M'),
                    'venue': slot.venue or 'TBA',
                    'lecturer': slot.lecturer.get_full_name() if slot.lecturer else 'TBA',
                    'session_status': session_status,
                    'session_id': session_id,
                    'attendance_status': attendance_status,
                    'presence_percentage': presence_percentage
                })
            
            return schedule
            
        except Exception as e:
            logger.error(f"Error getting today's schedule for student {student.id}: {e}")
            return []
    
    def _get_recent_notifications(self, student: Student, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent notifications for student"""
        try:
            # Import notification service
            from notifications.notification_system import notification_service
            
            # Get actual notifications from the notification system
            notifications = notification_service.get_user_notifications(
                user=student.user,
                unread_only=False,
                limit=limit
            )
            
            # Convert to expected format
            notifications_data = []
            for notification in notifications:
                notifications_data.append({
                    'id': str(notification.id),
                    'type': notification.notification_type,
                    'title': notification.title,
                    'message': notification.message,
                    'timestamp': notification.created_at.isoformat(),
                    'read': notification.is_read,
                    'priority': notification.priority,
                    'action_url': notification.action_url,
                    'action_text': notification.action_text,
                    'expires_at': notification.expires_at.isoformat() if notification.expires_at else None
                })
            
            return notifications_data
            
        except Exception as e:
            logger.error(f"Error getting notifications for student {student.id}: {e}")
            return []


# Global dashboard service instance
student_dashboard_service = StudentDashboardService()


# API Endpoints
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_dashboard_overview(request):
    """Get student dashboard overview"""
    try:
        if not request.user.is_student():
            return Response({
                'success': False,
                'message': 'Student access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        student = request.user.student_profile
        overview = student_dashboard_service.get_student_overview(student)
        
        return Response({
            'success': True,
            'data': overview
        })
        
    except Exception as e:
        logger.error(f"Error getting student dashboard overview: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get dashboard overview'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_courses(request):
    """Get student's courses and registration status"""
    try:
        if not request.user.is_student():
            return Response({
                'success': False,
                'message': 'Student access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        student = request.user.student_profile
        courses = student_dashboard_service.get_student_courses(student)
        
        return Response({
            'success': True,
            'data': courses
        })
        
    except Exception as e:
        logger.error(f"Error getting student courses: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get student courses'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_timetable(request):
    """Get student's weekly timetable"""
    try:
        if not request.user.is_student():
            return Response({
                'success': False,
                'message': 'Student access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        student = request.user.student_profile
        timetable = student_dashboard_service.get_student_timetable(student)
        
        return Response({
            'success': True,
            'data': timetable
        })
        
    except Exception as e:
        logger.error(f"Error getting student timetable: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get student timetable'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_attendance_history(request):
    """Get student's attendance history"""
    try:
        if not request.user.is_student():
            return Response({
                'success': False,
                'message': 'Student access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        student = request.user.student_profile
        days = int(request.GET.get('days', 30))
        
        history = student_dashboard_service.get_attendance_history(student, days)
        
        return Response({
            'success': True,
            'data': history
        })
        
    except Exception as e:
        logger.error(f"Error getting student attendance history: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get attendance history'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_for_course(request):
    """Register student for a course"""
    try:
        if not request.user.is_student():
            return Response({
                'success': False,
                'message': 'Student access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        student = request.user.student_profile
        course_id = request.data.get('course_id')
        
        if not course_id:
            return Response({
                'success': False,
                'message': 'Course ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = student_dashboard_service.register_for_course(student, course_id)
        
        return Response(result)
        
    except Exception as e:
        logger.error(f"Error registering for course: {e}")
        return Response({
            'success': False,
            'message': 'Course registration failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def withdraw_from_course(request):
    """Withdraw student from a course"""
    try:
        if not request.user.is_student():
            return Response({
                'success': False,
                'message': 'Student access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        student = request.user.student_profile
        registration_id = request.data.get('registration_id')
        
        if not registration_id:
            return Response({
                'success': False,
                'message': 'Registration ID is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        result = student_dashboard_service.withdraw_from_course(student, registration_id)
        
        return Response(result)
        
    except Exception as e:
        logger.error(f"Error withdrawing from course: {e}")
        return Response({
            'success': False,
            'message': 'Course withdrawal failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)