#!/usr/bin/env python3
"""
Presence Tracking Service

This service handles real-time presence duration tracking for students
during class sessions, calculating accurate attendance based on time spent.
"""

from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.db import transaction
from django.db.models import Q, Count, Avg, Sum
import logging

from .models import Attendance, CourseRegistration
from students.models import Student
from courses.models import TimetableEntry

logger = logging.getLogger(__name__)


class PresenceTrackingService:
    """Service for tracking student presence duration during classes"""
    
    def __init__(self):
        self.active_tracking_sessions = {}  # Track active presence sessions
        self.presence_thresholds = {
            'present': 75.0,    # 75% presence required for "present"
            'partial': 50.0,    # 50% presence required for "partial"
            'late': 25.0        # 25% presence required for "late"
        }
    
    def start_presence_tracking(self, student: Student, course_registration: CourseRegistration, 
                              timetable_entry: Optional[TimetableEntry] = None) -> Attendance:
        """Start tracking presence for a student in a class session"""
        
        today = timezone.now().date()
        
        # Calculate expected class duration
        class_duration = self._calculate_class_duration(timetable_entry)
        
        # Get or create attendance record
        attendance, created = Attendance.objects.get_or_create(
            student=student,
            course_registration=course_registration,
            date=today,
            defaults={
                'timetable_entry': timetable_entry,
                'status': 'absent',  # Start as absent, will be updated based on presence
                'total_class_duration': class_duration,
                'presence_duration': timedelta(0),
                'detection_count': 0,
                'presence_percentage': 0.0
            }
        )
        
        if created:
            logger.info(f"Started presence tracking for {student.matric_number} in {course_registration.course.code}")
        
        return attendance
    
    def record_presence_detection(self, attendance: Attendance, detection_timestamp: Optional[datetime] = None) -> bool:
        """Record a presence detection event for a student"""
        
        if detection_timestamp is None:
            detection_timestamp = timezone.now()
        
        with transaction.atomic():
            # Update detection count
            attendance.detection_count += 1
            
            # Update first/last detection times
            if not attendance.first_detected_at:
                attendance.first_detected_at = detection_timestamp
            attendance.last_detected_at = detection_timestamp
            
            # Calculate presence duration
            self._update_presence_duration(attendance, detection_timestamp)
            
            # Update presence percentage
            attendance.update_presence_percentage()
            
            # Update status based on current presence
            self._update_attendance_status(attendance)
            
            attendance.save()
            
            logger.debug(f"Recorded presence for {attendance.student.matric_number}: "
                        f"count={attendance.detection_count}, "
                        f"percentage={attendance.presence_percentage:.1f}%")
        
        return True
    
    def _update_presence_duration(self, attendance: Attendance, detection_timestamp: datetime):
        """Update the presence duration based on detection patterns"""
        
        if not attendance.first_detected_at:
            return
        
        # Calculate base presence duration (time between first and last detection)
        if attendance.last_detected_at and attendance.first_detected_at:
            base_duration = attendance.last_detected_at - attendance.first_detected_at
            
            # Add buffer time for continuous presence assumption
            # Assume student was present for 30 seconds after each detection
            detection_buffer = timedelta(seconds=30 * attendance.detection_count)
            
            # Total presence is base duration plus detection buffer, capped at class duration
            total_presence = base_duration + detection_buffer
            
            if attendance.total_class_duration:
                total_presence = min(total_presence, attendance.total_class_duration)
            
            attendance.presence_duration = total_presence
    
    def _update_attendance_status(self, attendance: Attendance):
        """Update attendance status based on current presence percentage"""
        
        if attendance.is_manual_override:
            return  # Don't change manually set status
        
        percentage = attendance.calculate_presence_percentage()
        
        if percentage >= self.presence_thresholds['present']:
            attendance.status = 'present'
        elif percentage >= self.presence_thresholds['partial']:
            attendance.status = 'partial'
        elif percentage >= self.presence_thresholds['late']:
            attendance.status = 'late'
        else:
            attendance.status = 'absent'
    
    def finalize_class_session(self, course_registration: CourseRegistration, 
                             date: Optional[datetime] = None) -> Dict:
        """Finalize attendance for all students in a class session"""
        
        if date is None:
            date = timezone.now().date()
        
        # Get all attendance records for this session
        attendance_records = Attendance.objects.filter(
            course_registration=course_registration,
            date=date
        )
        
        finalized_count = 0
        status_changes = []
        
        for attendance in attendance_records:
            old_status = attendance.status
            
            # Final calculation of presence percentage
            attendance.update_presence_percentage()
            
            # Final status determination
            self._update_attendance_status(attendance)
            
            # Mark as finalized (locked)
            attendance.is_locked = True
            attendance.save()
            
            if old_status != attendance.status:
                status_changes.append({
                    'student_id': attendance.student.id,
                    'matric_number': attendance.student.matric_number,
                    'old_status': old_status,
                    'new_status': attendance.status,
                    'presence_percentage': attendance.presence_percentage,
                    'presence_duration_minutes': attendance.presence_duration.total_seconds() / 60 if attendance.presence_duration else 0
                })
            
            finalized_count += 1
        
        logger.info(f"Finalized {finalized_count} attendance records for {course_registration.course.code}, "
                   f"{len(status_changes)} status changes")
        
        return {
            'finalized_count': finalized_count,
            'status_changes': status_changes,
            'course_code': course_registration.course.code,
            'date': date.isoformat()
        }
    
    def get_real_time_attendance_stats(self, course_registration: CourseRegistration, 
                                     date: Optional[datetime] = None) -> Dict:
        """Get real-time attendance statistics for a course"""
        
        if date is None:
            date = timezone.now().date()
        
        records = Attendance.objects.filter(
            course_registration=course_registration,
            date=date
        )
        
        total_students = records.count()
        present_students = records.filter(status='present').count()
        partial_students = records.filter(status='partial').count()
        late_students = records.filter(status='late').count()
        absent_students = records.filter(status='absent').count()
        
        # Calculate average presence statistics
        avg_presence = records.exclude(presence_percentage__isnull=True).aggregate(
            avg_percentage=Avg('presence_percentage'),
            avg_duration=Avg('presence_duration'),
            total_detections=Sum('detection_count')
        )
        
        # Students currently being detected (last 2 minutes)
        currently_detected = records.filter(
            last_detected_at__gte=timezone.now() - timedelta(minutes=2)
        ).count()
        
        return {
            'course_code': course_registration.course.code,
            'date': date.isoformat(),
            'total_students': total_students,
            'present': present_students,
            'partial': partial_students,
            'late': late_students,
            'absent': absent_students,
            'currently_detected': currently_detected,
            'attendance_rate': (present_students + partial_students + late_students) / total_students * 100 if total_students > 0 else 0,
            'average_presence_percentage': round(avg_presence['avg_percentage'] or 0, 1),
            'average_presence_duration_minutes': round((avg_presence['avg_duration'].total_seconds() / 60) if avg_presence['avg_duration'] else 0, 1),
            'total_detections': avg_presence['total_detections'] or 0
        }
    
    def get_student_presence_summary(self, student: Student, days: int = 30) -> Dict:
        """Get comprehensive presence summary for a student"""
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        records = Attendance.objects.filter(
            student=student,
            date__range=[start_date, end_date]
        ).order_by('-date')
        
        total_classes = records.count()
        present_count = records.filter(status='present').count()
        partial_count = records.filter(status='partial').count()
        late_count = records.filter(status='late').count()
        absent_count = records.filter(status='absent').count()
        
        # Calculate averages
        avg_stats = records.exclude(presence_percentage__isnull=True).aggregate(
            avg_presence_percentage=Avg('presence_percentage'),
            avg_presence_duration=Avg('presence_duration'),
            avg_detections=Avg('detection_count')
        )
        
        # Recent attendance pattern
        recent_records = []
        for record in records[:10]:  # Last 10 classes
            recent_records.append({
                'date': record.date.isoformat(),
                'course_code': record.course_registration.course.code,
                'status': record.status,
                'presence_percentage': record.presence_percentage,
                'presence_duration_minutes': record.presence_duration.total_seconds() / 60 if record.presence_duration else 0,
                'detection_count': record.detection_count,
                'is_manual_override': record.is_manual_override
            })
        
        return {
            'student_id': student.id,
            'matric_number': student.matric_number,
            'full_name': student.full_name,
            'period': f'{start_date.isoformat()} to {end_date.isoformat()}',
            'total_classes': total_classes,
            'present': present_count,
            'partial': partial_count,
            'late': late_count,
            'absent': absent_count,
            'overall_attendance_rate': round((present_count + partial_count + late_count) / total_classes * 100, 1) if total_classes > 0 else 0,
            'average_presence_percentage': round(avg_stats['avg_presence_percentage'] or 0, 1),
            'average_presence_duration_minutes': round((avg_stats['avg_presence_duration'].total_seconds() / 60) if avg_stats['avg_presence_duration'] else 0, 1),
            'average_detections_per_class': round(avg_stats['avg_detections'] or 0, 1),
            'recent_attendance': recent_records
        }
    
    def _calculate_class_duration(self, timetable_entry: Optional[TimetableEntry]) -> timedelta:
        """Calculate the total duration of a class session"""
        
        if not timetable_entry or not timetable_entry.start_time or not timetable_entry.end_time:
            # Default class duration if no timetable entry
            return timedelta(hours=1, minutes=30)  # 90 minutes default
        
        # Calculate duration from timetable
        start_datetime = datetime.combine(timezone.now().date(), timetable_entry.start_time)
        end_datetime = datetime.combine(timezone.now().date(), timetable_entry.end_time)
        
        return end_datetime - start_datetime
    
    def update_presence_thresholds(self, present: float = None, partial: float = None, late: float = None):
        """Update the presence percentage thresholds"""
        
        if present is not None:
            self.presence_thresholds['present'] = present
        if partial is not None:
            self.presence_thresholds['partial'] = partial
        if late is not None:
            self.presence_thresholds['late'] = late
        
        logger.info(f"Updated presence thresholds: {self.presence_thresholds}")
    
    def get_presence_thresholds(self) -> Dict:
        """Get current presence percentage thresholds"""
        return self.presence_thresholds.copy()


# Global service instance
presence_tracking_service = PresenceTrackingService()