"""
API views for Course Selection Audit Trail Management.

This module provides REST API endpoints for administrators to:
1. View audit logs for course selection changes
2. Get audit summaries for students and departments
3. Export audit data for compliance purposes
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
import csv
from django.http import HttpResponse

from .models import Student, CourseSelectionAuditLog
from courses.models import Course, Level
from institutions.models import Department
from students.services.audit_service import CourseSelectionAuditService


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_audit_logs(request):
    """
    Get paginated audit logs with filtering options.
    
    Query Parameters:
        page (int): Page number (default: 1)
        page_size (int): Items per page (default: 20, max: 100)
        student_id (int): Filter by student ID
        course_id (int): Filter by course ID
        action (str): Filter by action type (CREATE, UPDATE, DELETE)
        department_id (int): Filter by department ID
        date_from (str): Filter from date (YYYY-MM-DD format)
        date_to (str): Filter to date (YYYY-MM-DD format)
        search (str): Search in student name, matric number, or course code
    """
    try:
        # Get query parameters
        page = int(request.GET.get('page', 1))
        page_size = min(int(request.GET.get('page_size', 20)), 100)
        student_id = request.GET.get('student_id')
        course_id = request.GET.get('course_id')
        action = request.GET.get('action')
        department_id = request.GET.get('department_id')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        search = request.GET.get('search')
        
        # Build queryset
        queryset = CourseSelectionAuditLog.objects.select_related(
            'student', 'course', 'level', 'department'
        ).all()
        
        # Apply filters
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        
        if action:
            queryset = queryset.filter(action=action.upper())
        
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        
        if date_from:
            try:
                from_date = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__gte=from_date)
            except ValueError:
                return Response(
                    {'error': 'Invalid date_from format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if date_to:
            try:
                to_date = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__lte=to_date)
            except ValueError:
                return Response(
                    {'error': 'Invalid date_to format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if search:
            queryset = queryset.filter(
                Q(student__matric_number__icontains=search) |
                Q(student__full_name__icontains=search) |
                Q(course__code__icontains=search) |
                Q(course__title__icontains=search)
            )
        
        # Paginate results
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)
        
        # Format response data
        logs_data = []
        for log in page_obj:
            logs_data.append({
                'id': log.id,
                'student': {
                    'id': log.student.id,
                    'matric_number': log.student.matric_number,
                    'full_name': log.student.full_name
                },
                'course': {
                    'id': log.course.id,
                    'code': log.course.code,
                    'title': log.course.title
                },
                'level': {
                    'id': log.level.id,
                    'name': log.level.name,
                    'code': log.level.code
                },
                'department': {
                    'id': log.department.id,
                    'name': log.department.name,
                    'code': log.department.code
                },
                'action': log.action,
                'old_is_offered': log.old_is_offered,
                'new_is_offered': log.new_is_offered,
                'change_summary': log.change_summary,
                'timestamp': log.timestamp.isoformat(),
                'ip_address': log.ip_address,
                'change_reason': log.change_reason,
                'batch_id': str(log.batch_id) if log.batch_id else None
            })
        
        return Response({
            'logs': logs_data,
            'pagination': {
                'current_page': page_obj.number,
                'total_pages': paginator.num_pages,
                'total_items': paginator.count,
                'page_size': page_size,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous()
            },
            'filters_applied': {
                'student_id': student_id,
                'course_id': course_id,
                'action': action,
                'department_id': department_id,
                'date_from': date_from,
                'date_to': date_to,
                'search': search
            }
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to retrieve audit logs: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_student_audit_summary(request, student_id):
    """
    Get audit summary for a specific student.
    """
    try:
        try:
            student = Student.objects.get(id=student_id)
        except Student.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        summary = CourseSelectionAuditService.get_audit_summary_for_student(student)
        return Response(summary)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get student audit summary: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_department_audit_summary(request, department_id):
    """
    Get audit summary for a specific department.
    """
    try:
        try:
            department = Department.objects.get(id=department_id)
        except Department.DoesNotExist:
            return Response(
                {'error': 'Department not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        summary = CourseSelectionAuditService.get_department_audit_summary(department)
        return Response(summary)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get department audit summary: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def get_audit_statistics(request):
    """
    Get overall audit statistics and recent activity.
    """
    try:
        # Overall statistics
        total_logs = CourseSelectionAuditLog.objects.count()
        
        # Action counts
        action_stats = {}
        for action, _ in CourseSelectionAuditLog.ACTION_CHOICES:
            action_stats[action.lower()] = CourseSelectionAuditLog.objects.filter(action=action).count()
        
        # Recent activity (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_activity = CourseSelectionAuditLog.objects.filter(
            timestamp__gte=week_ago
        ).count()
        
        # Most active students (last 30 days)
        month_ago = timezone.now() - timedelta(days=30)
        active_students = CourseSelectionAuditLog.objects.filter(
            timestamp__gte=month_ago
        ).values(
            'student__id', 'student__matric_number', 'student__full_name'
        ).annotate(
            change_count=Count('id')
        ).order_by('-change_count')[:10]
        
        # Most modified courses (last 30 days)
        active_courses = CourseSelectionAuditLog.objects.filter(
            timestamp__gte=month_ago
        ).values(
            'course__id', 'course__code', 'course__title'
        ).annotate(
            change_count=Count('id')
        ).order_by('-change_count')[:10]
        
        # Department activity
        dept_activity = CourseSelectionAuditLog.objects.values(
            'department__id', 'department__name', 'department__code'
        ).annotate(
            change_count=Count('id')
        ).order_by('-change_count')
        
        return Response({
            'total_logs': total_logs,
            'action_statistics': action_stats,
            'recent_activity_count': recent_activity,
            'most_active_students': list(active_students),
            'most_modified_courses': list(active_courses),
            'department_activity': list(dept_activity),
            'generated_at': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get audit statistics: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def export_audit_logs(request):
    """
    Export audit logs to CSV format.
    
    Query Parameters:
        Same as get_audit_logs endpoint for filtering
        format (str): Export format ('csv' only for now)
    """
    try:
        export_format = request.GET.get('format', 'csv').lower()
        
        if export_format != 'csv':
            return Response(
                {'error': 'Only CSV format is currently supported'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Build queryset with same filtering logic as get_audit_logs
        queryset = CourseSelectionAuditLog.objects.select_related(
            'student', 'course', 'level', 'department'
        ).all()
        
        # Apply filters (same logic as get_audit_logs)
        student_id = request.GET.get('student_id')
        course_id = request.GET.get('course_id')
        action = request.GET.get('action')
        department_id = request.GET.get('department_id')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        search = request.GET.get('search')
        
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        if course_id:
            queryset = queryset.filter(course_id=course_id)
        if action:
            queryset = queryset.filter(action=action.upper())
        if department_id:
            queryset = queryset.filter(department_id=department_id)
        if date_from:
            from_date = timezone.datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(timestamp__date__gte=from_date)
        if date_to:
            to_date = timezone.datetime.strptime(date_to, '%Y-%m-%d').date()
            queryset = queryset.filter(timestamp__date__lte=to_date)
        if search:
            queryset = queryset.filter(
                Q(student__matric_number__icontains=search) |
                Q(student__full_name__icontains=search) |
                Q(course__code__icontains=search) |
                Q(course__title__icontains=search)
            )
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="course_selection_audit_logs_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'ID', 'Student Matric', 'Student Name', 'Course Code', 'Course Title',
            'Level', 'Department', 'Action', 'Old Status', 'New Status',
            'Change Summary', 'Timestamp', 'IP Address', 'Change Reason', 'Batch ID'
        ])
        
        for log in queryset.iterator():  # Use iterator for memory efficiency
            writer.writerow([
                log.id,
                log.student.matric_number,
                log.student.full_name,
                log.course.code,
                log.course.title,
                log.level.name,
                log.department.name,
                log.action,
                'Offered' if log.old_is_offered else 'Not Offered' if log.old_is_offered is not None else 'N/A',
                'Offered' if log.new_is_offered else 'Not Offered',
                log.change_summary,
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.ip_address or 'N/A',
                log.change_reason,
                str(log.batch_id) if log.batch_id else 'N/A'
            ])
        
        return response
        
    except Exception as e:
        return Response(
            {'error': f'Failed to export audit logs: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def cleanup_old_audit_logs(request):
    """
    Clean up old audit logs (admin only).
    
    POST data:
        days_to_keep (int): Number of days to retain logs (default: 365)
    """
    try:
        days_to_keep = int(request.data.get('days_to_keep', 365))
        
        if days_to_keep < 30:
            return Response(
                {'error': 'Cannot delete logs newer than 30 days for compliance reasons'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        deleted_count = CourseSelectionAuditService.cleanup_old_audit_logs(days_to_keep)
        
        return Response({
            'message': f'Successfully cleaned up {deleted_count} old audit log entries',
            'deleted_count': deleted_count,
            'days_kept': days_to_keep,
            'cleanup_date': timezone.now().isoformat()
        })
        
    except ValueError:
        return Response(
            {'error': 'days_to_keep must be a valid integer'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        return Response(
            {'error': f'Failed to cleanup audit logs: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )