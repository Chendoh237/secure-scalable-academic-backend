"""
Caching strategies for Student Timetable Module

This module implements intelligent caching to improve performance
for frequently accessed data in the Student Timetable Module.
"""

from django.core.cache import cache
from django.conf import settings
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from typing import Dict, List, Any, Optional
import hashlib
import json
import logging

from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import Level, Course, TimetableSlot, Timetable
from institutions.models import Department

logger = logging.getLogger(__name__)


class StudentTimetableCacheManager:
    """
    Centralized cache management for Student Timetable Module
    """
    
    # Cache key prefixes
    LEVELS_PREFIX = "student_levels"
    TIMETABLE_PREFIX = "student_timetable"
    COURSE_SELECTIONS_PREFIX = "course_selections"
    DEPARTMENT_STATS_PREFIX = "dept_stats"
    
    # Cache timeouts (in seconds)
    LEVELS_TIMEOUT = 3600  # 1 hour - levels don't change often
    TIMETABLE_TIMEOUT = 1800  # 30 minutes - timetables are relatively stable
    COURSE_SELECTIONS_TIMEOUT = 300  # 5 minutes - course selections change more frequently
    STATS_TIMEOUT = 600  # 10 minutes - statistics for dashboards
    
    @classmethod
    def get_levels_cache_key(cls, department_id: int) -> str:
        """Generate cache key for department levels"""
        return f"{cls.LEVELS_PREFIX}_{department_id}"
    
    @classmethod
    def get_timetable_cache_key(cls, department_id: int, level_id: int) -> str:
        """Generate cache key for department timetable"""
        return f"{cls.TIMETABLE_PREFIX}_{department_id}_{level_id}"
    
    @classmethod
    def get_course_selections_cache_key(cls, student_id: int, level_id: int) -> str:
        """Generate cache key for student course selections"""
        return f"{cls.COURSE_SELECTIONS_PREFIX}_{student_id}_{level_id}"
    
    @classmethod
    def get_department_stats_cache_key(cls, department_id: int) -> str:
        """Generate cache key for department statistics"""
        return f"{cls.DEPARTMENT_STATS_PREFIX}_{department_id}"
    
    @classmethod
    def get_or_set_levels(cls, department_id: int) -> List[Dict[str, Any]]:
        """
        Get or cache department levels data
        
        Args:
            department_id: Department ID
            
        Returns:
            List of level data dictionaries
        """
        cache_key = cls.get_levels_cache_key(department_id)
        levels_data = cache.get(cache_key)
        
        if levels_data is None:
            try:
                levels = Level.objects.filter(
                    department_id=department_id
                ).order_by('code').values(
                    'id', 'name', 'code', 'department__name'
                )
                
                levels_data = list(levels)
                cache.set(cache_key, levels_data, cls.LEVELS_TIMEOUT)
                
                logger.debug(f"Cached {len(levels_data)} levels for department {department_id}")
            except Exception as e:
                logger.error(f"Error caching levels for department {department_id}: {e}")
                return []
        
        return levels_data
    
    @classmethod
    def get_or_set_timetable(cls, department_id: int, level_id: int) -> List[Dict[str, Any]]:
        """
        Get or cache timetable data for department and level
        
        Args:
            department_id: Department ID
            level_id: Level ID
            
        Returns:
            List of timetable slot data dictionaries
        """
        cache_key = cls.get_timetable_cache_key(department_id, level_id)
        timetable_data = cache.get(cache_key)
        
        if timetable_data is None:
            try:
                # Use select_related to optimize database queries
                timetable_slots = TimetableSlot.objects.select_related(
                    'course', 'lecturer', 'lecturer__user', 'level'
                ).filter(
                    timetable__department_id=department_id,
                    level_id=level_id
                ).order_by('day_of_week', 'start_time')
                
                timetable_data = []
                for slot in timetable_slots:
                    timetable_data.append({
                        'id': slot.id,
                        'day_of_week': slot.day_of_week,
                        'day_name': slot.get_day_of_week_display(),
                        'start_time': slot.start_time.strftime('%H:%M'),
                        'end_time': slot.end_time.strftime('%H:%M'),
                        'course': {
                            'id': slot.course.id,
                            'code': slot.course.code,
                            'title': slot.course.title,
                            'credit_units': slot.course.credit_units
                        },
                        'lecturer': {
                            'id': slot.lecturer.id,
                            'name': f"{slot.lecturer.user.first_name} {slot.lecturer.user.last_name}".strip(),
                            'employee_id': slot.lecturer.employee_id
                        },
                        'venue': slot.venue
                    })
                
                cache.set(cache_key, timetable_data, cls.TIMETABLE_TIMEOUT)
                
                logger.debug(f"Cached {len(timetable_data)} timetable slots for dept {department_id}, level {level_id}")
            except Exception as e:
                logger.error(f"Error caching timetable for dept {department_id}, level {level_id}: {e}")
                return []
        
        return timetable_data
    
    @classmethod
    def get_or_set_course_selections(cls, student_id: int, level_id: int) -> List[Dict[str, Any]]:
        """
        Get or cache student course selections
        
        Args:
            student_id: Student ID
            level_id: Level ID
            
        Returns:
            List of course selection data dictionaries
        """
        cache_key = cls.get_course_selections_cache_key(student_id, level_id)
        selections_data = cache.get(cache_key)
        
        if selections_data is None:
            try:
                course_selections = StudentCourseSelection.objects.select_related(
                    'course'
                ).filter(
                    student_id=student_id,
                    level_id=level_id
                ).order_by('course__code')
                
                selections_data = []
                for selection in course_selections:
                    selections_data.append({
                        'id': selection.id,
                        'course': {
                            'id': selection.course.id,
                            'code': selection.course.code,
                            'title': selection.course.title
                        },
                        'is_offered': selection.is_offered,
                        'created_at': selection.created_at.isoformat(),
                        'updated_at': selection.updated_at.isoformat()
                    })
                
                cache.set(cache_key, selections_data, cls.COURSE_SELECTIONS_TIMEOUT)
                
                logger.debug(f"Cached {len(selections_data)} course selections for student {student_id}, level {level_id}")
            except Exception as e:
                logger.error(f"Error caching course selections for student {student_id}, level {level_id}: {e}")
                return []
        
        return selections_data
    
    @classmethod
    def get_or_set_department_stats(cls, department_id: int) -> Dict[str, Any]:
        """
        Get or cache department statistics
        
        Args:
            department_id: Department ID
            
        Returns:
            Dictionary of department statistics
        """
        cache_key = cls.get_department_stats_cache_key(department_id)
        stats_data = cache.get(cache_key)
        
        if stats_data is None:
            try:
                # Calculate department statistics
                total_students = Student.objects.filter(department_id=department_id).count()
                students_with_level = StudentLevelSelection.objects.filter(
                    student__department_id=department_id
                ).count()
                total_course_selections = StudentCourseSelection.objects.filter(
                    department_id=department_id
                ).count()
                offered_courses = StudentCourseSelection.objects.filter(
                    department_id=department_id,
                    is_offered=True
                ).count()
                
                # Level distribution
                level_distribution = {}
                level_selections = StudentLevelSelection.objects.filter(
                    student__department_id=department_id
                ).select_related('level').values('level__name').annotate(
                    count=models.Count('id')
                )
                
                for item in level_selections:
                    level_distribution[item['level__name']] = item['count']
                
                stats_data = {
                    'total_students': total_students,
                    'students_with_level': students_with_level,
                    'level_selection_rate': (students_with_level / total_students * 100) if total_students > 0 else 0,
                    'total_course_selections': total_course_selections,
                    'offered_courses': offered_courses,
                    'course_offering_rate': (offered_courses / total_course_selections * 100) if total_course_selections > 0 else 0,
                    'level_distribution': level_distribution,
                    'last_updated': timezone.now().isoformat()
                }
                
                cache.set(cache_key, stats_data, cls.STATS_TIMEOUT)
                
                logger.debug(f"Cached statistics for department {department_id}")
            except Exception as e:
                logger.error(f"Error caching department stats for {department_id}: {e}")
                return {}
        
        return stats_data
    
    @classmethod
    def invalidate_levels_cache(cls, department_id: int):
        """Invalidate levels cache for a department"""
        cache_key = cls.get_levels_cache_key(department_id)
        cache.delete(cache_key)
        logger.debug(f"Invalidated levels cache for department {department_id}")
    
    @classmethod
    def invalidate_timetable_cache(cls, department_id: int, level_id: Optional[int] = None):
        """
        Invalidate timetable cache for a department
        
        Args:
            department_id: Department ID
            level_id: Optional level ID. If None, invalidates all levels for the department
        """
        if level_id:
            cache_key = cls.get_timetable_cache_key(department_id, level_id)
            cache.delete(cache_key)
            logger.debug(f"Invalidated timetable cache for dept {department_id}, level {level_id}")
        else:
            # Invalidate all timetable caches for the department
            # This is a simplified approach - in production you might want to track all cached keys
            levels = Level.objects.filter(department_id=department_id).values_list('id', flat=True)
            for level_id in levels:
                cache_key = cls.get_timetable_cache_key(department_id, level_id)
                cache.delete(cache_key)
            logger.debug(f"Invalidated all timetable caches for department {department_id}")
    
    @classmethod
    def invalidate_course_selections_cache(cls, student_id: int, level_id: int):
        """Invalidate course selections cache for a student"""
        cache_key = cls.get_course_selections_cache_key(student_id, level_id)
        cache.delete(cache_key)
        logger.debug(f"Invalidated course selections cache for student {student_id}, level {level_id}")
    
    @classmethod
    def invalidate_department_stats_cache(cls, department_id: int):
        """Invalidate department statistics cache"""
        cache_key = cls.get_department_stats_cache_key(department_id)
        cache.delete(cache_key)
        logger.debug(f"Invalidated department stats cache for {department_id}")
    
    @classmethod
    def clear_all_caches(cls):
        """Clear all Student Timetable Module caches"""
        # This is a simplified approach - in production you'd want more sophisticated cache management
        cache.clear()
        logger.info("Cleared all Student Timetable Module caches")


