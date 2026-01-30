"""
JWT Authentication System for Production-Ready Attendance Management
Secure token-based authentication with role-based access control
"""

import jwt
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List
from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.core.cache import cache
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
import logging

from users.models import User, AuditLog
from students.models import Student

logger = logging.getLogger(__name__)

class JWTAuthenticationService:
    """
    JWT Authentication service with secure token management
    """
    
    def __init__(self):
        self.secret_key = getattr(settings, 'JWT_SECRET_KEY', settings.SECRET_KEY)
        self.algorithm = 'HS256'
        self.access_token_lifetime = timedelta(hours=1)
        self.refresh_token_lifetime = timedelta(days=7)
        self.blacklist_cache_timeout = 60 * 60 * 24 * 7  # 7 days
    
    def generate_tokens(self, user: User) -> Dict[str, str]:
        """Generate access and refresh tokens for user"""
        try:
            now = timezone.now()
            
            # Generate unique token IDs
            access_jti = str(uuid.uuid4())
            refresh_jti = str(uuid.uuid4())
            
            # Access token payload
            access_payload = {
                'user_id': str(user.id),
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'is_approved': user.is_approved,
                'jti': access_jti,
                'token_type': 'access',
                'iat': now,
                'exp': now + self.access_token_lifetime
            }
            
            # Refresh token payload
            refresh_payload = {
                'user_id': str(user.id),
                'jti': refresh_jti,
                'token_type': 'refresh',
                'iat': now,
                'exp': now + self.refresh_token_lifetime
            }
            
            # Generate tokens
            access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
            refresh_token = jwt.encode(refresh_payload, self.secret_key, algorithm=self.algorithm)
            
            # Store token metadata in cache for blacklisting
            self._store_token_metadata(access_jti, user.id, 'access', now + self.access_token_lifetime)
            self._store_token_metadata(refresh_jti, user.id, 'refresh', now + self.refresh_token_lifetime)
            
            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'access_expires_at': (now + self.access_token_lifetime).isoformat(),
                'refresh_expires_at': (now + self.refresh_token_lifetime).isoformat(),
                'token_type': 'Bearer'
            }
            
        except Exception as e:
            logger.error(f"Error generating tokens for user {user.id}: {e}")
            raise
    
    def verify_token(self, token: str, token_type: str = 'access') -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            # Decode token
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Verify token type
            if payload.get('token_type') != token_type:
                logger.warning(f"Invalid token type. Expected: {token_type}, Got: {payload.get('token_type')}")
                return None
            
            # Check if token is blacklisted
            jti = payload.get('jti')
            if jti and self._is_token_blacklisted(jti):
                logger.warning(f"Token {jti} is blacklisted")
                return None
            
            # Verify user still exists and is active
            user_id = payload.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(id=user_id, is_active=True)
                    payload['user'] = user
                except User.DoesNotExist:
                    logger.warning(f"User {user_id} not found or inactive")
                    return None
            
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.debug("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return None
    
    def refresh_access_token(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """Generate new access token using refresh token"""
        try:
            # Verify refresh token
            payload = self.verify_token(refresh_token, 'refresh')
            if not payload:
                return None
            
            user = payload['user']
            
            # Generate new access token
            now = timezone.now()
            access_jti = str(uuid.uuid4())
            
            access_payload = {
                'user_id': str(user.id),
                'email': user.email,
                'role': user.role,
                'is_active': user.is_active,
                'is_approved': user.is_approved,
                'jti': access_jti,
                'token_type': 'access',
                'iat': now,
                'exp': now + self.access_token_lifetime
            }
            
            access_token = jwt.encode(access_payload, self.secret_key, algorithm=self.algorithm)
            
            # Store new token metadata
            self._store_token_metadata(access_jti, user.id, 'access', now + self.access_token_lifetime)
            
            return {
                'access_token': access_token,
                'access_expires_at': (now + self.access_token_lifetime).isoformat(),
                'token_type': 'Bearer'
            }
            
        except Exception as e:
            logger.error(f"Error refreshing access token: {e}")
            return None
    
    def blacklist_token(self, token: str) -> bool:
        """Add token to blacklist"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            jti = payload.get('jti')
            
            if jti:
                cache_key = f"blacklisted_token:{jti}"
                cache.set(cache_key, True, self.blacklist_cache_timeout)
                logger.info(f"Token {jti} blacklisted")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error blacklisting token: {e}")
            return False
    
    def _store_token_metadata(self, jti: str, user_id: str, token_type: str, expires_at: datetime):
        """Store token metadata in cache"""
        try:
            cache_key = f"token_metadata:{jti}"
            metadata = {
                'user_id': user_id,
                'token_type': token_type,
                'expires_at': expires_at.isoformat(),
                'created_at': timezone.now().isoformat()
            }
            
            # Cache until token expires
            timeout = int((expires_at - timezone.now()).total_seconds())
            if timeout > 0:
                cache.set(cache_key, metadata, timeout)
                
        except Exception as e:
            logger.error(f"Error storing token metadata: {e}")
    
    def _is_token_blacklisted(self, jti: str) -> bool:
        """Check if token is blacklisted"""
        try:
            cache_key = f"blacklisted_token:{jti}"
            return cache.get(cache_key, False)
        except Exception as e:
            logger.error(f"Error checking token blacklist: {e}")
            return False
    
    def get_user_from_token(self, token: str) -> Optional[User]:
        """Extract user from valid token"""
        payload = self.verify_token(token)
        return payload.get('user') if payload else None


# Global JWT service instance
jwt_auth_service = JWTAuthenticationService()


# API Endpoints
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """
    User login endpoint
    
    Expected payload:
    {
        "email": "user@example.com",
        "password": "password123"
    }
    """
    try:
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({
                'success': False,
                'message': 'Email and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Authenticate user
        user = authenticate(request, username=email, password=password)
        
        if not user:
            # Log failed login attempt
            AuditLog.log_action(
                user=None,
                action='login',
                additional_data={
                    'email': email,
                    'success': False,
                    'reason': 'Invalid credentials'
                },
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            
            return Response({
                'success': False,
                'message': 'Invalid email or password'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not user.is_active:
            return Response({
                'success': False,
                'message': 'Account is deactivated'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        if not user.is_approved:
            return Response({
                'success': False,
                'message': 'Account is pending approval'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Generate tokens
        tokens = jwt_auth_service.generate_tokens(user)
        
        # Get user profile data
        user_data = {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_active': user.is_active,
            'is_approved': user.is_approved
        }
        
        # Add student-specific data if user is a student
        if user.role == 'student' and hasattr(user, 'student_profile'):
            student = user.student_profile
            user_data.update({
                'matric_number': student.matric_number,
                'department': student.department.name if student.department else None,
                'current_level': getattr(student, 'current_level', None)
            })
        
        # Log successful login
        AuditLog.log_action(
            user=user,
            action='login',
            additional_data={'success': True},
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
        
        # Update last login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return Response({
            'success': True,
            'message': 'Login successful',
            'data': {
                'user': user_data,
                'tokens': tokens
            }
        })
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return Response({
            'success': False,
            'message': 'Login failed due to server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """
    Refresh access token using refresh token
    
    Expected payload:
    {
        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    }
    """
    try:
        refresh_token = request.data.get('refresh_token')
        
        if not refresh_token:
            return Response({
                'success': False,
                'message': 'Refresh token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate new access token
        new_tokens = jwt_auth_service.refresh_access_token(refresh_token)
        
        if not new_tokens:
            return Response({
                'success': False,
                'message': 'Invalid or expired refresh token'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        return Response({
            'success': True,
            'message': 'Token refreshed successfully',
            'data': new_tokens
        })
        
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        return Response({
            'success': False,
            'message': 'Token refresh failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    User logout endpoint - blacklists the current token
    """
    try:
        # Get token from Authorization header
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            
            # Blacklist the token
            jwt_auth_service.blacklist_token(token)
            
            # Log logout
            AuditLog.log_action(
                user=request.user,
                action='logout',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        
        return Response({
            'success': True,
            'message': 'Logout successful'
        })
        
    except Exception as e:
        logger.error(f"Logout error: {e}")
        return Response({
            'success': False,
            'message': 'Logout failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verify_token_endpoint(request):
    """
    Verify current token and return user info
    """
    try:
        user = request.user
        
        user_data = {
            'id': str(user.id),
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'is_active': user.is_active,
            'is_approved': user.is_approved,
            'permissions': {
                'can_access_admin': user.is_admin(),
                'can_access_student_data': user.can_access_student_data(),
                'can_modify_attendance': user.can_modify_attendance()
            }
        }
        
        # Add student-specific data if user is a student
        if user.role == 'student' and hasattr(user, 'student_profile'):
            student = user.student_profile
            user_data.update({
                'matric_number': student.matric_number,
                'department': student.department.name if student.department else None,
                'current_level': getattr(student, 'current_level', None),
                'face_consent_given': getattr(student, 'face_consent_given', False)
            })
        
        return Response({
            'success': True,
            'message': 'Token is valid',
            'data': {
                'user': user_data,
                'token_valid': True
            }
        })
        
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        return Response({
            'success': False,
            'message': 'Token verification failed'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_student(request):
    """
    Student registration endpoint
    
    Expected payload:
    {
        "email": "student@example.com",
        "password": "password123",
        "first_name": "John",
        "last_name": "Doe",
        "matric_number": "CS/2024/001",
        "department_id": "uuid-string"
    }
    """
    try:
        data = request.data
        
        # Validate required fields
        required_fields = ['email', 'password', 'first_name', 'last_name', 'matric_number', 'department_id']
        for field in required_fields:
            if not data.get(field):
                return Response({
                    'success': False,
                    'message': f'{field} is required'
                }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if email already exists
        if User.objects.filter(email=data['email']).exists():
            return Response({
                'success': False,
                'message': 'Email already registered'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if matric number already exists
        if Student.objects.filter(matric_number=data['matric_number']).exists():
            return Response({
                'success': False,
                'message': 'Matricule number already registered'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=data['email'],
                email=data['email'],
                password=data['password'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                role='student',
                is_active=True,
                is_approved=False  # Requires admin approval
            )
            
            # Create student profile
            from academics.models import Department
            department = Department.objects.get(id=data['department_id'])
            
            student = Student.objects.create(
                user=user,
                matric_number=data['matric_number'],
                full_name=f"{data['first_name']} {data['last_name']}",
                department=department,
                is_active=True,
                is_approved=False  # Requires admin approval
            )
            
            # Log registration
            AuditLog.log_action(
                user=user,
                action='create',
                model_name='Student',
                object_id=str(student.id),
                object_repr=str(student),
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        
        return Response({
            'success': True,
            'message': 'Registration successful. Your account is pending approval.',
            'data': {
                'user_id': str(user.id),
                'student_id': str(student.id),
                'matric_number': student.matric_number,
                'status': 'pending_approval'
            }
        })
        
    except Department.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Invalid department'
        }, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Student registration error: {e}")
        return Response({
            'success': False,
            'message': 'Registration failed due to server error'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# JWT Authentication Middleware
class JWTAuthenticationMiddleware:
    """
    Custom JWT authentication middleware
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Process request
        self.process_request(request)
        
        # Get response
        response = self.get_response(request)
        
        return response
    
    def process_request(self, request):
        """Process incoming request for JWT authentication"""
        try:
            # Skip authentication for certain paths
            skip_paths = ['/api/auth/login/', '/api/auth/register/', '/api/auth/refresh/']
            if any(request.path.startswith(path) for path in skip_paths):
                return
            
            # Get token from Authorization header
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            
            if not auth_header.startswith('Bearer '):
                request.user = AnonymousUser()
                return
            
            token = auth_header.split(' ')[1]
            
            # Verify token
            payload = jwt_auth_service.verify_token(token)
            
            if payload and 'user' in payload:
                request.user = payload['user']
            else:
                request.user = AnonymousUser()
                
        except Exception as e:
            logger.error(f"JWT authentication middleware error: {e}")
            request.user = AnonymousUser()