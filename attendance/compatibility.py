"""
Compatibility layer for integrating the new Student Timetable Module
with the existing attendance system.

This module provides adapters and utilities to bridge the gap between
the old attendance models and the new timetable structure.
"""

from django.utils import timezone
from django.db import transaction
from typing import Dict, Any, Optional
import logging

from attendance.models import Attendance, CourseRegistration
from courses.models import TimetableSlot, TimetableEntry, CourseRegistration
from academics.models import CourseOffering
from students.models import Student, StudentLevelSelection, StudentCourseSelection
from attendance.enhanced_services import EnhancedAttendanceService

logger = logging.getLogger(__name__)


class TimetableAdapter:
    """
    Adapter to convert between new TimetableSlot and old TimetableEntry structures
    """
    
    @staticmethod
    def create_timetable_entry_from_slot(timetable_slot: TimetableSlot) -> Optional[TimetableEntry]:
        """
        Create or get a TimetableEntry from a TimetableSlot for compatibility
        """
        try:
            # First, we need to find or create a CourseOffering
            current_year = timezone.now().year
            academic_year = f"{current_year}/{current_year + 1}"
            
            course_offering, created = CourseOffering.objects.get_or_create(
                course=timetable_slot.course,
                academic_year=academic_year,
                semester='1',  # Default to semester 1
                defaults={
                    'instructor_name': timetable_slot.lecturer.user.get_full_name()
                }
            )
            
            # Create or get TimetableEntry
            timetable_entry, created = TimetableEntry.objects.get_or_create(
                course_offering=course_offering,
                day_of_week=timetable_slot.day_of_week,
                start_time=timetable_slot.start_time,
                end_time=timetable_slot.end_time,
                defaults={
                    'room': timetable_slot.venue or 'TBA'
                }
            )
            
            return timetable_entry
            
        except Exception as e:
            logger.error(f"Error creating TimetableEntry from TimetableSlot: {e}")
            return None
    
    @staticmethod
    def ensure_student_course_registration(student: Student, timetable_slot: TimetableSlot) -> Optional[CourseRegistration]:
        """
        Ensure student has a course registration for the given timetable slot
        """
        try:
            # Get or create course offering
            current_year = timezone.now().year
            academic_year = f"{current_year}/{current_year + 1}"
            
            course_offering, created = CourseOffering.objects.get_or_create(
                course=timetable_slot.course,
                academic_year=academic_year,
                semester='1',
                defaults={
                    'instructor_name': timetable_slot.lecturer.user.get_full_name()
                }
            )
            
            # Get or create student course registration
            student_course, created = StudentCourse.objects.get_or_create(
                student=student,
                course_offering=course_offering,
                defaults={
                    'is_active': True
                }
            )
            
            return student_course
            
        except Exception as e:
            logger.error(f"Error ensuring student course registration: {e}")
            return None