# Signal handlers for automatic cache invalidation
@receiver(post_save, sender=Level)
@receiver(post_delete, sender=Level)
def invalidate_level_caches(sender, instance, **kwargs):
    """Invalidate caches when levels are modified"""
    StudentTimetableCacheManager.invalidate_levels_cache(instance.department_id)
    StudentTimetableCacheManager.invalidate_timetable_cache(instance.department_id)
    StudentTimetableCacheManager.invalidate_department_stats_cache(instance.department_id)


@receiver(post_save, sender=TimetableSlot)
@receiver(post_delete, sender=TimetableSlot)
def invalidate_timetable_caches(sender, instance, **kwargs):
    """Invalidate caches when timetable slots are modified"""
    department_id = instance.timetable.department_id
    level_id = instance.level_id
    
    StudentTimetableCacheManager.invalidate_timetable_cache(department_id, level_id)
    StudentTimetableCacheManager.invalidate_department_stats_cache(department_id)


@receiver(post_save, sender=StudentLevelSelection)
@receiver(post_delete, sender=StudentLevelSelection)
def invalidate_level_selection_caches(sender, instance, **kwargs):
    """Invalidate caches when student level selections are modified"""
    department_id = instance.student.department_id
    StudentTimetableCacheManager.invalidate_department_stats_cache(department_id)


