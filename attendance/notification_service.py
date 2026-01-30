"""
Real-time attendance notification service
Handles creating and broadcasting attendance notifications when attendance is marked
"""
import logging
from typing import Dict, List, Optional, Any
from django.contrib.auth import get_user_model
from django.utils import timezone
from notifications.models import Notification
from students.models import Student
from .models import Attendance

User = get_user_model()
logger = logging.getLogger(__name__)


class AttendanceNotificationService:
    """Service for managing real-time attendance notifications"""
    
    @staticmethod
    def create_attendance_notification(
        attendance_record: Attendance,
        notification_type: str = 'attendance'
    ) -> Dict[str, Any]:
        """
        Create notifications when attendance is marked
        
        Args:
            attendance_record: The attendance record that was created/updated
            notification_type: Type of notification ('attendance', 'success', 'warning')
            
        Returns:
            Dict containing notification details and recipients
        """
        try:
            student = attendance_record.student
            course_registration = attendance_record.course_registration
            course = course_registration.course
            
            # Determine notification details based on attendance status
            status_config = {
                'present': {
                    'title': f'✅ Attendance Marked - {student.full_name}',
                    'message': f'{student.full_name} ({student.matric_number}) marked present for {course.code} - {course.title}',
                    'icon': 'check-circle',
                    'type': 'success'
                },
                'late': {
                    'title': f'⏰ Late Arrival - {student.full_name}',
                    'message': f'{student.full_name} ({student.matric_number}) marked late for {course.code} - {course.title}',
                    'icon': 'clock',
                    'type': 'warning'
                },
                'absent': {
                    'title': f'❌ Absent - {student.full_name}',
                    'message': f'{student.full_name} ({student.matric_number}) marked absent for {course.code} - {course.title}',
                    'icon': 'x-circle',
                    'type': 'error'
                }
            }
            
            config = status_config.get(attendance_record.status, status_config['present'])
            
            # Create notification data
            notification_data = {
                'title': config['title'],
                'message': config['message'],
                'description': f'Course: {course.code} - {course.title}\nTime: {timezone.now().strftime("%H:%M:%S")}\nDate: {attendance_record.date.strftime("%Y-%m-%d")}',
                'notification_type': config['type'],
                'icon': config['icon'],
                'link': f'/admin/attendance/{attendance_record.id}/',
                'metadata': {
                    'student_id': student.id,
                    'student_matric': student.matric_number,
                    'course_id': course.id,
                    'course_code': course.code,
                    'attendance_id': attendance_record.id,
                    'attendance_status': attendance_record.status,
                    'timestamp': timezone.now().isoformat()
                }
            }
            
            # Create notifications for different user types
            notifications_created = []
            
            # 1. Admin users notification
            admin_users = User.objects.filter(role__in=['admin', 'super_admin', 'institution_admin', 'department_admin'], is_active=True)
            for admin_user in admin_users:
                admin_notification = Notification.objects.create(
                    recipient=admin_user,
                    title=notification_data['title'],
                    message=notification_data['message'],
                    description=notification_data['description'],
                    notification_type=notification_data['notification_type'],
                    icon=notification_data['icon'],
                    link=notification_data['link']
                )
                notifications_created.append({
                    'id': admin_notification.id,
                    'recipient_type': 'admin',
                    'recipient_id': admin_user.id,
                    'recipient_name': admin_user.get_full_name() or admin_user.username
                })
            
            # 2. Student notification (for the student whose attendance was marked)
            if hasattr(student, 'user') and student.user:
                student_title = f'📚 Your Attendance - {course.code}'
                student_message = f'Your attendance has been marked as "{attendance_record.status.title()}" for {course.code} - {course.title}'
                
                student_notification = Notification.objects.create(
                    recipient=student.user,
                    title=student_title,
                    message=student_message,
                    description=f'Status: {attendance_record.status.title()}\nTime: {timezone.now().strftime("%H:%M:%S")}\nDate: {attendance_record.date.strftime("%Y-%m-%d")}',
                    notification_type=config['type'],
                    icon=config['icon'],
                    link='/student/attendance/'
                )
                notifications_created.append({
                    'id': student_notification.id,
                    'recipient_type': 'student',
                    'recipient_id': student.user.id,
                    'recipient_name': student.full_name
                })
            
            # 3. Lecturer notification (if available)
            if hasattr(attendance_record, 'timetable_entry') and attendance_record.timetable_entry:
                timetable_entry = attendance_record.timetable_entry
                if hasattr(timetable_entry, 'lecturer') and timetable_entry.lecturer and hasattr(timetable_entry.lecturer, 'user'):
                    lecturer_title = f'👨‍🏫 Student Attendance - {course.code}'
                    lecturer_message = f'{student.full_name} marked {attendance_record.status} in your {course.code} class'
                    
                    lecturer_notification = Notification.objects.create(
                        recipient=timetable_entry.lecturer.user,
                        title=lecturer_title,
                        message=lecturer_message,
                        description=f'Student: {student.full_name} ({student.matric_number})\nStatus: {attendance_record.status.title()}\nTime: {timezone.now().strftime("%H:%M:%S")}',
                        notification_type=config['type'],
                        icon=config['icon'],
                        link=f'/lecturer/attendance/{course.id}/'
                    )
                    notifications_created.append({
                        'id': lecturer_notification.id,
                        'recipient_type': 'lecturer',
                        'recipient_id': timetable_entry.lecturer.user.id,
                        'recipient_name': timetable_entry.lecturer.user.get_full_name()
                    })
            
            logger.info(f"Created {len(notifications_created)} attendance notifications for {student.matric_number} - {attendance_record.status}")
            
            return {
                'success': True,
                'attendance_record': {
                    'id': attendance_record.id,
                    'student': student.full_name,
                    'matric_number': student.matric_number,
                    'course': course.code,
                    'status': attendance_record.status,
                    'timestamp': timezone.now().isoformat()
                },
                'notifications_created': notifications_created,
                'notification_data': notification_data
            }
            
        except Exception as e:
            logger.error(f"Error creating attendance notification: {e}")
            return {
                'success': False,
                'error': str(e),
                'attendance_record': {
                    'id': attendance_record.id if attendance_record else None,
                    'status': attendance_record.status if attendance_record else None
                }
            }
    
    @staticmethod
    def get_recent_attendance_notifications(
        user: User,
        limit: int = 10,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get recent attendance notifications for a user
        
        Args:
            user: User to get notifications for
            limit: Maximum number of notifications to return
            hours: Number of hours to look back
            
        Returns:
            List of recent attendance notifications
        """
        try:
            since = timezone.now() - timezone.timedelta(hours=hours)
            
            notifications = Notification.objects.filter(
                recipient=user,
                notification_type__in=['attendance', 'success', 'warning', 'error'],
                created_at__gte=since
            ).order_by('-created_at')[:limit]
            
            return [
                {
                    'id': notification.id,
                    'title': notification.title,
                    'message': notification.message,
                    'description': notification.description,
                    'type': notification.notification_type,
                    'icon': notification.icon,
                    'link': notification.link,
                    'is_read': notification.is_read,
                    'created_at': notification.created_at.isoformat(),
                    'read_at': notification.read_at.isoformat() if notification.read_at else None
                }
                for notification in notifications
            ]
            
        except Exception as e:
            logger.error(f"Error getting recent attendance notifications: {e}")
            return []
    
    @staticmethod
    def mark_attendance_notifications_read(
        user: User,
        notification_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Mark attendance notifications as read
        
        Args:
            user: User whose notifications to mark as read
            notification_ids: Specific notification IDs to mark (if None, marks all unread)
            
        Returns:
            Dict with operation results
        """
        try:
            query = Notification.objects.filter(
                recipient=user,
                notification_type__in=['attendance', 'success', 'warning', 'error'],
                is_read=False
            )
            
            if notification_ids:
                query = query.filter(id__in=notification_ids)
            
            count = query.count()
            for notification in query:
                notification.mark_as_read()
            
            return {
                'success': True,
                'marked_count': count,
                'message': f'Marked {count} attendance notifications as read'
            }
            
        except Exception as e:
            logger.error(f"Error marking attendance notifications as read: {e}")
            return {
                'success': False,
                'error': str(e),
                'marked_count': 0
            }
    
    @staticmethod
    def get_attendance_summary_for_notifications(
        hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get attendance summary for notification dashboard
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dict with attendance summary data
        """
        try:
            since = timezone.now() - timezone.timedelta(hours=hours)
            
            recent_attendance = Attendance.objects.filter(
                recorded_at__gte=since
            ).select_related('student', 'course_registration__course')
            
            summary = {
                'total_records': recent_attendance.count(),
                'present_count': recent_attendance.filter(status='present').count(),
                'late_count': recent_attendance.filter(status='late').count(),
                'absent_count': recent_attendance.filter(status='absent').count(),
                'unique_students': recent_attendance.values('student').distinct().count(),
                'unique_courses': recent_attendance.values('course_registration__course').distinct().count(),
                'time_period': f'Last {hours} hours',
                'last_updated': timezone.now().isoformat()
            }
            
            # Calculate attendance rate
            total_present_late = summary['present_count'] + summary['late_count']
            if summary['total_records'] > 0:
                summary['attendance_rate'] = round((total_present_late / summary['total_records']) * 100, 1)
            else:
                summary['attendance_rate'] = 0.0
            
            return {
                'success': True,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Error getting attendance summary for notifications: {e}")
            return {
                'success': False,
                'error': str(e),
                'summary': {}
            }