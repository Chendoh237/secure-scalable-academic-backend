from django.shortcuts import render

# Create your views here.
# backend/users/views.py
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q, Avg
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
import json
from .models import User, UserProfile, DepartmentAdmin, AuditLog
from students.models import Student
from attendance.models import Attendance
from datetime import datetime, timedelta


def log_admin_activity(request, action, description=''):
    """Log admin activity"""
    if request.user.is_authenticated and request.user.is_admin_user():
        AdminActivity.objects.create(
            admin=request.user,
            action=action,
            description=description,
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@api_view(['POST'])
@permission_classes([AllowAny])
@csrf_exempt
def admin_login_view(request):
    """Admin login with email/password"""
    try:
        data = json.loads(request.body)
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return Response({
                'success': False,
                'message': 'Email and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Try to find user by email
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            user = User.objects.get(email=email)
            # Authenticate using username (since Django authenticate expects username)
            authenticated_user = authenticate(username=user.username, password=password)
        except User.DoesNotExist:
            authenticated_user = None
        
        if authenticated_user and authenticated_user.is_staff:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(authenticated_user)
            access_token = str(refresh.access_token)
            
            return Response({
                'success': True,
                'message': 'Login successful',
                'access_token': access_token,
                'refresh_token': str(refresh),
                'user': {
                    'id': authenticated_user.id,
                    'username': authenticated_user.username,
                    'email': authenticated_user.email,
                    'first_name': authenticated_user.first_name,
                    'last_name': authenticated_user.last_name,
                    'is_staff': authenticated_user.is_staff,
                    'is_superuser': authenticated_user.is_superuser,
                }
            })
        else:
            return Response({
                'success': False,
                'message': 'Invalid credentials or insufficient permissions'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
    except json.JSONDecodeError:
        return Response({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_dashboard_stats(request):
    """Get dashboard statistics for admin"""
    if not request.user.is_staff:
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        today = timezone.now().date()
        
        # Basic stats
        total_students = Student.objects.count()
        total_admins = User.objects.filter(is_staff=True).count()
        
        # Today's stats
        today_attendance = Attendance.objects.filter(date=today).count()
        
        # Student approval status
        pending_students = Student.objects.filter(is_approved=False).count()
        approved_students = Student.objects.filter(is_approved=True).count()
        
        return Response({
            'success': True,
            'totalStudents': total_students,
            'totalCourses': 0,  # Will be updated when courses are properly connected
            'totalDepartments': 0,  # Will be updated
            'activeSessionsCount': 0,  # Will be updated
            'todayAttendanceRate': 0,  # Will be calculated
            'weeklyAttendanceRate': 0,  # Will be calculated
            'lowAttendanceAlerts': pending_students,
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def students_list(request):
    """Get list of students with filtering and pagination"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        # Query parameters
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        search = request.GET.get('search', '')
        status_filter = request.GET.get('status', 'all')
        institution_filter = request.GET.get('institution', '')
        
        # Base queryset with permissions
        queryset = User.objects.filter(role='student').select_related('student')
        
        # Apply institution filter for non-super admins
        if request.user.role != 'super_admin' and request.user.institution:
            queryset = queryset.filter(student__institution=request.user.institution)
        
        # Apply filters
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search) |
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(student__matric_number__icontains=search)
            )
        
        if status_filter == 'pending':
            queryset = queryset.filter(is_approved=False)
        elif status_filter == 'approved':
            queryset = queryset.filter(is_approved=True)
        
        if institution_filter:
            queryset = queryset.filter(student__institution__id=institution_filter)
        
        # Pagination
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        students = queryset[start:end]
        
        return Response({
            'success': True,
            'students': [
                {
                    'id': student.id,
                    'username': student.username,
                    'email': student.email,
                    'first_name': student.first_name,
                    'last_name': student.last_name,
                    'full_name': student.student.full_name if hasattr(student, 'student') else f"{student.first_name} {student.last_name}",
                    'matricule': student.student.matric_number if hasattr(student, 'student') else '',
                    'phone': student.student.phone if hasattr(student, 'student') else student.phone,
                    'institution': student.student.institution.name if hasattr(student, 'student') and student.student.institution else None,
                    'faculty': student.student.faculty.name if hasattr(student, 'student') and student.student.faculty else None,
                    'department': student.student.department.name if hasattr(student, 'student') and student.student.department else None,
                    'is_approved': student.is_approved,
                    'date_joined': student.date_joined.isoformat(),
                } for student in students
            ],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'pages': (total + page_size - 1) // page_size
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_student(request, student_id):
    """Approve or reject student registration"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = json.loads(request.body)
        approve = data.get('approve', True)
        reason = data.get('reason', '')
        
        student = User.objects.get(id=student_id, role='student')
        
        # Check permissions
        if hasattr(student, 'student') and student.student.institution:
            if not request.user.can_manage_institution(student.student.institution):
                return Response({
                    'success': False,
                    'message': 'Insufficient permissions'
                }, status=status.HTTP_403_FORBIDDEN)
        
        student.is_approved = approve
        student.save()
        
        action = 'APPROVE_STUDENT' if approve else 'REJECT_STUDENT'
        description = f"{action}: {student.username} - {reason}" if reason else f"{action}: {student.username}"
        log_admin_activity(request, action, description)
        
        return Response({
            'success': True,
            'message': f'Student {"approved" if approve else "rejected"} successfully'
        })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Student not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def login_logs(request):
    """Get login logs with filtering"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        search = request.GET.get('search', '')
        success_filter = request.GET.get('success', 'all')
        
        queryset = LoginLog.objects.all()
        
        if search:
            queryset = queryset.filter(username__icontains=search)
        
        if success_filter != 'all':
            is_success = success_filter == 'success'
            queryset = queryset.filter(success=is_success)
        
        # Pagination
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        logs = queryset[start:end]
        
        return Response({
            'success': True,
            'logs': [
                {
                    'id': log.id,
                    'username': log.username,
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent,
                    'success': log.success,
                    'failure_reason': log.failure_reason,
                    'timestamp': log.timestamp.isoformat(),
                } for log in logs
            ],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'pages': (total + page_size - 1) // page_size
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_activities(request):
    """Get admin activity logs"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 50))
        
        queryset = AdminActivity.objects.all()
        
        # Filter by admin if not super admin
        if request.user.role != 'super_admin':
            queryset = queryset.filter(admin=request.user)
        
        # Pagination
        total = queryset.count()
        start = (page - 1) * page_size
        end = start + page_size
        activities = queryset[start:end]
        
        return Response({
            'success': True,
            'activities': [
                {
                    'id': activity.id,
                    'admin': activity.admin.username,
                    'action': activity.action,
                    'description': activity.description,
                    'ip_address': activity.ip_address,
                    'timestamp': activity.timestamp.isoformat(),
                } for activity in activities
            ],
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total': total,
                'pages': (total + page_size - 1) // page_size
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_student(request):
    """Create new student (admin only)"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        data = json.loads(request.body)
        
        # Required fields
        required_fields = ['username', 'email', 'password', 'first_name', 'last_name', 'matricule', 'full_name']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'message': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user exists
        if User.objects.filter(username=data['username']).exists():
            return Response({
                'success': False,
                'message': 'Username already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if User.objects.filter(email=data['email']).exists():
            return Response({
                'success': False,
                'message': 'Email already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if Student.objects.filter(matric_number=data['matricule']).exists():
            return Response({
                'success': False,
                'message': 'Matricule already exists'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create user
        user = User.objects.create_user(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            role='student',
            is_approved=data.get('auto_approve', True)
        )
        
        # Create student profile
        student = Student.objects.create(
            user=user,
            full_name=data['full_name'],
            matric_number=data['matricule'],
            phone=data.get('phone', ''),
            address=data.get('address', ''),
            institution_id=data.get('institution_id'),
            faculty_id=data.get('faculty_id'),
            department_id=data.get('department_id')
        )
        
        # Log activity
        log_admin_activity(request, 'CREATE_STUDENT', f'Created student: {user.username}')
        
        return Response({
            'success': True,
            'message': 'Student created successfully',
            'student': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'full_name': student.full_name,
                'matricule': student.matric_number,
                'is_approved': user.is_approved,
            }
        })
        
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def manage_student(request, student_id):
    """Update or delete student"""
    if not request.user.is_admin_user():
        return Response({
            'success': False,
            'message': 'Admin access required'
        }, status=status.HTTP_403_FORBIDDEN)
    
    try:
        student = User.objects.get(id=student_id, role='student')
        
        # Check permissions
        if hasattr(student, 'student') and student.student.institution:
            if not request.user.can_manage_institution(student.student.institution):
                return Response({
                    'success': False,
                    'message': 'Insufficient permissions'
                }, status=status.HTTP_403_FORBIDDEN)
        
        if request.method == 'PUT':
            # Update student
            data = json.loads(request.body)
            
            # Update user fields
            if 'first_name' in data:
                student.first_name = data['first_name']
            if 'last_name' in data:
                student.last_name = data['last_name']
            if 'email' in data:
                student.email = data['email']
            if 'is_approved' in data:
                student.is_approved = data['is_approved']
            
            student.save()
            
            # Update student profile
            if hasattr(student, 'student'):
                student_profile = student.student
                if 'full_name' in data:
                    student_profile.full_name = data['full_name']
                if 'phone' in data:
                    student_profile.phone = data['phone']
                if 'address' in data:
                    student_profile.address = data['address']
                student_profile.save()
            
            # Log activity
            log_admin_activity(request, 'UPDATE_STUDENT', f'Updated student: {student.username}')
            
            return Response({
                'success': True,
                'message': 'Student updated successfully'
            })
            
        elif request.method == 'DELETE':
            # Delete student
            student.delete()
            
            # Log activity
            log_admin_activity(request, 'DELETE_STUDENT', f'Deleted student: {student.username}')
            
            return Response({
                'success': True,
                'message': 'Student deleted successfully'
            })
        
    except User.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Student not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Admin logout"""
    try:
        if request.user.is_authenticated:
            log_admin_activity(request, 'LOGOUT', f'Admin {request.user.username} logged out')
        
        logout(request)
        return Response({
            'success': True,
            'message': 'Logged out successfully'
        })
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)