"""
Attendance Integration Service

This service provides a high-level interface for integrating the attendance system
with student course selections. It includes caching, error handling, and fallback
mechanisms for robust operation.
"""

from django.core.cache import cache
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from typing import Dict, Any, Optional, List, Tuple
import logging
import hashlib
import json

from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import TimetableSlot, Level, Course
from attendance.models import Attendance
from attendance.enhanced_services import EnhancedAttendanceService
from attendance.compatibility import EnhancedAttendanceAdapter

logger = logging.getLogger(__name__)


class AttendanceIntegrationService:
    """
    High-level service for attendance integration with caching and error handling
    """
    
    # Cache timeouts (in seconds)
    STUDENT_CACHE_TIMEOUT = 300  # 5 minutes
    TIMETABLE_CACHE_TIMEOUT = 600  # 10 minutes
    COURSE_SELECTION_CACHE_TIMEOUT = 180  # 3 minutes
    VALIDATION_CACHE_TIMEOUT = 60  # 1 minute
    
    @classmethod
    def _get_cache_key(cls, prefix: str, *args) -> str:
        """Generate cache key from prefix and arguments"""
        key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    @classmethod
    def get_student_with_cache(cls, matric_number: str) -> Optional[Student]:
        """Get student with caching"""
        cache_key = cls._get_cache_key('student', matric_number)
        
        # Try cache first
        student = cache.get(cache_key)
        if student is not None:
            return student
        
        try:
            student = Student.objects.select_related(
                'department', 'faculty', 'institution'
            ).get(matric_number=matric_number)
            
            # Cache the student
            cache.set(cache_key, student, cls.STUDENT_CACHE_TIMEOUT)
            return student
            
        except Student.DoesNotExist:
            # Cache negative result for shorter time
            cache.set(cache_key, None, 60)
            return None
        except Exception as e:
            logger.error(f"Error getting student {matric_number}: {e}")
            return None
    
    @classmethod
    def get_student_level_selection_with_cache(cls, student: Student) -> Optional[StudentLevelSelection]:
        """Get student level selection with caching"""
        cache_key = cls._get_cache_key('level_selection', student.id)
        
        # Try cache first
        level_selection = cache.get(cache_key)
        if level_selection is not None:
            return level_selection
        
        try:
            level_selection = StudentLevelSelection.objects.select_related(
                'level'
            ).get(student=student)
            
            # Cache the level selection
            cache.set(cache_key, level_selection, cls.STUDENT_CACHE_TIMEOUT)
            return level_selection
            
        except StudentLevelSelection.DoesNotExist:
            # Cache negative result
            cache.set(cache_key, None, 60)
            return None
        except Exception as e:
            logger.error(f"Error getting level selection for student {student.matric_number}: {e}")
            return None
    
    @classmethod
    def get_current_timetable_slot_with_cache(cls, student: Student) -> Optional[TimetableSlot]:
        """Get current timetable slot with caching"""
        # Cache key includes current time (rounded to minute) for short-term caching
        current_time = timezone.localtime()
        time_key = f"{current_time.strftime('%Y%m%d_%H%M')}"
        cache_key = cls._get_cache_key('current_slot', student.id, time_key)
        
        # Try cache first (very short cache for current slot)
        current_slot = cache.get(cache_key)
        if current_slot is not None:
            return current_slot
        
        try:
            current_slot = EnhancedAttendanceService.get_current_timetable_slot_for_student(student)
            
            # Cache for 1 minute only (current slot changes frequently)
            cache.set(cache_key, current_slot, 60)
            return current_slot
            
        except Exception as e:
            logger.error(f"Error getting current timetable slot for student {student.matric_number}: {e}")
            return None
    
    @classmethod
    def get_student_course_selections_with_cache(cls, student: Student, level: Level) -> List[StudentCourseSelection]:
        """Get student course selections with caching"""
        cache_key = cls._get_cache_key('course_selections', student.id, level.id)
        
        # Try cache first
        selections = cache.get(cache_key)
        if selections is not None:
            return selections
        
        try:
            selections = list(StudentCourseSelection.objects.select_related(
                'course'
            ).filter(
                student=student,
                level=level
            ))
            
            # Cache the selections
            cache.set(cache_key, selections, cls.COURSE_SELECTION_CACHE_TIMEOUT)
            return selections
            
        except Exception as e:
            logger.error(f"Error getting course selections for student {student.matric_number}: {e}")
            return []
    
    @classmethod
    def invalidate_student_cache(cls, student: Student):
        """Invalidate all cached data for a student"""
        try:
            # Invalidate student cache
            student_key = cls._get_cache_key('student', student.matric_number)
            cache.delete(student_key)
            
            # Invalidate level selection cache
            level_key = cls._get_cache_key('level_selection', student.id)
            cache.delete(level_key)
            
            # Invalidate course selections cache (we don't know the level, so we can't be specific)
            # In a production system, you might use cache tags or patterns
            
            logger.info(f"Invalidated cache for student {student.matric_number}")
            
        except Exception as e:
            logger.error(f"Error invalidating cache for student {student.matric_number}: {e}")
    
    @classmethod
    def mark_attendance_with_full_integration(cls, matric_number: str) -> Dict[str, Any]:
        """
        Mark attendance with full integration including caching and error handling
        """
        result = {
            'success': False,
            'message': '',
            'student': None,
            'attendance': None,
            'validation': None,
            'cached_data_used': False,
            'performance_metrics': {}
        }
        
        start_time = timezone.now()
        
        try:
            # Get student with caching
            student = cls.get_student_with_cache(matric_number)
            if not student:
                result['message'] = f'Student with matric number {matric_number} not found'
                return result
            
            result['student'] = {
                'matric_number': student.matric_number,
                'full_name': student.full_name,
                'department': student.department.name
            }
            
            # Get level selection with caching
            level_selection = cls.get_student_level_selection_with_cache(student)
            if not level_selection:
                result['message'] = 'Student has not selected an academic level'
                return result
            
            # Get current timetable slot with caching
            current_slot = cls.get_current_timetable_slot_with_cache(student)
            if not current_slot:
                result['message'] = 'No ongoing class found for student or student is not offering any current courses'
                return result
            
            # Validate attendance eligibility
            validation = EnhancedAttendanceService.validate_attendance_eligibility(student, current_slot)
            result['validation'] = validation
            
            if not validation['eligible']:
                result['message'] = f'Attendance not allowed: {validation["reason"]}'
                return result
            
            # Use the enhanced attendance adapter for actual marking
            attendance_result = EnhancedAttendanceAdapter.mark_attendance_with_course_selection_validation(matric_number)
            
            # Merge results
            result.update(attendance_result)
            
            # Add performance metrics
            end_time = timezone.now()
            result['performance_metrics'] = {
                'total_time_ms': int((end_time - start_time).total_seconds() * 1000),
                'cached_student': cache.get(cls._get_cache_key('student', matric_number)) is not None,
                'cached_level': cache.get(cls._get_cache_key('level_selection', student.id)) is not None,
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in mark_attendance_with_full_integration: {e}")
            result['message'] = f'System error: {str(e)}'
            return result
    
    @classmethod
    def get_student_attendance_summary_with_cache(cls, student: Student) -> Dict[str, Any]:
        """
        Get comprehensive attendance summary with caching
        """
        cache_key = cls._get_cache_key('attendance_summary', student.id)
        
        # Try cache first
        summary = cache.get(cache_key)
        if summary is not None:
            return summary
        
        try:
            # Get level selection
            level_selection = cls.get_student_level_selection_with_cache(student)
            if not level_selection:
                return {
                    'error': 'Student has not selected an academic level',
                    'student': {
                        'matric_number': student.matric_number,
                        'full_name': student.full_name
                    }
                }
            
            # Get course selections
            course_selections = cls.get_student_course_selections_with_cache(student, level_selection.level)
            
            # Get offered courses
            offered_courses = EnhancedAttendanceService.get_student_offered_courses(student)
            
            # Build summary
            summary = {
                'student': {
                    'matric_number': student.matric_number,
                    'full_name': student.full_name,
                    'department': student.department.name,
                    'level': level_selection.level.name
                },
                'level_selection': {
                    'level_name': level_selection.level.name,
                    'level_code': level_selection.level.code,
                    'selected_at': level_selection.selected_at.isoformat(),
                    'updated_at': level_selection.updated_at.isoformat()
                },
                'course_selections': {
                    'total_courses': len(course_selections),
                    'offered_courses': len([cs for cs in course_selections if cs.is_offered]),
                    'opted_out_courses': len([cs for cs in course_selections if not cs.is_offered]),
                    'courses': [
                        {
                            'course_code': cs.course.code,
                            'course_title': cs.course.title,
                            'is_offered': cs.is_offered,
                            'updated_at': cs.updated_at.isoformat()
                        }
                        for cs in course_selections
                    ]
                },
                'offered_courses_detail': offered_courses,
                'generated_at': timezone.now().isoformat()
            }
            
            # Cache the summary
            cache.set(cache_key, summary, cls.STUDENT_CACHE_TIMEOUT)
            return summary
            
        except Exception as e:
            logger.error(f"Error getting attendance summary for student {student.matric_number}: {e}")
            return {
                'error': str(e),
                'student': {
                    'matric_number': student.matric_number,
                    'full_name': student.full_name
                }
            }
    
    @classmethod
    def validate_attendance_with_cache(cls, student: Student, timetable_slot: TimetableSlot) -> Dict[str, Any]:
        """
        Validate attendance eligibility with caching
        """
        # Create cache key from student and slot details
        cache_key = cls._get_cache_key(
            'validation',
            student.id,
            timetable_slot.id,
            timezone.now().strftime('%Y%m%d_%H%M')  # Include time for current validation
        )
        
        # Try cache first
        validation = cache.get(cache_key)
        if validation is not None:
            return validation
        
        try:
            validation = EnhancedAttendanceService.validate_attendance_eligibility(student, timetable_slot)
            
            # Cache validation result for short time
            cache.set(cache_key, validation, cls.VALIDATION_CACHE_TIMEOUT)
            return validation
            
        except Exception as e:
            logger.error(f"Error validating attendance: {e}")
            return {
                'eligible': False,
                'reason': f'Validation error: {str(e)}',
                'student_info': {
                    'matric_number': student.matric_number,
                    'department': student.department.name,
                    'selected_level': None
                }
            }
    
    @classmethod
    def bulk_validate_students(cls, matric_numbers: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Validate attendance for multiple students efficiently
        """
        results = {}
        
        for matric_number in matric_numbers:
            try:
                student = cls.get_student_with_cache(matric_number)
                if not student:
                    results[matric_number] = {
                        'eligible': False,
                        'reason': 'Student not found',
                        'student_info': {'matric_number': matric_number}
                    }
                    continue
                
                current_slot = cls.get_current_timetable_slot_with_cache(student)
                if not current_slot:
                    results[matric_number] = {
                        'eligible': False,
                        'reason': 'No current class or not offering current courses',
                        'student_info': {
                            'matric_number': student.matric_number,
                            'department': student.department.name
                        }
                    }
                    continue
                
                validation = cls.validate_attendance_with_cache(student, current_slot)
                results[matric_number] = validation
                
            except Exception as e:
                logger.error(f"Error validating student {matric_number}: {e}")
                results[matric_number] = {
                    'eligible': False,
                    'reason': f'System error: {str(e)}',
                    'student_info': {'matric_number': matric_number}
                }
        
        return results
    
    @classmethod
    def get_system_health_check(cls) -> Dict[str, Any]:
        """
        Get system health check for attendance integration
        """
        health = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'components': {},
            'metrics': {}
        }
        
        try:
            # Check database connectivity
            student_count = Student.objects.count()
            health['components']['database'] = {
                'status': 'healthy',
                'student_count': student_count
            }
            
            # Check cache connectivity
            test_key = 'health_check_test'
            cache.set(test_key, 'test_value', 10)
            cached_value = cache.get(test_key)
            cache.delete(test_key)
            
            health['components']['cache'] = {
                'status': 'healthy' if cached_value == 'test_value' else 'degraded',
                'test_successful': cached_value == 'test_value'
            }
            
            # Check level selections
            level_selections_count = StudentLevelSelection.objects.count()
            health['components']['level_selections'] = {
                'status': 'healthy',
                'count': level_selections_count
            }
            
            # Check course selections
            course_selections_count = StudentCourseSelection.objects.count()
            health['components']['course_selections'] = {
                'status': 'healthy',
                'count': course_selections_count
            }
            
            # Check timetable slots
            timetable_slots_count = TimetableSlot.objects.count()
            health['components']['timetable_slots'] = {
                'status': 'healthy',
                'count': timetable_slots_count
            }
            
            # Overall status
            component_statuses = [comp['status'] for comp in health['components'].values()]
            if 'unhealthy' in component_statuses:
                health['status'] = 'unhealthy'
            elif 'degraded' in component_statuses:
                health['status'] = 'degraded'
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            health['status'] = 'unhealthy'
            health['error'] = str(e)
        
        return health
    
    @classmethod
    def clear_all_cache(cls):
        """
        Clear all attendance-related cache (for maintenance)
        """
        try:
            # In a production system, you'd use cache patterns or tags
            # For now, we'll just log the action
            logger.info("Clearing all attendance integration cache")
            
            # If using Redis or similar, you could use patterns like:
            # cache.delete_pattern('student:*')
            # cache.delete_pattern('level_selection:*')
            # etc.
            
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")


# Convenience functions for backward compatibility and ease of use
def mark_attendance_integrated(matric_number: str) -> Dict[str, Any]:
    """Convenience function for integrated attendance marking"""
    return AttendanceIntegrationService.mark_attendance_with_full_integration(matric_number)


def get_student_summary_integrated(matric_number: str) -> Dict[str, Any]:
    """Convenience function for getting student attendance summary"""
    student = AttendanceIntegrationService.get_student_with_cache(matric_number)
    if not student:
        return {
            'error': f'Student {matric_number} not found',
            'student': {'matric_number': matric_number}
        }
    
    return AttendanceIntegrationService.get_student_attendance_summary_with_cache(student)


def validate_multiple_students(matric_numbers: List[str]) -> Dict[str, Dict[str, Any]]:
    """Convenience function for bulk validation"""
    return AttendanceIntegrationService.bulk_validate_students(matric_numbers)


def get_health_status() -> Dict[str, Any]:
    """Convenience function for health check"""
    return AttendanceIntegrationService.get_system_health_check()