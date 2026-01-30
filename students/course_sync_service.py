"""
Course Synchronization Service

Handles synchronization between StudentCourseSelection (timetable-based) 
and StudentCourse (direct registration) models to ensure consistency
across "My Courses" and timetable views.
"""

from django.db import transaction
from django.utils import timezone
from students.models import Student, StudentCourseSelection
from courses.models import StudentCourse, CourseOffering, Course
import logging

logger = logging.getLogger(__name__)


def sync_approved_courses_to_student_course(student):
    """
    Synchronizes approved StudentCourseSelection records to StudentCourse model.
    This ensures approved courses appear in both "My Courses" and timetable views.
    
    Args:
        student: Student instance
        
    Returns:
        dict: Summary of synchronization results
    """
    try:
        with transaction.atomic():
            # Get all approved course selections for the student
            approved_selections = StudentCourseSelection.objects.filter(
                student=student,
                is_offered=True,
                is_approved=True
            ).select_related('course', 'level')
            
            synced_count = 0
            skipped_count = 0
            created_offerings = 0
            
            for selection in approved_selections:
                course = selection.course
                
                # Check if StudentCourse already exists for this course
                existing_student_course = StudentCourse.objects.filter(
                    student=student,
                    course_offering__course=course
                ).first()
                
                if existing_student_course:
                    # Ensure it's active
                    if not existing_student_course.is_active:
                        existing_student_course.is_active = True
                        existing_student_course.save()
                        synced_count += 1
                    else:
                        skipped_count += 1
                    continue
                
                # Find or create a CourseOffering for this course
                current_year = timezone.now().year
                academic_year = f"{current_year}/{current_year + 1}"
                
                course_offering, offering_created = CourseOffering.objects.get_or_create(
                    course=course,
                    academic_year=academic_year,
                    semester='1',  # Default to semester 1
                    defaults={
                        'instructor_name': 'TBA'  # To be assigned
                    }
                )
                
                if offering_created:
                    created_offerings += 1
                
                # Create StudentCourse record
                student_course, course_created = StudentCourse.objects.get_or_create(
                    student=student,
                    course_offering=course_offering,
                    defaults={
                        'is_active': True
                    }
                )
                
                if course_created:
                    synced_count += 1
                else:
                    # Ensure it's active
                    if not student_course.is_active:
                        student_course.is_active = True
                        student_course.save()
                        synced_count += 1
                    else:
                        skipped_count += 1
            
            logger.info(f"Course sync completed for student {student.matric_number}: "
                       f"{synced_count} synced, {skipped_count} skipped, "
                       f"{created_offerings} offerings created")
            
            return {
                'success': True,
                'synced_count': synced_count,
                'skipped_count': skipped_count,
                'created_offerings': created_offerings,
                'total_approved': approved_selections.count()
            }
            
    except Exception as e:
        logger.error(f"Course sync failed for student {student.matric_number}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'synced_count': 0,
            'skipped_count': 0,
            'created_offerings': 0,
            'total_approved': 0
        }


def sync_student_course_to_course_selection(student):
    """
    Synchronizes active StudentCourse records back to StudentCourseSelection.
    This ensures courses registered through direct registration appear in timetable.
    
    Args:
        student: Student instance
        
    Returns:
        dict: Summary of synchronization results
    """
    try:
        with transaction.atomic():
            # Get student's level selection
            try:
                level_selection = student.level_selection
                level = level_selection.level
            except:
                return {
                    'success': False,
                    'error': 'Student has no level selection',
                    'synced_count': 0
                }
            
            # Get all active StudentCourse records
            active_courses = StudentCourse.objects.filter(
                student=student,
                is_active=True
            ).select_related('course_offering__course')
            
            synced_count = 0
            
            for student_course in active_courses:
                course = student_course.course_offering.course
                
                # Check if StudentCourseSelection already exists
                existing_selection = StudentCourseSelection.objects.filter(
                    student=student,
                    course=course
                ).first()
                
                if not existing_selection:
                    # Create new course selection
                    StudentCourseSelection.objects.create(
                        student=student,
                        department=student.department,
                        level=level,
                        course=course,
                        is_offered=True,
                        is_approved=True
                    )
                    synced_count += 1
                elif not existing_selection.is_approved:
                    # Approve existing selection
                    existing_selection.is_approved = True
                    existing_selection.is_offered = True
                    existing_selection.save()
                    synced_count += 1
            
            logger.info(f"Reverse course sync completed for student {student.matric_number}: "
                       f"{synced_count} synced")
            
            return {
                'success': True,
                'synced_count': synced_count,
                'total_active': active_courses.count()
            }
            
    except Exception as e:
        logger.error(f"Reverse course sync failed for student {student.matric_number}: {str(e)}")
        return {
            'success': False,
            'error': str(e),
            'synced_count': 0
        }


def full_course_sync(student):
    """
    Performs a complete bidirectional synchronization between 
    StudentCourseSelection and StudentCourse models.
    
    Args:
        student: Student instance
        
    Returns:
        dict: Complete synchronization results
    """
    # First sync approved selections to student courses
    forward_sync = sync_approved_courses_to_student_course(student)
    
    # Then sync student courses back to selections
    reverse_sync = sync_student_course_to_course_selection(student)
    
    return {
        'success': forward_sync['success'] and reverse_sync['success'],
        'forward_sync': forward_sync,
        'reverse_sync': reverse_sync
    }


def auto_sync_on_login(student):
    """
    Automatically synchronizes courses when student logs in.
    This ensures consistency after login.
    
    Args:
        student: Student instance
        
    Returns:
        dict: Synchronization results
    """
    logger.info(f"Auto-syncing courses for student {student.matric_number} on login")
    return full_course_sync(student)