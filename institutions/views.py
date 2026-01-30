from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from .models import Institution, Faculty, Department
from .program_models import AcademicProgram
from courses.models import CourseRegistration
from academics.models import Course
from students.models import Student

@api_view(['GET'])
@permission_classes([AllowAny])
def get_programs(request):
    """Get all academic programs"""
    try:
        programs = AcademicProgram.objects.all()
        data = [{'id': p.id, 'name': p.name, 'code': p.code} for p in programs]
        return Response({'data': data})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_faculties(request):
    """Get faculties by program"""
    try:
        program_id = request.GET.get('program_id')
        if program_id:
            faculties = Faculty.objects.filter(program_id=program_id)
        else:
            faculties = Faculty.objects.all()
        
        data = [{'id': f.id, 'name': f.name, 'program_id': f.program_id} for f in faculties]
        return Response({'data': data})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_departments(request):
    """Get departments by faculty"""
    try:
        faculty_id = request.GET.get('faculty_id')
        if faculty_id:
            departments = Department.objects.filter(faculty_id=faculty_id)
        else:
            departments = Department.objects.all()
        
        data = [{'id': d.id, 'name': d.name, 'faculty_id': d.faculty_id} for d in departments]
        return Response({'data': data})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_courses(request):
    """Get courses by department"""
    try:
        department_id = request.GET.get('department_id')
        if department_id:
            courses = Course.objects.filter(department_id=department_id)
        else:
            courses = Course.objects.all()
        
        data = [{
            'id': c.id, 
            'code': c.code, 
            'title': c.title,
            'credit_units': c.credit_units,
            'level': c.level,
            'semester': c.semester,
            'department_id': c.department_id
        } for c in courses]
        return Response({'data': data})
    except Exception as e:
        return Response({'error': str(e)}, status=500)

# ===== ADMIN VIEWS =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_departments(request):
    """Get all departments with enrollment statistics"""
    try:
        # Get all departments with student count
        departments = Department.objects.annotate(
            student_count=Count('course__courseoffering__students', distinct=True),
            course_count=Count('course', distinct=True)
        ).select_related('faculty', 'faculty__program').order_by('name')
        
        # Get search query if provided
        search = request.GET.get('search', '').strip()
        if search:
            departments = departments.filter(
                Q(name__icontains=search) | 
                Q(faculty__name__icontains=search) |
                Q(faculty__program__name__icontains=search)
            )
        
        # Get sort parameter
        sort_by = request.GET.get('sort', 'name')
        if sort_by == 'enrollment':
            departments = departments.order_by('-student_count', 'name')
        elif sort_by == 'courses':
            departments = departments.order_by('-course_count', 'name')
        else:
            departments = departments.order_by('name')
        
        departments_data = []
        for dept in departments:
            departments_data.append({
                'id': dept.id,
                'name': dept.name,
                'faculty_name': dept.faculty.name,
                'program_name': dept.faculty.program.name,
                'student_count': dept.student_count,
                'course_count': dept.course_count,
                'has_students': dept.student_count > 0
            })
        
        return Response({
            'success': True,
            'data': departments_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_department_detail(request, dept_id):
    """Get department details with courses"""
    try:
        department = get_object_or_404(Department, id=dept_id)
        
        # Get courses in this department
        courses = Course.objects.filter(department=department).annotate(
            student_count=Count('courseoffering__students', distinct=True)
        ).order_by('code')
        
        courses_data = []
        for course in courses:
            courses_data.append({
                'id': course.id,
                'code': course.code,
                'title': course.title,
                'credit_units': course.credit_units,
                'level': course.level,
                'semester': course.semester,
                'attendance_threshold': course.attendance_threshold,
                'student_count': course.student_count
            })
        
        department_data = {
            'id': department.id,
            'name': department.name,
            'faculty_name': department.faculty.name,
            'program_name': department.faculty.program.name,
            'courses': courses_data,
            'total_courses': len(courses_data),
            'total_students': sum(course['student_count'] for course in courses_data)
        }
        
        return Response({
            'success': True,
            'data': department_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_courses_enhanced(request):
    """Get all courses with department filtering and enhanced data"""
    try:
        courses = Course.objects.select_related('department', 'department__faculty').annotate(
            student_count=Count('courseoffering__students', distinct=True)
        )
        
        # Filter by department if provided
        department_id = request.GET.get('department')
        if department_id:
            courses = courses.filter(department_id=department_id)
        
        # Search functionality
        search = request.GET.get('search', '').strip()
        if search:
            courses = courses.filter(
                Q(code__icontains=search) |
                Q(title__icontains=search) |
                Q(department__name__icontains=search)
            )
        
        courses = courses.order_by('department__name', 'code')
        
        courses_data = []
        for course in courses:
            courses_data.append({
                'id': course.id,
                'code': course.code,
                'title': course.title,
                'credit_units': course.credit_units,
                'level': course.level,
                'semester': course.semester,
                'attendance_threshold': course.attendance_threshold,
                'student_count': course.student_count,
                'department_id': course.department.id,
                'department_name': course.department.name,
                'faculty_name': course.department.faculty.name
            })
        
        return Response({
            'success': True,
            'data': courses_data
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_course_create(request):
    """Create a new course"""
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['code', 'title', 'credit_units', 'department_id', 'level', 'semester']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'message': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if course code already exists
        if Course.objects.filter(code=data['code']).exists():
            return Response({
                'success': False,
                'message': 'Course code already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get department
        try:
            department = Department.objects.get(id=data['department_id'])
        except Department.DoesNotExist:
            return Response({
                'success': False,
                'message': 'Department not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Create course
        course = Course.objects.create(
            code=data['code'],
            title=data['title'],
            credit_units=int(data['credit_units']),
            department=department,
            level=data['level'],
            semester=data['semester'],
            attendance_threshold=int(data.get('attendance_threshold', 75))
        )
        
        return Response({
            'success': True,
            'message': 'Course created successfully',
            'data': {
                'id': course.id,
                'code': course.code,
                'title': course.title,
                'department_name': course.department.name
            }
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)