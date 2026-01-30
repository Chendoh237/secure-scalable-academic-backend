"""
API views for Student Timetable Module.

This module provides REST API endpoints for students to:
1. Select their academic level
2. View their department-specific timetable
3. Manage their course selections
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError

from .models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import Level, Course, TimetableSlot, Timetable
from institutions.models import Department
from students.signals import AuditContext
from students.monitoring import monitor_performance
from students.caching import (
    get_cached_levels, 
    get_cached_timetable, 
    get_cached_course_selections,
    StudentTimetableCacheManager
)
from students.monitoring import monitor_performance


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@monitor_performance('get_available_levels')
def get_available_levels(request):
    """
    Get available academic levels for the authenticated student's department.
    
    Returns:
        JSON response with available levels for student's department
        
    Requirements: 1.1, 1.2, 6.1
    """
    try:
        # Get the student profile for the authenticated user
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student profile not found for this user'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if student has a department
        if not student.department:
            return Response(
                {'error': 'Student is not assigned to any department'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get levels for student's department using cache
        levels_data = get_cached_levels(student.department.id)
        
        return Response({
            'levels': levels_data,
            'student_department': student.department.name
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve levels: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@monitor_performance('manage_level_selection')
def manage_level_selection(request):
    """
    Get or set the student's selected academic level.
    
    GET: Returns current level selection
    POST: Sets new level selection and auto-populates default courses
    
    Requirements: 1.4, 4.2
    """
    try:
        # Get the student profile for the authenticated user
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student profile not found for this user'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if request.method == 'GET':
            # Return current level selection
            try:
                level_selection = student.level_selection
                return Response({
                    'level_selection': {
                        'id': level_selection.level.id,
                        'name': level_selection.level.name,
                        'code': level_selection.level.code,
                        'selected_at': level_selection.selected_at.isoformat(),
                        'updated_at': level_selection.updated_at.isoformat()
                    }
                })
            except StudentLevelSelection.DoesNotExist:
                return Response({
                    'level_selection': None,
                    'message': 'No level selected yet'
                })
        
        elif request.method == 'POST':
            # Set new level selection
            level_id = request.data.get('level_id')
            
            if not level_id:
                return Response(
                    {'error': 'level_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                level = Level.objects.get(id=level_id)
            except Level.DoesNotExist:
                return Response(
                    {'error': 'Level not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Validate that level belongs to student's department
            if level.department != student.department:
                return Response(
                    {'error': 'Selected level must belong to your department'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                with transaction.atomic():
                    # Update or create level selection
                    level_selection, created = StudentLevelSelection.objects.update_or_create(
                        student=student,
                        defaults={'level': level}
                    )
                    
                    # Clear existing course selections when level changes
                    if not created:  # If updating existing selection
                        StudentCourseSelection.objects.filter(
                            student=student
                        ).delete()
                    
                    # Auto-populate default courses for the selected level
                    from courses.models import TimetableSlot, DepartmentTimetable
                    
                    try:
                        department_timetable = DepartmentTimetable.objects.get(
                            department=student.department
                        )
                        
                        # Get all courses scheduled for this level
                        timetable_slots = TimetableSlot.objects.filter(
                            timetable=department_timetable,
                            level=level
                        ).select_related('course')
                        
                        # Create course selections for all timetable courses (auto-approved)
                        courses_added = 0
                        for slot in timetable_slots:
                            course_selection, selection_created = StudentCourseSelection.objects.get_or_create(
                                student=student,
                                department=student.department,
                                level=level,
                                course=slot.course,
                                defaults={
                                    'is_offered': True,
                                    'is_approved': True  # Auto-approve timetable courses
                                }
                            )
                            if selection_created:
                                courses_added += 1
                        
                        return Response({
                            'message': 'Level selection updated successfully',
                            'level_selection': {
                                'id': level_selection.level.id,
                                'name': level_selection.level.name,
                                'code': level_selection.level.code,
                                'selected_at': level_selection.selected_at.isoformat(),
                                'updated_at': level_selection.updated_at.isoformat()
                            },
                            'created': created,
                            'courses_added': courses_added,
                            'auto_populated': True
                        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
                        
                    except DepartmentTimetable.DoesNotExist:
                        # No timetable found, just return level selection
                        return Response({
                            'message': 'Level selection updated successfully (no timetable found)',
                            'level_selection': {
                                'id': level_selection.level.id,
                                'name': level_selection.level.name,
                                'code': level_selection.level.code,
                                'selected_at': level_selection.selected_at.isoformat(),
                                'updated_at': level_selection.updated_at.isoformat()
                            },
                            'created': created,
                            'courses_added': 0,
                            'auto_populated': False
                        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
                    
            except ValidationError as e:
                return Response(
                    {'error': f'Validation error: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except IntegrityError as e:
                return Response(
                    {'error': f'Database error: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
    
    except Exception as e:
        return Response(
            {'error': f'Failed to manage level selection: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@monitor_performance('get_student_timetable')
def get_student_timetable(request):
    """
    Get timetable data for student's department and selected level.
    
    Query Parameters:
        level_id (optional): Override the student's selected level
        
    Requirements: 1.4, 1.5, 6.2
    """
    try:
        # Get the student profile for the authenticated user
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student profile not found for this user'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get level from query parameter or student's selection
        level_id = request.GET.get('level_id')
        
        if level_id:
            try:
                level = Level.objects.get(id=level_id)
                # Validate that level belongs to student's department
                if level.department != student.department:
                    return Response(
                        {'error': 'Level must belong to your department'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except Level.DoesNotExist:
                return Response(
                    {'error': 'Level not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Use student's selected level
            try:
                level_selection = student.level_selection
                level = level_selection.level
            except StudentLevelSelection.DoesNotExist:
                return Response(
                    {'error': 'No level selected. Please select a level first.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Get department timetable
        try:
            department_timetable = DepartmentTimetable.objects.get(
                department=student.department
            )
        except DepartmentTimetable.DoesNotExist:
            return Response(
                {'error': 'No timetable found for your department'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get timetable data using cache
        timetable_data = get_cached_timetable(student.department.id, level.id)
        
        return Response({
            'timetable': timetable_data,
            'level': {
                'id': level.id,
                'name': level.name,
                'code': level.code
            },
            'department': student.department.name,
            'total_slots': len(timetable_data)
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve timetable: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@monitor_performance('manage_course_selections')
def manage_course_selections(request):
    """
    Get or update student's course selections.
    
    GET: Returns current course selections
    POST: Updates course selections
    
    Requirements: 3.4, 3.5, 4.2, 4.3, 6.3, 6.4, 6.5
    """
    try:
        # Get the student profile for the authenticated user
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student profile not found for this user'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Ensure student has selected a level
        try:
            level_selection = student.level_selection
            level = level_selection.level
        except StudentLevelSelection.DoesNotExist:
            return Response(
                {'error': 'No level selected. Please select a level first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if request.method == 'GET':
            # Return current course selections using cache
            selections_data = get_cached_course_selections(student.id, level.id)
            
            return Response({
                'course_selections': selections_data,
                'level': {
                    'id': level.id,
                    'name': level.name,
                    'code': level.code
                },
                'total_selections': len(selections_data)
            })
        
        elif request.method == 'POST':
            # Update course selections with audit logging
            selections_data = request.data.get('selections', [])
            
            if not isinstance(selections_data, list):
                return Response(
                    {'error': 'selections must be a list'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                # Use audit context to capture request information
                with AuditContext(request=request, change_reason="Course selections updated via API"):
                    with transaction.atomic():
                        updated_selections = []
                        
                        for selection_data in selections_data:
                            course_id = selection_data.get('course_id')
                            is_offered = selection_data.get('is_offered', True)
                            
                            if not course_id:
                                return Response(
                                    {'error': 'course_id is required for each selection'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                            
                            try:
                                course = Course.objects.get(id=course_id)
                            except Course.DoesNotExist:
                                return Response(
                                    {'error': f'Course with id {course_id} not found'},
                                    status=status.HTTP_404_NOT_FOUND
                                )
                            
                            # Validate that course belongs to student's department
                            if course.department != student.department:
                                return Response(
                                    {'error': f'Course {course.code} does not belong to your department'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                            
                            # Validate that course is scheduled for student's level
                            if not TimetableSlot.objects.filter(
                                course=course,
                                level=level,
                                timetable__department=student.department
                            ).exists():
                                return Response(
                                    {'error': f'Course {course.code} is not scheduled for your level'},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                            
                            # Update or create course selection (audit logging happens automatically via signals)
                            # Auto-approve timetable courses when marked as offering
                            course_selection, created = StudentCourseSelection.objects.update_or_create(
                                student=student,
                                department=student.department,
                                level=level,
                                course=course,
                                defaults={
                                    'is_offered': is_offered,
                                    'is_approved': is_offered  # Auto-approve when is_offered=True
                                }
                            )
                            
                            updated_selections.append({
                                'id': course_selection.id,
                                'course': {
                                    'id': course.id,
                                    'code': course.code,
                                    'title': course.title
                                },
                                'is_offered': course_selection.is_offered,
                                'created': created
                            })
                        
                        # Invalidate cache after successful updates
                        StudentTimetableCacheManager.invalidate_course_selections_cache(
                            student.id, level.id
                        )
                        StudentTimetableCacheManager.invalidate_department_stats_cache(
                            student.department.id
                        )
                        
                        return Response({
                            'message': 'Course selections updated successfully',
                            'updated_selections': updated_selections,
                            'total_updated': len(updated_selections),
                            'audit_logged': True  # Indicate that changes were logged
                        })
                    
            except ValidationError as e:
                return Response(
                    {'error': f'Validation error: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except IntegrityError as e:
                return Response(
                    {'error': f'Database error: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
    
    except Exception as e:
        return Response(
            {'error': f'Failed to manage course selections: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )