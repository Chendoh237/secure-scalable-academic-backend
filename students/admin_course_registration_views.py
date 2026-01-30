"""
Admin Course Registration API Views

Provides REST API endpoints for admins to:
- View all pending course registrations
- Approve pending registrations
- Reject pending registrations
- View registration history
"""

from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied

from students.approval_service import (
    get_all_pending_registrations,
    approve_registration,
    reject_registration,
    get_registration_history
)


class PendingRegistrationsAdminView(APIView):
    """
    GET /api/admin/course-registrations/pending/
    Lists all pending registrations across all students.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        pending_registrations = get_all_pending_registrations()
        
        registrations_data = [
            {
                'id': selection.id,
                'student': {
                    'id': selection.student.id,
                    'name': selection.student.full_name,
                    'matric_number': selection.student.matric_number,
                    'level': selection.level.name,
                    'department': selection.department.name
                },
                'course': {
                    'id': selection.course.id,
                    'code': selection.course.code,
                    'title': selection.course.title,
                    'level': selection.level.name
                },
                'submitted_at': selection.created_at.isoformat()
            }
            for selection in pending_registrations
        ]
        
        return Response({'pending_registrations': registrations_data})


class ApproveRegistrationView(APIView):
    """
    POST /api/admin/course-registrations/{id}/approve/
    Approves a pending registration.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, registration_id):
        try:
            result = approve_registration(registration_id, request.user)
            return Response(result)
            
        except DjangoValidationError as e:
            raise ValidationError({'error': str(e), 'code': 'REGISTRATION_NOT_FOUND'})


class RejectRegistrationView(APIView):
    """
    POST /api/admin/course-registrations/{id}/reject/
    Rejects a pending registration.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def post(self, request, registration_id):
        reason = request.data.get('reason', None)
        
        try:
            result = reject_registration(registration_id, request.user, reason)
            return Response(result)
            
        except DjangoValidationError as e:
            raise ValidationError({'error': str(e), 'code': 'REGISTRATION_NOT_FOUND'})


class RegistrationHistoryView(APIView):
    """
    GET /api/admin/course-registrations/history/
    Views registration history with filtering.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsAdminUser]
    
    def get(self, request):
        student_id = request.query_params.get('student_id', None)
        action_filter = request.query_params.get('status', None)
        
        # Map status to action
        if action_filter:
            action_map = {
                'approved': 'UPDATE',
                'rejected': 'DELETE',
                'created': 'CREATE'
            }
            action_filter = action_map.get(action_filter.lower(), action_filter)
        
        history = get_registration_history(student_id, action_filter)
        
        history_data = [
            {
                'id': log.id,
                'student': {
                    'id': log.student.id,
                    'name': log.student.full_name,
                    'matric_number': log.student.matric_number
                },
                'course': {
                    'id': log.course.id,
                    'code': log.course.code,
                    'title': log.course.title
                },
                'action': log.action.lower(),
                'timestamp': log.timestamp.isoformat(),
                'reason': log.change_reason
            }
            for log in history[:100]  # Limit to 100 records
        ]
        
        return Response({'history': history_data})
