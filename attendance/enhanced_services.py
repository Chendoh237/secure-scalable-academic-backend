"""
Enhanced Attendance Services with Course Selection Integration

This module provides enhanced attendance services that integrate with the
Student Timetable Module course selections. It validates attendance based on:
- Student identity
- Student department
- Student-selected level
- Current day and time
- Timetable slot (course + lecturer)
- Student course offering status
"""

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from typing import Dict, Any, Optional, List
import logging

from attendance.models import Attendance
from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import TimetableSlot, Level, Course
from attendance.utils import determine_attendance_status

logger = logging.getLogger(__name__)


class AttendanceValidationError(Exception):
    """Custom exception for attendance validation errors"""
    pass


class EnhancedAttendanceService:
    """
    Enhanced attendance service that integrates with student course selections
    """
    
    @staticmethod
    def get_current_timetable_slot_for_student(student: Student) -> Optional[TimetableSlot]:
        """
        Get the current timetable slot for a student based on their selected level
        and current time, considering only courses they are offering.
        """
        try:
            # Get student's selected level
            level_selection = StudentLevelSelection.objects.select_related('level').get(
                student=student
            )
            selected_level = level_selection.level
            
            # Get current time and day
            now = timezone.localtime()
            current_day = now.strftime('%a').upper()[:3]  # MON, TUE, WED, etc.
            current_time = now.time()
            
            # Find current timetable slot for the student's level and department
            current_slot = TimetableSlot.objects.select_related(
                'course', 'lecturer', 'timetable'
            ).filter(
                timetable__department=student.department,
                level=selected_level,
                day_of_week=current_day,
                start_time__lte=current_time,
                end_time__gte=current_time
            ).first()
            
            if not current_slot:
                return None
            
            # Check if student is offering this course
            try:
                course_selection = StudentCourseSelection.objects.get(
                    student=student,
                    course=current_slot.course,
                    level=selected_level
                )
                
                # Only return the slot if student is offering the course
                if course_selection.is_offered:
                    return current_slot
                else:
                    logger.info(
                        f"Student {student.matric_number} is not offering course "
                        f"{current_slot.course.code}, skipping attendance"
                    )
                    return None
                    
            except StudentCourseSelection.DoesNotExist:
                # If no explicit selection exists, default to offered (as per requirements)
                logger.info(
                    f"No course selection found for student {student.matric_number} "
                    f"and course {current_slot.course.code}, defaulting to offered"
                )
                return current_slot
                
        except StudentLevelSelection.DoesNotExist:
            logger.warning(f"Student {student.matric_number} has no level selection")
            return None
        except Exception as e:
            logger.error(f"Error getting current timetable slot for student {student.matric_number}: {e}")
            return None
    
    @staticmethod
    def validate_attendance_eligibility(student: Student, timetable_slot: TimetableSlot) -> Dict[str, Any]:
        """
        Comprehensive validation for attendance eligibility.
        Returns validation result with details.
        """
        validation_result = {
            'eligible': False,
            'reason': '',
            'details': {},
            'student_info': {
                'matric_number': student.matric_number,
                'department': student.department.name,
                'selected_level': None,
            }
        }
        
        try:
            # 1. Validate student has selected a level
            try:
                level_selection = StudentLevelSelection.objects.select_related('level').get(
                    student=student
                )
                validation_result['student_info']['selected_level'] = level_selection.level.name
            except StudentLevelSelection.DoesNotExist:
                validation_result['reason'] = 'Student has not selected an academic level'
                return validation_result
            
            # 2. Validate student department matches timetable department
            if student.department != timetable_slot.timetable.department:
                validation_result['reason'] = 'Student department does not match timetable department'
                validation_result['details'] = {
                    'student_department': student.department.name,
                    'timetable_department': timetable_slot.timetable.department.name
                }
                return validation_result
            
            # 3. Validate student level matches timetable slot level
            if level_selection.level != timetable_slot.level:
                validation_result['reason'] = 'Student level does not match timetable slot level'
                validation_result['details'] = {
                    'student_level': level_selection.level.name,
                    'slot_level': timetable_slot.level.name
                }
                return validation_result
            
            # 4. Validate student is offering the course
            try:
                course_selection = StudentCourseSelection.objects.get(
                    student=student,
                    course=timetable_slot.course,
                    level=level_selection.level
                )
                
                if not course_selection.is_offered:
                    validation_result['reason'] = 'Student is not offering this course'
                    validation_result['details'] = {
                        'course_code': timetable_slot.course.code,
                        'course_title': timetable_slot.course.title,
                        'is_offered': False
                    }
                    return validation_result
                    
            except StudentCourseSelection.DoesNotExist:
                # Default to offered if no explicit selection
                logger.info(
                    f"No course selection found for {student.matric_number} "
                    f"and {timetable_slot.course.code}, defaulting to offered"
                )
            
            # 5. Validate timing (class is currently ongoing)
            now = timezone.localtime()
            current_day = now.strftime('%a').upper()[:3]
            current_time = now.time()
            
            if timetable_slot.day_of_week != current_day:
                validation_result['reason'] = 'Class is not scheduled for today'
                validation_result['details'] = {
                    'current_day': current_day,
                    'class_day': timetable_slot.day_of_week
                }
                return validation_result
            
            if not (timetable_slot.start_time <= current_time <= timetable_slot.end_time):
                validation_result['reason'] = 'Class is not currently ongoing'
                validation_result['details'] = {
                    'current_time': current_time.strftime('%H:%M'),
                    'class_start': timetable_slot.start_time.strftime('%H:%M'),
                    'class_end': timetable_slot.end_time.strftime('%H:%M')
                }
                return validation_result
            
            # All validations passed
            validation_result['eligible'] = True
            validation_result['reason'] = 'Student is eligible for attendance'
            validation_result['details'] = {
                'course_code': timetable_slot.course.code,
                'course_title': timetable_slot.course.title,
                'lecturer': timetable_slot.lecturer.user.get_full_name(),
                'venue': timetable_slot.venue,
                'time_slot': f"{timetable_slot.start_time.strftime('%H:%M')}-{timetable_slot.end_time.strftime('%H:%M')}"
            }
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating attendance eligibility: {e}")
            validation_result['reason'] = f'Validation error: {str(e)}'
            return validation_result
    
    @staticmethod
    @transaction.atomic
    def mark_enhanced_attendance(student_matric: str) -> Dict[str, Any]:
        """
        Enhanced attendance marking that considers course selections.
        
        Args:
            student_matric: Student matriculation number
            
        Returns:
            Dict containing attendance result and details
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
            
            # Get current timetable slot for student
            current_slot = EnhancedAttendanceService.get_current_timetable_slot_for_student(student)
            
            if not current_slot:
                result['message'] = 'No ongoing class found for student or student is not offering any current courses'
                return result
            
            # Validate attendance eligibility
            validation = EnhancedAttendanceService.validate_attendance_eligibility(student, current_slot)
            result['validation'] = validation
            
            if not validation['eligible']:
                result['message'] = f'Attendance not allowed: {validation["reason"]}'
                return result
            
            # Check if attendance already exists
            today = timezone.now().date()
            existing_attendance = Attendance.objects.filter(
                student=student,
                timetable_entry__isnull=True,  # We'll need to adapt this for new structure
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
            status = determine_attendance_status(current_slot)
            
            # Create attendance record
            # Note: We need to adapt this to work with the new TimetableSlot structure
            # For now, we'll create a basic attendance record
            attendance = Attendance.objects.create(
                student=student,
                # We'll need to create a course registration or adapt the model
                course_registration=None,  # This needs to be handled
                timetable_entry=None,  # This needs to be adapted
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
    def get_student_offered_courses(student: Student) -> List[Dict[str, Any]]:
        """
        Get list of courses that a student is currently offering.
        """
        try:
            level_selection = StudentLevelSelection.objects.select_related('level').get(
                student=student
            )
            
            # Get all courses for the student's level
            timetable_slots = TimetableSlot.objects.select_related(
                'course', 'lecturer'
            ).filter(
                timetable__department=student.department,
                level=level_selection.level
            ).distinct('course')
            
            offered_courses = []
            
            for slot in timetable_slots:
                # Check if student is offering this course and it's approved
                try:
                    course_selection = StudentCourseSelection.objects.get(
                        student=student,
                        course=slot.course,
                        level=level_selection.level
                    )
                    is_offered = course_selection.is_offered and course_selection.is_approved
                except StudentCourseSelection.DoesNotExist:
                    # Default to offered and approved for timetable courses
                    is_offered = True
                
                if is_offered:
                    offered_courses.append({
                        'course_code': slot.course.code,
                        'course_title': slot.course.title,
                        'credit_units': slot.course.credit_units,
                        'is_offered': is_offered
                    })
            
            return offered_courses
            
        except StudentLevelSelection.DoesNotExist:
            return []
        except Exception as e:
            logger.error(f"Error getting offered courses for {student.matric_number}: {e}")
            return []
    
    @staticmethod
    def auto_mark_absent_for_opted_out_courses():
        """
        Automatically mark students as absent for courses they have opted out of.
        This should be run after class ends to ensure no penalties for non-offered courses.
        """
        now = timezone.localtime()
        current_day = now.strftime('%a').upper()[:3]
        
        # Get all timetable slots that have ended today
        ended_slots = TimetableSlot.objects.select_related(
            'course', 'level', 'timetable__department'
        ).filter(
            day_of_week=current_day,
            end_time__lt=now.time()
        )
        
        for slot in ended_slots:
            # Get all students who have opted out of this course
            opted_out_students = StudentCourseSelection.objects.select_related(
                'student'
            ).filter(
                course=slot.course,
                level=slot.level,
                department=slot.timetable.department,
                is_offered=False
            )
            
            for selection in opted_out_students:
                logger.info(
                    f"Skipping attendance for {selection.student.matric_number} "
                    f"in {slot.course.code} - student opted out"
                )
                # We don't create attendance records for opted-out courses
                # This ensures no penalties are recorded
    
    @staticmethod
    def get_attendance_summary_for_student(student: Student) -> Dict[str, Any]:
        """
        Get attendance summary for a student, considering only offered courses.
        """
        try:
            level_selection = StudentLevelSelection.objects.select_related('level').get(
                student=student
            )
            
            offered_courses = EnhancedAttendanceService.get_student_offered_courses(student)
            
            summary = {
                'student': {
                    'matric_number': student.matric_number,
                    'full_name': student.full_name,
                    'level': level_selection.level.name
                },
                'total_offered_courses': len(offered_courses),
                'courses': []
            }
            
            for course_info in offered_courses:
                # Calculate attendance for this course
                # Note: This would need to be adapted based on the actual attendance model structure
                course_summary = {
                    'course_code': course_info['course_code'],
                    'course_title': course_info['course_title'],
                    'total_classes': 0,  # Would be calculated from actual attendance records
                    'attended_classes': 0,  # Would be calculated from actual attendance records
                    'attendance_percentage': 0.0,  # Would be calculated
                    'eligible_for_exam': True  # Would be calculated based on threshold
                }
                summary['courses'].append(course_summary)
            
            return summary
            
        except StudentLevelSelection.DoesNotExist:
            return {
                'error': 'Student has not selected an academic level',
                'student': {
                    'matric_number': student.matric_number,
                    'full_name': student.full_name
                }
            }
        except Exception as e:
            logger.error(f"Error getting attendance summary for {student.matric_number}: {e}")
            return {
                'error': str(e),
                'student': {
                    'matric_number': student.matric_number,
                    'full_name': student.full_name
                }
            }


# Convenience functions for backward compatibility
def get_current_timetable_slot_for_student(student: Student) -> Optional[TimetableSlot]:
    """Convenience function for getting current timetable slot"""
    return EnhancedAttendanceService.get_current_timetable_slot_for_student(student)


def mark_enhanced_attendance(student_matric: str) -> Dict[str, Any]:
    """Convenience function for marking enhanced attendance"""
    return EnhancedAttendanceService.mark_enhanced_attendance(student_matric)


def validate_attendance_eligibility(student: Student, timetable_slot: TimetableSlot) -> Dict[str, Any]:
    """Convenience function for validating attendance eligibility"""
    return EnhancedAttendanceService.validate_attendance_eligibility(student, timetable_slot)