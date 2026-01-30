"""
Timetable Selection Service

Handles timetable-based course selection with auto-approval.
Students can mark courses from their academic level's timetable as "offering" or "not offering".
"""

from django.db import transaction
from students.models import StudentCourseSelection, CourseSelectionAuditLog
from courses.models import Course, TimetableSlot


def mark_timetable_course_offering(student, course, level):
    """
    Marks a timetable course as "offering" for a student.
    Auto-approves the course (is_approved=True).
    
    Args:
        student: Student instance
        course: Course instance
        level: Level instance
    
    Returns:
        StudentCourseSelection: The created or updated selection
    """
    with transaction.atomic():
        selection, created = StudentCourseSelection.objects.update_or_create(
            student=student,
            course=course,
            level=level,
            defaults={
                'department': student.department,
                'is_offered': True,
                'is_approved': True  # Auto-approve timetable courses
            }
        )
        
        # Log the action
        CourseSelectionAuditLog.objects.create(
            student=student,
            course=course,
            level=level,
            department=student.department,
            action='CREATE' if created else 'UPDATE',
            old_is_offered=None if created else (not selection.is_offered),
            new_is_offered=True,
            change_reason='Timetable course marked as offering (auto-approved)'
        )
        
        return selection


def mark_timetable_course_not_offering(student, course, level):
    """
    Marks a timetable course as "not offering" for a student.
    Sets is_offered=False.
    
    Args:
        student: Student instance
        course: Course instance
        level: Level instance
    
    Returns:
        StudentCourseSelection: The updated selection, or None if deleted
    """
    with transaction.atomic():
        try:
            selection = StudentCourseSelection.objects.get(
                student=student,
                course=course,
                level=level
            )
            
            old_is_offered = selection.is_offered
            selection.is_offered = False
            selection.is_approved = False  # Remove approval when not offering
            selection.save()
            
            # Log the action
            CourseSelectionAuditLog.objects.create(
                student=student,
                course=course,
                level=level,
                department=student.department,
                action='UPDATE',
                old_is_offered=old_is_offered,
                new_is_offered=False,
                change_reason='Timetable course marked as not offering'
            )
            
            return selection
            
        except StudentCourseSelection.DoesNotExist:
            # Create a new record with is_offered=False
            selection = StudentCourseSelection.objects.create(
                student=student,
                course=course,
                level=level,
                department=student.department,
                is_offered=False,
                is_approved=False
            )
            
            # Log the action
            CourseSelectionAuditLog.objects.create(
                student=student,
                course=course,
                level=level,
                department=student.department,
                action='CREATE',
                old_is_offered=None,
                new_is_offered=False,
                change_reason='Timetable course marked as not offering'
            )
            
            return selection


def get_timetable_for_student(student, academic_level):
    """
    Returns timetable courses for a student's level,
    excluding courses already approved through direct registration from other levels.
    
    Args:
        student: Student instance
        academic_level: Level instance
    
    Returns:
        list: List of dicts with course info and selection status
    """
    # Get all courses for the academic level from timetable
    timetable_slots = TimetableSlot.objects.filter(
        level=academic_level,
        timetable__department=student.department
    ).select_related('course').distinct()
    
    # Get unique courses from timetable slots
    level_courses = Course.objects.filter(
        id__in=timetable_slots.values_list('course_id', flat=True)
    ).distinct()
    
    # Get courses already approved through direct registration from other levels
    approved_other_level = StudentCourseSelection.objects.filter(
        student=student,
        is_approved=True,
        is_offered=True
    ).exclude(
        level=academic_level
    ).values_list('course_id', flat=True)
    
    # Build timetable with selection status
    timetable = []
    for course in level_courses:
        # Skip if already approved from another level
        if course.id in approved_other_level:
            continue
            
        # Get selection for this course at this level
        selection = StudentCourseSelection.objects.filter(
            student=student,
            course=course,
            level=academic_level
        ).first()
        
        timetable.append({
            'course': course,
            'is_offered': selection.is_offered if selection else False,
            'is_approved': selection.is_approved if selection else False,
            'source': 'timetable',
            'selection_id': selection.id if selection else None
        })
    
    return timetable
