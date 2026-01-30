from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from datetime import time
from .models import Level, TimetableSlot
from academics.models import Course
from institutions.models import Department
from .serializers import (
    LevelSerializer, 
    TimetableSlotSerializer,
    TimetableSlotCreateSerializer
)

User = get_user_model()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_department_timetable(request, department_id):
    """
    Get the timetable for a specific department
    """
    try:
        # Validate department_id
        if not department_id:
            return Response({'error': 'Department ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        department = get_object_or_404(Department, id=department_id)
        
        # Get or create timetable for department
        timetable, created = DepartmentTimetable.objects.get_or_create(
            department=department,
            defaults={
                'name': f'Timetable for {department.name}',
                'description': f'Default timetable for {department.name}'
            }
        )
        
        # Get all related data
        levels = Level.objects.filter(department=department)
        lecturers = Lecturer.objects.filter(department=department)
        courses = Course.objects.filter(department=department)
        slots = TimetableSlot.objects.filter(timetable=timetable).select_related(
            'level', 'course', 'lecturer'
        )
        
        # Prepare response data
        response_data = {
            'timetable': DepartmentTimetableSerializer(timetable).data,
            'levels': LevelSerializer(levels, many=True).data,
            'lecturers': LecturerSerializer(lecturers, many=True).data,
            'courses': [
                {
                    'id': course.id,
                    'code': course.code,
                    'title': course.title,
                    'level': course.level,
                    'department_id': course.department.id
                } for course in courses
            ],
            'slots': TimetableSlotSerializer(slots, many=True).data
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    except Department.DoesNotExist:
        return Response({'error': f'Department with ID {department_id} not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        import traceback
        error_details = {
            'error': str(e),
            'traceback': traceback.format_exc(),
            'department_id': department_id
        }
        return Response(error_details, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


def check_timetable_conflicts(timetable, level, course, lecturer, day_of_week, start_time, end_time, exclude_slot_id=None):
    """
    Check for conflicts in the timetable
    Only check for overlapping time slots, not exact matches
    """
    conflicts = []

    # Check for level-time conflicts (overlapping, not exact matches)
    level_conflicts = TimetableSlot.objects.filter(
        timetable=timetable,
        level=level,
        day_of_week=day_of_week
    ).filter(
        # Only check for actual overlaps, not exact matches
        Q(start_time__lt=end_time, end_time__gt=start_time) &
        ~Q(start_time=start_time, end_time=end_time)
    )
    if exclude_slot_id:
        level_conflicts = level_conflicts.exclude(id=exclude_slot_id)

    if level_conflicts.exists():
        conflicts.append({
            'type': 'level_time',
            'message': f'Level {level.name} already has a course scheduled during this time period',
            'conflicting_slot': TimetableSlotSerializer(level_conflicts.first()).data
        })

    # Check for course-time conflicts (overlapping, not exact matches)
    course_conflicts = TimetableSlot.objects.filter(
        timetable=timetable,
        course=course,
        day_of_week=day_of_week
    ).filter(
        # Only check for actual overlaps, not exact matches
        Q(start_time__lt=end_time, end_time__gt=start_time) &
        ~Q(start_time=start_time, end_time=end_time)
    )
    if exclude_slot_id:
        course_conflicts = course_conflicts.exclude(id=exclude_slot_id)

    if course_conflicts.exists():
        conflicts.append({
            'type': 'course_time',
            'message': f'Course {course.code} is already scheduled during this time period',
            'conflicting_slot': TimetableSlotSerializer(course_conflicts.first()).data
        })

    # Check for lecturer-time conflicts (overlapping, not exact matches)
    lecturer_conflicts = TimetableSlot.objects.filter(
        timetable=timetable,
        lecturer=lecturer,
        day_of_week=day_of_week
    ).filter(
        # Only check for actual overlaps, not exact matches
        Q(start_time__lt=end_time, end_time__gt=start_time) &
        ~Q(start_time=start_time, end_time=end_time)
    )
    if exclude_slot_id:
        lecturer_conflicts = lecturer_conflicts.exclude(id=exclude_slot_id)

    if lecturer_conflicts.exists():
        conflicts.append({
            'type': 'lecturer_time',
            'message': f'Lecturer {lecturer.user.get_full_name()} is already assigned to another class during this time period',
            'conflicting_slot': TimetableSlotSerializer(lecturer_conflicts.first()).data
        })

    return conflicts


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_timetable_slot(request, department_id):
    """
    Create a new timetable slot with validation
    """
    try:
        department = get_object_or_404(Department, id=department_id)

        # Get or create timetable for department
        timetable, created = DepartmentTimetable.objects.get_or_create(
            department=department,
            defaults={
                'name': f'Timetable for {department.name}',
                'description': f'Default timetable for {department.name}'
            }
        )

        # Validate and create slot
        serializer = TimetableSlotCreateSerializer(data=request.data)
        if serializer.is_valid():
            # Perform additional validation for conflicts
            slot_data = serializer.validated_data

            # Get related objects
            level = get_object_or_404(Level, id=slot_data['level'].id if hasattr(slot_data['level'], 'id') else slot_data['level'])
            course = get_object_or_404(Course, id=slot_data['course'].id if hasattr(slot_data['course'], 'id') else slot_data['course'])
            lecturer = get_object_or_404(Lecturer, id=slot_data['lecturer'].id if hasattr(slot_data['lecturer'], 'id') else slot_data['lecturer'])

            # Check for conflicts
            conflicts = check_timetable_conflicts(
                timetable=timetable,
                level=level,
                course=course,
                lecturer=lecturer,
                day_of_week=slot_data['day_of_week'],
                start_time=slot_data['start_time'],
                end_time=slot_data['end_time']
            )

            if conflicts:
                return Response(
                    {'error': 'Schedule conflicts detected', 'conflicts': conflicts},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the slot
            slot = TimetableSlot.objects.create(
                timetable=timetable,
                level=level,
                course=course,
                lecturer=lecturer,
                day_of_week=slot_data['day_of_week'],
                start_time=slot_data['start_time'],
                end_time=slot_data['end_time'],
                venue=slot_data.get('venue', '')
            )

            return Response(
                TimetableSlotSerializer(slot).data,
                status=status.HTTP_201_CREATED
            )
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_timetable_slot(request, department_id, slot_id):
    """
    Update or delete a timetable slot
    """
    try:
        department = get_object_or_404(Department, id=department_id)
        timetable = get_object_or_404(DepartmentTimetable, department=department)
        slot = get_object_or_404(TimetableSlot, id=slot_id, timetable=timetable)
        
        if request.method == 'PUT':
            # Update slot with validation
            serializer = TimetableSlotCreateSerializer(slot, data=request.data)
            if serializer.is_valid():
                # Perform conflict validation
                slot_data = serializer.validated_data

                # Get related objects
                level = get_object_or_404(Level, id=slot_data['level'].id if hasattr(slot_data['level'], 'id') else slot_data['level'])
                course = get_object_or_404(Course, id=slot_data['course'].id if hasattr(slot_data['course'], 'id') else slot_data['course'])
                lecturer = get_object_or_404(Lecturer, id=slot_data['lecturer'].id if hasattr(slot_data['lecturer'], 'id') else slot_data['lecturer'])

                # Check for conflicts (excluding current slot)
                conflicts = check_timetable_conflicts(
                    timetable=timetable,
                    level=level,
                    course=course,
                    lecturer=lecturer,
                    day_of_week=slot_data['day_of_week'],
                    start_time=slot_data['start_time'],
                    end_time=slot_data['end_time'],
                    exclude_slot_id=slot_id
                )

                if conflicts:
                    return Response(
                        {'error': 'Schedule conflicts detected', 'conflicts': conflicts},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Update the slot
                slot.level = level
                slot.course = course
                slot.lecturer = lecturer
                slot.day_of_week = slot_data['day_of_week']
                slot.start_time = slot_data['start_time']
                slot.end_time = slot_data['end_time']
                slot.venue = slot_data.get('venue', '')
                slot.save()

                return Response(TimetableSlotSerializer(slot).data)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        elif request.method == 'DELETE':
            slot.delete()
            return Response({'message': 'Timetable slot deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_department_levels(request, department_id):
    """
    Get all levels for a specific department
    """
    try:
        department = get_object_or_404(Department, id=department_id)
        levels = Level.objects.filter(department=department)
        serializer = LevelSerializer(levels, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_level(request, department_id):
    """
    Create a new level for a department
    """
    try:
        department = get_object_or_404(Department, id=department_id)
        
        # Check if level already exists for this department
        name = request.data.get('name')
        code = request.data.get('code')
        
        if Level.objects.filter(department=department, name=name).exists():
            return Response(
                {'error': 'Level with this name already exists in this department'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if Level.objects.filter(code=code).exists():
            return Response(
                {'error': 'Level with this code already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        level = Level.objects.create(
            name=name,
            code=code,
            department=department
        )
        
        serializer = LevelSerializer(level)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_department_lecturers(request, department_id):
    """
    Get all lecturers for a specific department
    """
    try:
        department = get_object_or_404(Department, id=department_id)
        lecturers = Lecturer.objects.filter(department=department)
        serializer = LecturerSerializer(lecturers, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_lecturer(request, department_id):
    """
    Create a new lecturer for a department
    """
    try:
        department = get_object_or_404(Department, id=department_id)
        
        # Get user data
        user_email = request.data.get('email')
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        employee_id = request.data.get('employee_id')
        specialization = request.data.get('specialization', '')
        
        # Check if user already exists
        user, created = User.objects.get_or_create(
            email=user_email,
            defaults={
                'username': user_email,
                'first_name': first_name,
                'last_name': last_name
            }
        )
        
        if not created:
            # Update user if already exists
            user.first_name = first_name
            user.last_name = last_name
            user.save()
        
        # Check if lecturer already exists
        if Lecturer.objects.filter(employee_id=employee_id).exists():
            return Response(
                {'error': 'Lecturer with this employee ID already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        lecturer = Lecturer.objects.create(
            user=user,
            employee_id=employee_id,
            department=department,
            specialization=specialization
        )
        
        serializer = LecturerSerializer(lecturer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_timetable_conflicts_endpoint(request, department_id):
    """
    Check for timetable conflicts without creating a slot
    """
    try:
        department = get_object_or_404(Department, id=department_id)
        timetable = get_object_or_404(DepartmentTimetable, department=department)

        # Get required data from request
        level_id = request.data.get('level_id')
        course_id = request.data.get('course_id')
        lecturer_id = request.data.get('lecturer_id')
        day_of_week = request.data.get('day_of_week')
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        slot_id = request.data.get('slot_id')  # Optional: for updates

        if not all([level_id, course_id, lecturer_id, day_of_week, start_time, end_time]):
            return Response(
                {'error': 'Missing required fields'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get related objects
        level = get_object_or_404(Level, id=level_id)
        course = get_object_or_404(Course, id=course_id)
        lecturer = get_object_or_404(Lecturer, id=lecturer_id)

        # Parse time strings to time objects
        from datetime import datetime
        start_time_obj = datetime.strptime(start_time, '%H:%M').time()
        end_time_obj = datetime.strptime(end_time, '%H:%M').time()

        # Check for conflicts
        conflicts = check_timetable_conflicts(
            timetable=timetable,
            level=level,
            course=course,
            lecturer=lecturer,
            day_of_week=day_of_week,
            start_time=start_time_obj,
            end_time=end_time_obj,
            exclude_slot_id=slot_id
        )

        return Response({
            'has_conflicts': len(conflicts) > 0,
            'conflicts': conflicts
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_department_courses(request, department_id):
    """
    Get all courses for a specific department
    """
    try:
        department = get_object_or_404(Department, id=department_id)
        courses = Course.objects.filter(department=department)
        data = [
            {
                'id': course.id,
                'code': course.code,
                'title': course.title,
                'level': course.level,
                'department_id': course.department.id
            } for course in courses
        ]
        return Response(data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)