@receiver(post_save, sender=StudentCourseSelection)
@receiver(post_delete, sender=StudentCourseSelection)
def invalidate_course_selection_caches(sender, instance, **kwargs):
    """Invalidate caches when course selections are modified"""
    StudentTimetableCacheManager.invalidate_course_selections_cache(
        instance.student_id, 
        instance.level_id
    )
    StudentTimetableCacheManager.invalidate_department_stats_cache(instance.department_id)


# Utility functions for view integration
def get_cached_levels(department_id: int) -> List[Dict[str, Any]]:
    """Get cached levels data for a department"""
    return StudentTimetableCacheManager.get_or_set_levels(department_id)


def get_cached_timetable(department_id: int, level_id: int) -> List[Dict[str, Any]]:
    """Get cached timetable data for department and level"""
    return StudentTimetableCacheManager.get_or_set_timetable(department_id, level_id)


def get_cached_course_selections(student_id: int, level_id: int) -> List[Dict[str, Any]]:
    """Get cached course selections for a student"""
    return StudentTimetableCacheManager.get_or_set_course_selections(student_id, level_id)


def get_cached_department_stats(department_id: int) -> Dict[str, Any]:
    """Get cached department statistics"""
    return StudentTimetableCacheManager.get_or_set_department_stats(department_id)


# Cache warming functions for proactive caching
def warm_department_caches(department_id: int):
    """
    Warm up caches for a department by pre-loading frequently accessed data
    
    Args:
        department_id: Department ID to warm caches for
    """
    try:
        # Warm levels cache
        get_cached_levels(department_id)
        
        # Warm timetable caches for all levels
        levels = Level.objects.filter(department_id=department_id).values_list('id', flat=True)
        for level_id in levels:
            get_cached_timetable(department_id, level_id)
        
        # Warm department stats cache
        get_cached_department_stats(department_id)
        
        logger.info(f"Warmed caches for department {department_id}")
    except Exception as e:
        logger.error(f"Error warming caches for department {department_id}: {e}")


def warm_student_caches(student_id: int):
    """
    Warm up caches for a student by pre-loading their data
    
    Args:
        student_id: Student ID to warm caches for
    """
    try:
        student = Student.objects.select_related('level_selection').get(id=student_id)
        
        # Warm department-level caches
        warm_department_caches(student.department_id)
        
        # Warm student-specific caches if they have a level selection
        if hasattr(student, 'level_selection'):
            get_cached_course_selections(student_id, student.level_selection.level_id)
        
        logger.info(f"Warmed caches for student {student_id}")
    except Student.DoesNotExist:
        logger.warning(f"Student {student_id} not found for cache warming")
    except Exception as e:
        logger.error(f"Error warming caches for student {student_id}: {e}")


# Management command helper
def warm_all_caches():
    """
    Warm up all caches for the Student Timetable Module
    This function can be called from a management command or scheduled task
    """
    try:
        # Get all departments
        departments = Department.objects.values_list('id', flat=True)
        
        for department_id in departments:
            warm_department_caches(department_id)
        
        logger.info(f"Warmed caches for {len(departments)} departments")
    except Exception as e:
        logger.error(f"Error warming all caches: {e}")