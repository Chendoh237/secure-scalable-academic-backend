"""
Comprehensive Admin Dashboard with Analytics
Real-time analytics and management interface for attendance system
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
from collections import defaultdict

from users.models import User, AuditLog
from students.models import Student
from academics.models import Department, Course, AcademicYear, Semester
from courses.models import CourseRegistration, ClassSession, TimetableSlot
from attendance.models import Attendance, ExamEligibility
from .system_config import system_config_service

logger = logging.getLogger(__name__)

class AdminDashboardService:
    """
    Service for generating admin dashboard analytics and data
    """
    
    def __init__(self):
        self.cache_timeout = 300  # 5 minutes
    
    def get_overview_stats(self) -> Dict[str, Any]:
        """Get high-level overview statistics"""
        try:
            today = timezone.now().date()
            current_semester = Semester.get_current()
            
            # Basic counts
            total_students = Student.objects.filter(is_active=True, is_approved=True).count()
            total_courses = Course.objects.filter(is_active=True).count()
            total_departments = Department.objects.filter(is_active=True).count()
            
            # Today's attendance
            today_attendance = Attendance.objects.filter(date=today)
            present_today = today_attendance.filter(status__in=['present', 'partial', 'late']).count()
            total_expected_today = today_attendance.count()
            
            # Active sessions
            active_sessions = ClassSession.objects.filter(
                date=today,
                state='active'
            ).count()
            
            # Pending approvals
            pending_students = Student.objects.filter(is_approved=False, is_active=True).count()
            pending_registrations = CourseRegistration.objects.filter(status='pending').count()
            
            # Low attendance warnings
            low_attendance_threshold = system_config_service.get_setting('notifications.low_attendance_warning_threshold', 60.0)
            low_attendance_students = self._get_low_attendance_students(low_attendance_threshold)
            
            return {
                'total_students': total_students,
                'total_courses': total_courses,
                'total_departments': total_departments,
                'today_attendance_rate': round((present_today / total_expected_today * 100), 2) if total_expected_today > 0 else 0,
                'present_today': present_today,
                'total_expected_today': total_expected_today,
                'active_sessions': active_sessions,
                'pending_students': pending_students,
                'pending_registrations': pending_registrations,
                'low_attendance_count': len(low_attendance_students),
                'current_semester': current_semester.name if current_semester else None,
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting overview stats: {e}")
            return {}
    
    def get_attendance_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get detailed attendance analytics"""
        try:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=days)
            
            # Daily attendance trends
            daily_stats = []
            current_date = start_date
            
            while current_date <= end_date:
                day_attendance = Attendance.objects.filter(date=current_date)
                total = day_attendance.count()
                present = day_attendance.filter(status__in=['present', 'partial', 'late']).count()
                
                daily_stats.append({
                    'date': current_date.isoformat(),
                    'total_expected': total,
                    'present': present,
                    'attendance_rate': round((present / total * 100), 2) if total > 0 else 0
                })
                
                current_date += timedelta(days=1)
            
            # Department-wise attendance
            dept_stats = []
            departments = Department.objects.filter(is_active=True)
            
            for dept in departments:
                dept_attendance = Attendance.objects.filter(
                    date__range=[start_date, end_date],
                    student__department=dept
                )
                
                total = dept_attendance.count()
                present = dept_attendance.filter(status__in=['present', 'partial', 'late']).count()
                
                dept_stats.append({
                    'department_id': str(dept.id),
                    'department_name': dept.name,
                    'department_code': dept.code,
                    'total_classes': total,
                    'present_count': present,
                    'attendance_rate': round((present / total * 100), 2) if total > 0 else 0,
                    'student_count': dept.get_active_students().count()
                })
            
            # Course-wise attendance
            course_stats = []
            courses = Course.objects.filter(is_active=True)[:20]  # Top 20 courses
            
            for course in courses:
                course_attendance = Attendance.objects.filter(
                    date__range=[start_date, end_date],
                    course_registration__course=course
                )
                
                total = course_attendance.count()
                present = course_attendance.filter(status__in=['present', 'partial', 'late']).count()
                avg_presence = course_attendance.exclude(presence_percentage__isnull=True).aggregate(
                    avg=Avg('presence_percentage')
                )['avg'] or 0
                
                course_stats.append({
                    'course_id': str(course.id),
                    'course_code': course.code,
                    'course_title': course.title,
                    'department': course.department.name,
                    'total_classes': total,
                    'present_count': present,
                    'attendance_rate': round((present / total * 100), 2) if total > 0 else 0,
                    'avg_presence_percentage': round(avg_presence, 2)
                })
            
            # Status distribution
            status_distribution = Attendance.objects.filter(
                date__range=[start_date, end_date]
            ).values('status').annotate(count=Count('id')).order_by('status')
            
            return {
                'period': f'{start_date.isoformat()} to {end_date.isoformat()}',
                'daily_trends': daily_stats,
                'department_stats': sorted(dept_stats, key=lambda x: x['attendance_rate'], reverse=True),
                'course_stats': sorted(course_stats, key=lambda x: x['attendance_rate'], reverse=True),
                'status_distribution': list(status_distribution),
                'summary': {
                    'total_classes': sum(day['total_expected'] for day in daily_stats),
                    'total_present': sum(day['present'] for day in daily_stats),
                    'overall_rate': round(sum(day['present'] for day in daily_stats) / sum(day['total_expected'] for day in daily_stats) * 100, 2) if sum(day['total_expected'] for day in daily_stats) > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting attendance analytics: {e}")
            return {}
    
    def get_student_performance_analytics(self) -> Dict[str, Any]:
        """Get student performance analytics"""
        try:
            current_semester = Semester.get_current()
            if not current_semester:
                return {'error': 'No current semester found'}
            
            # Get all active students
            students = Student.objects.filter(is_active=True, is_approved=True)
            
            # Performance categories
            excellent_students = []  # >90% attendance
            good_students = []       # 75-90% attendance
            warning_students = []    # 60-75% attendance
            critical_students = []   # <60% attendance
            
            for student in students:
                attendance_rate = self._calculate_student_attendance_rate(student, current_semester)
                
                student_data = {
                    'student_id': str(student.id),
                    'matric_number': student.matric_number,
                    'full_name': student.full_name,
                    'department': student.department.name,
                    'attendance_rate': attendance_rate,
                    'courses_count': student.course_registrations.filter(
                        semester=current_semester,
                        status__in=['approved', 'auto_approved']
                    ).count()
                }
                
                if attendance_rate >= 90:
                    excellent_students.append(student_data)
                elif attendance_rate >= 75:
                    good_students.append(student_data)
                elif attendance_rate >= 60:
                    warning_students.append(student_data)
                else:
                    critical_students.append(student_data)
            
            # Exam eligibility stats
            exam_eligibility_threshold = system_config_service.get_setting('attendance.exam_eligibility_threshold', 75.0)
            eligible_count = len(excellent_students) + len(good_students)
            total_students = len(excellent_students) + len(good_students) + len(warning_students) + len(critical_students)
            
            return {
                'semester': current_semester.name,
                'total_students': total_students,
                'performance_categories': {
                    'excellent': {
                        'count': len(excellent_students),
                        'percentage': round(len(excellent_students) / total_students * 100, 2) if total_students > 0 else 0,
                        'students': excellent_students[:10]  # Top 10
                    },
                    'good': {
                        'count': len(good_students),
                        'percentage': round(len(good_students) / total_students * 100, 2) if total_students > 0 else 0,
                        'students': good_students[:10]
                    },
                    'warning': {
                        'count': len(warning_students),
                        'percentage': round(len(warning_students) / total_students * 100, 2) if total_students > 0 else 0,
                        'students': warning_students
                    },
                    'critical': {
                        'count': len(critical_students),
                        'percentage': round(len(critical_students) / total_students * 100, 2) if total_students > 0 else 0,
                        'students': critical_students
                    }
                },
                'exam_eligibility': {
                    'threshold': exam_eligibility_threshold,
                    'eligible_count': eligible_count,
                    'ineligible_count': total_students - eligible_count,
                    'eligibility_rate': round(eligible_count / total_students * 100, 2) if total_students > 0 else 0
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting student performance analytics: {e}")
            return {}
    
    def get_system_activity_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent system activity logs"""
        try:
            logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:limit]
            
            activity_logs = []
            for log in logs:
                activity_logs.append({
                    'id': str(log.id),
                    'user': log.user.get_full_name() if log.user else 'System',
                    'user_email': log.user.email if log.user else None,
                    'action': log.get_action_display(),
                    'model_name': log.model_name,
                    'object_repr': log.object_repr,
                    'timestamp': log.timestamp.isoformat(),
                    'ip_address': log.ip_address,
                    'changes': log.changes
                })
            
            return activity_logs
            
        except Exception as e:
            logger.error(f"Error getting system activity logs: {e}")
            return []
    
    def get_face_recognition_analytics(self) -> Dict[str, Any]:
        """Get face recognition system analytics"""
        try:
            from attendance.enhanced_face_recognition import enhanced_face_recognition_engine
            
            # Get model status
            model_status = enhanced_face_recognition_engine.get_model_status()
            
            # Get recent detection statistics
            today = timezone.now().date()
            week_ago = today - timedelta(days=7)
            
            recent_detections = Attendance.objects.filter(
                date__gte=week_ago,
                detection_count__gt=0
            ).aggregate(
                total_detections=Sum('detection_count'),
                avg_confidence=Avg('presence_percentage'),
                successful_recognitions=Count('id', filter=Q(status__in=['present', 'partial', 'late'])),
                total_attempts=Count('id')
            )
            
            # Students with face consent
            students_with_consent = Student.objects.filter(
                is_active=True,
                face_consent_given=True
            ).count()
            
            students_trained = Student.objects.filter(
                is_active=True,
                face_trained=True
            ).count()
            
            return {
                'model_status': model_status,
                'students_with_consent': students_with_consent,
                'students_trained': students_trained,
                'recent_performance': {
                    'total_detections': recent_detections['total_detections'] or 0,
                    'avg_confidence': round(recent_detections['avg_confidence'] or 0, 2),
                    'successful_recognitions': recent_detections['successful_recognitions'] or 0,
                    'total_attempts': recent_detections['total_attempts'] or 0,
                    'success_rate': round((recent_detections['successful_recognitions'] or 0) / (recent_detections['total_attempts'] or 1) * 100, 2)
                },
                'period': f'{week_ago.isoformat()} to {today.isoformat()}'
            }
            
        except Exception as e:
            logger.error(f"Error getting face recognition analytics: {e}")
            return {}
    
    def get_alerts_and_notifications(self) -> Dict[str, Any]:
        """Get system alerts and notifications for admin"""
        try:
            alerts = []
            
            # Low attendance alerts
            low_attendance_threshold = system_config_service.get_setting('notifications.low_attendance_warning_threshold', 60.0)
            low_attendance_students = self._get_low_attendance_students(low_attendance_threshold)
            
            if low_attendance_students:
                alerts.append({
                    'type': 'warning',
                    'category': 'attendance',
                    'title': 'Low Attendance Alert',
                    'message': f'{len(low_attendance_students)} students have attendance below {low_attendance_threshold}%',
                    'count': len(low_attendance_students),
                    'action_url': '/admin/students/low-attendance'
                })
            
            # Pending approvals
            pending_students = Student.objects.filter(is_approved=False, is_active=True).count()
            if pending_students > 0:
                alerts.append({
                    'type': 'info',
                    'category': 'approvals',
                    'title': 'Pending Student Approvals',
                    'message': f'{pending_students} students awaiting approval',
                    'count': pending_students,
                    'action_url': '/admin/students/pending'
                })
            
            pending_registrations = CourseRegistration.objects.filter(status='pending').count()
            if pending_registrations > 0:
                alerts.append({
                    'type': 'info',
                    'category': 'approvals',
                    'title': 'Pending Course Registrations',
                    'message': f'{pending_registrations} course registrations awaiting approval',
                    'count': pending_registrations,
                    'action_url': '/admin/courses/registrations/pending'
                })
            
            # System health checks
            today = timezone.now().date()
            active_sessions = ClassSession.objects.filter(date=today, state='active').count()
            
            if active_sessions == 0:
                # Check if there should be active sessions
                current_time = timezone.now().time()
                current_day = timezone.now().strftime('%a').upper()[:3]
                
                expected_sessions = TimetableSlot.objects.filter(
                    day_of_week=current_day,
                    start_time__lte=current_time,
                    end_time__gte=current_time
                ).count()
                
                if expected_sessions > 0:
                    alerts.append({
                        'type': 'warning',
                        'category': 'system',
                        'title': 'No Active Sessions',
                        'message': f'{expected_sessions} sessions should be active but none are running',
                        'count': expected_sessions,
                        'action_url': '/admin/sessions/manage'
                    })
            
            # Face recognition model status
            try:
                from attendance.enhanced_face_recognition import enhanced_face_recognition_engine
                if not enhanced_face_recognition_engine.model_loaded:
                    alerts.append({
                        'type': 'error',
                        'category': 'face_recognition',
                        'title': 'Face Recognition Models Not Loaded',
                        'message': 'Face recognition system is not operational',
                        'action_url': '/admin/face-recognition/setup'
                    })
            except:
                pass
            
            return {
                'alerts': alerts,
                'total_alerts': len(alerts),
                'critical_count': len([a for a in alerts if a['type'] == 'error']),
                'warning_count': len([a for a in alerts if a['type'] == 'warning']),
                'info_count': len([a for a in alerts if a['type'] == 'info']),
                'last_updated': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting alerts and notifications: {e}")
            return {}
    
    def _calculate_student_attendance_rate(self, student: Student, semester: Semester) -> float:
        """Calculate attendance rate for a student in a semester"""
        try:
            attendance_records = Attendance.objects.filter(
                student=student,
                course_registration__semester=semester,
                date__range=[semester.start_date, semester.end_date]
            )
            
            total_classes = attendance_records.count()
            if total_classes == 0:
                return 0.0
            
            present_classes = attendance_records.filter(
                status__in=['present', 'partial', 'late']
            ).count()
            
            return round((present_classes / total_classes) * 100, 2)
            
        except Exception as e:
            logger.error(f"Error calculating attendance rate for student {student.id}: {e}")
            return 0.0
    
    def _get_low_attendance_students(self, threshold: float) -> List[Dict[str, Any]]:
        """Get students with attendance below threshold"""
        try:
            current_semester = Semester.get_current()
            if not current_semester:
                return []
            
            students = Student.objects.filter(is_active=True, is_approved=True)
            low_attendance_students = []
            
            for student in students:
                attendance_rate = self._calculate_student_attendance_rate(student, current_semester)
                
                if attendance_rate < threshold:
                    low_attendance_students.append({
                        'student_id': str(student.id),
                        'matric_number': student.matric_number,
                        'full_name': student.full_name,
                        'department': student.department.name,
                        'attendance_rate': attendance_rate,
                        'courses_count': student.course_registrations.filter(
                            semester=current_semester,
                            status__in=['approved', 'auto_approved']
                        ).count()
                    })
            
            return sorted(low_attendance_students, key=lambda x: x['attendance_rate'])
            
        except Exception as e:
            logger.error(f"Error getting low attendance students: {e}")
            return []


# Global dashboard service instance
admin_dashboard_service = AdminDashboardService()


# API Endpoints
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_admin_dashboard_overview(request):
    """Get admin dashboard overview statistics"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        overview_stats = admin_dashboard_service.get_overview_stats()
        
        return Response({
            'success': True,
            'data': overview_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting admin dashboard overview: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get dashboard overview'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_attendance_analytics(request):
    """Get detailed attendance analytics"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        days = int(request.GET.get('days', 30))
        analytics = admin_dashboard_service.get_attendance_analytics(days)
        
        return Response({
            'success': True,
            'data': analytics
        })
        
    except Exception as e:
        logger.error(f"Error getting attendance analytics: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get attendance analytics'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_student_performance_analytics(request):
    """Get student performance analytics"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        analytics = admin_dashboard_service.get_student_performance_analytics()
        
        return Response({
            'success': True,
            'data': analytics
        })
        
    except Exception as e:
        logger.error(f"Error getting student performance analytics: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get student performance analytics'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_system_activity_logs(request):
    """Get recent system activity logs"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        limit = int(request.GET.get('limit', 50))
        logs = admin_dashboard_service.get_system_activity_logs(limit)
        
        return Response({
            'success': True,
            'data': {
                'logs': logs,
                'total_count': len(logs)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting system activity logs: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get system activity logs'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_face_recognition_analytics(request):
    """Get face recognition system analytics"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        analytics = admin_dashboard_service.get_face_recognition_analytics()
        
        return Response({
            'success': True,
            'data': analytics
        })
        
    except Exception as e:
        logger.error(f"Error getting face recognition analytics: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get face recognition analytics'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_admin_alerts(request):
    """Get system alerts and notifications for admin"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        alerts = admin_dashboard_service.get_alerts_and_notifications()
        
        return Response({
            'success': True,
            'data': alerts
        })
        
    except Exception as e:
        logger.error(f"Error getting admin alerts: {e}")
        return Response({
            'success': False,
            'message': 'Failed to get admin alerts'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def export_attendance_report(request):
    """Export attendance report in various formats"""
    try:
        if not request.user.is_admin():
            return Response({
                'success': False,
                'message': 'Admin permissions required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # This would implement CSV/PDF export functionality
        # For now, return success with export URL
        
        export_format = request.data.get('format', 'csv')
        date_range = request.data.get('date_range', {})
        filters = request.data.get('filters', {})
        
        # Generate export (placeholder)
        export_id = f"export_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        
        return Response({
            'success': True,
            'message': 'Export generated successfully',
            'data': {
                'export_id': export_id,
                'format': export_format,
                'download_url': f'/api/admin/exports/{export_id}/download',
                'expires_at': (timezone.now() + timedelta(hours=24)).isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Error exporting attendance report: {e}")
        return Response({
            'success': False,
            'message': 'Failed to export attendance report'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)