class EnhancedAttendanceAdapter:
    """
    Adapter that integrates the enhanced attendance service with the existing system
    """
    
    @staticmethod
    @transaction.atomic
    def mark_attendance_with_course_selection_validation(student_matric: str) -> Dict[str, Any]:
        """
        Mark attendance using the enhanced validation but compatible with existing models
        """
        result = {
            'success': False,
            'message': '',
            'student': None,
            'attendance': None,
            'validation': None
        }
        
        try:
            # Get student
            try:
                student = Student.objects.select_related(
                    'department', 'faculty', 'institution'
                ).get(matric_number=student_matric)
                result['student'] = {
                    'matric_number': student.matric_number,
                    'full_name': student.full_name,
                    'department': student.department.name
                }
            except Student.DoesNotExist:
                result['message'] = f'Student with matric number {student_matric} not found'
                return result
            
            # Get current timetable slot using enhanced service
            current_slot = EnhancedAttendanceService.get_current_timetable_slot_for_student(student)
            
            if not current_slot:
                result['message'] = 'No ongoing class found for student or student is not offering any current courses'
                return result
            
            # Validate attendance eligibility using enhanced service
            validation = EnhancedAttendanceService.validate_attendance_eligibility(student, current_slot)
            result['validation'] = validation
            
            if not validation['eligible']:
                result['message'] = f'Attendance not allowed: {validation["reason"]}'
                return result
            
            # Create compatible TimetableEntry
            timetable_entry = TimetableAdapter.create_timetable_entry_from_slot(current_slot)
            if not timetable_entry:
                result['message'] = 'Failed to create compatible timetable entry'
                return result
            
            # Ensure student course registration
            course_registration = TimetableAdapter.ensure_student_course_registration(student, current_slot)
            if not course_registration:
                result['message'] = 'Failed to ensure student course registration'
                return result
            
            # Check if attendance already exists
            today = timezone.now().date()
            existing_attendance = Attendance.objects.filter(
                student=student,
                timetable_entry=timetable_entry,
                date=today
            ).first()
            
            if existing_attendance:
                result['message'] = 'Attendance already marked for this class today'
                result['attendance'] = {
                    'status': existing_attendance.status,
                    'recorded_at': existing_attendance.recorded_at.isoformat()
                }
                return result
            
            # Determine attendance status (present/late)
            now = timezone.localtime().time()
            if now <= current_slot.start_time:
                status = "present"
            else:
                status = "late"
            
            # Create attendance record
            attendance = Attendance.objects.create(
                student=student,
                course_registration=course_registration,
                timetable_entry=timetable_entry,
                date=today,
                status=status,
                is_manual_override=False
            )
            
            result['success'] = True
            result['message'] = f'Attendance marked as {status.upper()}'
            result['attendance'] = {
                'status': attendance.status,
                'recorded_at': attendance.recorded_at.isoformat(),
                'course': current_slot.course.code,
                'lecturer': current_slot.lecturer.user.get_full_name(),
                'venue': current_slot.venue
            }
            
            logger.info(
                f"Enhanced attendance marked for {student.matric_number} "
                f"in {current_slot.course.code} as {status}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error marking enhanced attendance: {e}")
            result['message'] = f'Error marking attendance: {str(e)}'
            return result
    
    @staticmethod
    def get_current_timetable_entry_enhanced(student: Student) -> Optional[TimetableEntry]:
        """
        Get current timetable entry using enhanced logic but returning compatible format
        """
        try:
            # Get current slot using enhanced service
            current_slot = EnhancedAttendanceService.get_current_timetable_slot_for_student(student)
            
            if not current_slot:
                return None
            
            # Convert to TimetableEntry
            return TimetableAdapter.create_timetable_entry_from_slot(current_slot)
            
        except Exception as e:
            logger.error(f"Error getting current timetable entry: {e}")
            return None
    
    @staticmethod
    def auto_mark_absent_with_course_selection_filtering():
        """
        Auto-mark absent but only for courses students are offering
        """
        now = timezone.localtime()
        current_day = now.strftime('%a').upper()[:3]
        
        # Get all timetable slots that have ended today
        ended_slots = TimetableSlot.objects.select_related(
            'course', 'level', 'timetable__department', 'lecturer'
        ).filter(
            day_of_week=current_day,
            end_time__lt=now.time()
        )
        
        for slot in ended_slots:
            # Get all students in this department and level
            students_in_level = StudentLevelSelection.objects.select_related(
                'student'
            ).filter(
                level=slot.level,
                student__department=slot.timetable.department
            )
            
            for level_selection in students_in_level:
                student = level_selection.student
                
                # Check if student is offering this course and it's approved
                try:
                    course_selection = StudentCourseSelection.objects.get(
                        student=student,
                        course=slot.course,
                        level=slot.level
                    )
                    is_offered = course_selection.is_offered and course_selection.is_approved
                except StudentCourseSelection.DoesNotExist:
                    # Default to offered and approved for timetable courses
                    is_offered = True
                
                if is_offered:
                    # Student is offering the course, mark as absent if not already marked
                    timetable_entry = TimetableAdapter.create_timetable_entry_from_slot(slot)
                    course_registration = TimetableAdapter.ensure_student_course_registration(student, slot)
                    
                    if timetable_entry and course_registration:
                        today = timezone.now().date()
                        attendance, created = Attendance.objects.get_or_create(
                            student=student,
                            course_registration=course_registration,
                            timetable_entry=timetable_entry,
                            date=today,
                            defaults={'status': 'absent'}
                        )
                        
                        if created:
                            logger.info(
                                f"Auto-marked {student.matric_number} as absent "
                                f"for {slot.course.code}"
                            )
                else:
                    # Student opted out, don't create attendance record
                    logger.info(
                        f"Skipping attendance for {student.matric_number} "
                        f"in {slot.course.code} - student opted out"
                    )


# Convenience functions to replace existing attendance functions
def mark_attendance_enhanced(student_matric: str) -> Dict[str, Any]:
    """
    Enhanced version of mark_attendance that considers course selections
    """
    return EnhancedAttendanceAdapter.mark_attendance_with_course_selection_validation(student_matric)


def get_current_timetable_entry_enhanced(student: Student) -> Optional[TimetableEntry]:
    """
    Enhanced version of get_current_timetable_entry that considers course selections
    """
    return EnhancedAttendanceAdapter.get_current_timetable_entry_enhanced(student)


def auto_mark_absent_enhanced():
    """
    Enhanced version of auto_mark_absent that considers course selections
    """
    return EnhancedAttendanceAdapter.auto_mark_absent_with_course_selection_filtering()