from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import (
    AcademicYear, Semester, Holiday, Department, Program, Course, CourseOffering
)
from .serializers import (
    AcademicYearSerializer, SemesterSerializer, HolidaySerializer,
    DepartmentSerializer, ProgramSerializer, CourseSerializer, CourseOfferingSerializer
)


# ===== ACADEMIC YEAR ENDPOINTS =====

@api_view(['GET'])
@permission_classes([AllowAny])
def get_academic_years(request):
    """Get all academic years"""
    try:
        academic_years = AcademicYear.objects.all().order_by('-name')
        serializer = AcademicYearSerializer(academic_years, many=True)
        return Response({
            'success': True,
            'count': academic_years.count(),
            'data': serializer.data
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_current_academic_year(request):
    """Get current academic year"""
    try:
        academic_year = AcademicYear.objects.get(is_current=True)
        serializer = AcademicYearSerializer(academic_year)
        return Response({
            'success': True,
            'data': serializer.data
        })
    except AcademicYear.DoesNotExist:
        return Response({
            'success': False,
            'message': 'No current academic year set'
        }, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_academic_year(request):
    """Create a new academic year (admin only)"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = AcademicYearSerializer(data=request.data)
    if serializer.is_valid():
        academic_year = serializer.save()
        return Response({
            'success': True,
            'message': 'Academic year created successfully',
            'data': AcademicYearSerializer(academic_year).data
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


# ===== SEMESTER ENDPOINTS =====

@api_view(['GET'])
@permission_classes([AllowAny])
def get_semesters(request):
    """Get all semesters or semesters for a specific academic year"""
    try:
        academic_year_id = request.query_params.get('academic_year_id')
        
        if academic_year_id:
            semesters = Semester.objects.filter(academic_year_id=academic_year_id)
        else:
            semesters = Semester.objects.all()
        
        serializer = SemesterSerializer(semesters, many=True)
        return Response({
            'success': True,
            'count': semesters.count(),
            'data': serializer.data
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_current_semester(request):
    """Get current active semester"""
    try:
        semester = Semester.objects.get(is_current=True)
        serializer = SemesterSerializer(semester)
        return Response({
            'success': True,
            'data': serializer.data
        })
    except Semester.DoesNotExist:
        return Response({
            'success': False,
            'message': 'No current semester set'
        }, status=status.HTTP_404_NOT_FOUND)


# ===== STUDENT LEVEL ENDPOINTS =====

@api_view(['GET'])
@permission_classes([AllowAny])
def get_student_levels(request):
    """Get all student levels"""
    try:
        levels = StudentLevel.objects.all().order_by('code')
        serializer = StudentLevelSerializer(levels, many=True)
        return Response({
            'success': True,
            'count': levels.count(),
            'data': serializer.data
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_student_level_detail(request, level_id):
    """Get specific student level details"""
    try:
        level = get_object_or_404(StudentLevel, id=level_id)
        serializer = StudentLevelSerializer(level)
        return Response({
            'success': True,
            'data': serializer.data
        })
    except StudentLevel.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Level not found'
        }, status=status.HTTP_404_NOT_FOUND)


# ===== GRADE SCALE ENDPOINTS =====

@api_view(['GET'])
@permission_classes([AllowAny])
def get_grade_scales(request):
    """Get all grade scales"""
    try:
        scales = GradeScale.objects.all().prefetch_related('grades')
        serializer = GradeScaleSerializer(scales, many=True)
        return Response({
            'success': True,
            'count': scales.count(),
            'data': serializer.data
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_grade_scale_detail(request, scale_id):
    """Get specific grade scale with all grade points"""
    try:
        scale = get_object_or_404(GradeScale.objects.prefetch_related('grades'), id=scale_id)
        serializer = GradeScaleSerializer(scale)
        return Response({
            'success': True,
            'data': serializer.data
        })
    except GradeScale.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Grade scale not found'
        }, status=status.HTTP_404_NOT_FOUND)


# ===== COURSE CATEGORY ENDPOINTS =====

@api_view(['GET'])
@permission_classes([AllowAny])
def get_course_categories(request):
    """Get all course categories"""
    try:
        categories = CourseCategory.objects.all()
        serializer = CourseCategorySerializer(categories, many=True)
        return Response({
            'success': True,
            'count': categories.count(),
            'data': serializer.data
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_course_category_detail(request, category_id):
    """Get specific course category"""
    try:
        category = get_object_or_404(CourseCategory, id=category_id)
        serializer = CourseCategorySerializer(category)
        return Response({
            'success': True,
            'data': serializer.data
        })
    except CourseCategory.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Course category not found'
        }, status=status.HTTP_404_NOT_FOUND)


# ===== ADMIN ENDPOINTS =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_create_grade_scale(request):
    """Create new grade scale (admin only)"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = GradeScaleSerializer(data=request.data)
    if serializer.is_valid():
        grade_scale = serializer.save()
        return Response({
            'success': True,
            'message': 'Grade scale created successfully',
            'data': GradeScaleSerializer(grade_scale).data
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_create_course_category(request):
    """Create new course category (admin only)"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    serializer = CourseCategorySerializer(data=request.data)
    if serializer.is_valid():
        category = serializer.save()
        return Response({
            'success': True,
            'message': 'Course category created successfully',
            'data': CourseCategorySerializer(category).data
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_academics_overview(request):
    """Get academic system overview (admin only)"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Permission denied'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        return Response({
            'success': True,
            'data': {
                'academic_years_count': AcademicYear.objects.count(),
                'current_academic_year': AcademicYearSerializer(
                    AcademicYear.objects.get(is_current=True)
                ).data if AcademicYear.objects.filter(is_current=True).exists() else None,
                'semesters_count': Semester.objects.count(),
                'current_semester': SemesterSerializer(
                    Semester.objects.get(is_current=True)
                ).data if Semester.objects.filter(is_current=True).exists() else None,
                'student_levels_count': StudentLevel.objects.count(),
                'grade_scales_count': GradeScale.objects.count(),
                'course_categories_count': CourseCategory.objects.count(),
            }
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

