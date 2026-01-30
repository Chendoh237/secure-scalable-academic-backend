"""
Recipient Service for the Email Management System

This service handles recipient selection, filtering, and email address validation.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
import logging
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Q, Count
from .models import Student
from institutions.models import Department
from courses.models import Level

logger = logging.getLogger(__name__)


class RecipientServiceError(Exception):
    """Base exception for recipient service errors"""
    pass


class RecipientService:
    """
    Service for managing email recipients and filtering students.
    """
    
    def __init__(self):
        """Initialize the recipient service"""
        pass
    
    def get_all_students(self, include_inactive: bool = False) -> List[Student]:
        """
        Get all students with email addresses.
        
        Args:
            include_inactive: Whether to include inactive students
            
        Returns:
            List of Student objects
        """
        try:
            queryset = Student.objects.select_related('user', 'department', 'faculty', 'institution')
            
            if not include_inactive:
                queryset = queryset.filter(is_active=True)
            
            # Filter students with email addresses
            queryset = queryset.filter(
                user__email__isnull=False
            ).exclude(user__email='')
            
            return list(queryset.order_by('full_name'))
            
        except Exception as e:
            logger.error(f"Failed to retrieve all students: {str(e)}")
            raise RecipientServiceError(f"Failed to retrieve students: {str(e)}")
    
    def get_students_by_department(self, department_ids: List[int], 
                                 include_inactive: bool = False) -> List[Student]:
        """
        Get students filtered by department(s).
        
        Args:
            department_ids: List of department IDs
            include_inactive: Whether to include inactive students
            
        Returns:
            List of Student objects
        """
        try:
            if not department_ids:
                return []
            
            queryset = Student.objects.select_related('user', 'department', 'faculty', 'institution')
            
            if not include_inactive:
                queryset = queryset.filter(is_active=True)
            
            # Filter by departments and email addresses
            queryset = queryset.filter(
                department_id__in=department_ids,
                user__email__isnull=False
            ).exclude(user__email='')
            
            return list(queryset.order_by('department__name', 'full_name'))
            
        except Exception as e:
            logger.error(f"Failed to retrieve students by department: {str(e)}")
            raise RecipientServiceError(f"Failed to retrieve students by department: {str(e)}")
    
    def get_students_by_level(self, levels: List[str], department_id: Optional[int] = None,
                            include_inactive: bool = False) -> List[Student]:
        """
        Get students filtered by academic level(s).
        
        Args:
            levels: List of level names/codes
            department_id: Optional department filter
            include_inactive: Whether to include inactive students
            
        Returns:
            List of Student objects
        """
        try:
            if not levels:
                return []
            
            # Get students who have selected these levels
            from .models import StudentLevelSelection
            
            queryset = Student.objects.select_related('user', 'department', 'faculty', 'institution')
            
            if not include_inactive:
                queryset = queryset.filter(is_active=True)
            
            # Filter by level selections
            level_filter = Q()
            for level in levels:
                level_filter |= Q(level_selection__level__name=level) | Q(level_selection__level__code=level)
            
            queryset = queryset.filter(level_filter)
            
            # Optional department filter
            if department_id:
                queryset = queryset.filter(department_id=department_id)
            
            # Filter students with email addresses
            queryset = queryset.filter(
                user__email__isnull=False
            ).exclude(user__email='')
            
            return list(queryset.order_by('level_selection__level__name', 'full_name'))
            
        except Exception as e:
            logger.error(f"Failed to retrieve students by level: {str(e)}")
            raise RecipientServiceError(f"Failed to retrieve students by level: {str(e)}")
    
    def get_students_by_ids(self, student_ids: List[int], 
                          include_inactive: bool = False) -> List[Student]:
        """
        Get specific students by their IDs.
        
        Args:
            student_ids: List of student IDs
            include_inactive: Whether to include inactive students
            
        Returns:
            List of Student objects
        """
        try:
            if not student_ids:
                return []
            
            queryset = Student.objects.select_related('user', 'department', 'faculty', 'institution')
            
            if not include_inactive:
                queryset = queryset.filter(is_active=True)
            
            # Filter by IDs and email addresses
            queryset = queryset.filter(
                id__in=student_ids,
                user__email__isnull=False
            ).exclude(user__email='')
            
            return list(queryset.order_by('full_name'))
            
        except Exception as e:
            logger.error(f"Failed to retrieve students by IDs: {str(e)}")
            raise RecipientServiceError(f"Failed to retrieve students by IDs: {str(e)}")
    
    def search_students(self, query: str, department_id: Optional[int] = None,
                       limit: int = 50) -> List[Student]:
        """
        Search students by name, matric number, or email.
        
        Args:
            query: Search query
            department_id: Optional department filter
            limit: Maximum number of results
            
        Returns:
            List of Student objects
        """
        try:
            if not query or len(query.strip()) < 2:
                return []
            
            query = query.strip()
            queryset = Student.objects.select_related('user', 'department', 'faculty', 'institution')
            
            # Search in multiple fields
            search_filter = (
                Q(full_name__icontains=query) |
                Q(matric_number__icontains=query) |
                Q(user__email__icontains=query)
            )
            
            queryset = queryset.filter(
                search_filter,
                is_active=True,
                user__email__isnull=False
            ).exclude(user__email='')
            
            # Optional department filter
            if department_id:
                queryset = queryset.filter(department_id=department_id)
            
            return list(queryset.order_by('full_name')[:limit])
            
        except Exception as e:
            logger.error(f"Failed to search students: {str(e)}")
            raise RecipientServiceError(f"Failed to search students: {str(e)}")
    
    def validate_email_addresses(self, emails: List[str]) -> Dict[str, Any]:
        """
        Validate a list of email addresses.
        
        Args:
            emails: List of email addresses to validate
            
        Returns:
            Dictionary with validation results
        """
        try:
            valid_emails = []
            invalid_emails = []
            
            for email in emails:
                email = email.strip()
                if not email:
                    continue
                
                try:
                    validate_email(email)
                    valid_emails.append(email)
                except ValidationError:
                    invalid_emails.append(email)
            
            return {
                'valid_emails': valid_emails,
                'invalid_emails': invalid_emails,
                'total_count': len(emails),
                'valid_count': len(valid_emails),
                'invalid_count': len(invalid_emails)
            }
            
        except Exception as e:
            logger.error(f"Failed to validate email addresses: {str(e)}")
            raise RecipientServiceError(f"Failed to validate email addresses: {str(e)}")
    
    def get_recipient_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about available recipients.
        
        Returns:
            Dictionary with recipient statistics
        """
        try:
            # Total students with emails
            total_students = Student.objects.filter(
                is_active=True,
                user__email__isnull=False
            ).exclude(user__email='').count()
            
            # Students by department
            department_stats = Student.objects.filter(
                is_active=True,
                user__email__isnull=False
            ).exclude(user__email='').values(
                'department__id',
                'department__name'
            ).annotate(
                student_count=Count('id')
            ).order_by('department__name')
            
            # Students by level (if level selection is implemented)
            level_stats = []
            try:
                from .models import StudentLevelSelection
                level_stats = Student.objects.filter(
                    is_active=True,
                    user__email__isnull=False,
                    level_selection__isnull=False
                ).exclude(user__email='').values(
                    'level_selection__level__name',
                    'level_selection__level__code'
                ).annotate(
                    student_count=Count('id')
                ).order_by('level_selection__level__name')
            except:
                pass
            
            return {
                'total_students': total_students,
                'departments': list(department_stats),
                'levels': list(level_stats)
            }
            
        except Exception as e:
            logger.error(f"Failed to get recipient statistics: {str(e)}")
            raise RecipientServiceError(f"Failed to get recipient statistics: {str(e)}")
    
    def get_departments_with_student_counts(self) -> List[Dict[str, Any]]:
        """
        Get all departments with their student counts.
        
        Returns:
            List of department dictionaries with student counts
        """
        try:
            departments = Department.objects.annotate(
                student_count=Count(
                    'student',
                    filter=Q(
                        student__is_active=True,
                        student__user__email__isnull=False
                    ) & ~Q(student__user__email='')
                )
            ).order_by('name')
            
            return [
                {
                    'id': dept.id,
                    'name': dept.name,
                    'faculty_name': dept.faculty.name,
                    'student_count': dept.student_count
                }
                for dept in departments
            ]
            
        except Exception as e:
            logger.error(f"Failed to get departments with counts: {str(e)}")
            raise RecipientServiceError(f"Failed to get departments with counts: {str(e)}")
    
    def get_levels_with_student_counts(self, department_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get all levels with their student counts.
        
        Args:
            department_id: Optional department filter
            
        Returns:
            List of level dictionaries with student counts
        """
        try:
            from .models import StudentLevelSelection
            
            queryset = Level.objects.select_related('department')
            
            if department_id:
                queryset = queryset.filter(department_id=department_id)
            
            levels = queryset.annotate(
                student_count=Count(
                    'studentlevelselection',
                    filter=Q(
                        studentlevelselection__student__is_active=True,
                        studentlevelselection__student__user__email__isnull=False
                    ) & ~Q(studentlevelselection__student__user__email='')
                )
            ).order_by('department__name', 'name')
            
            return [
                {
                    'id': level.id,
                    'name': level.name,
                    'code': getattr(level, 'code', ''),
                    'department_name': level.department.name,
                    'student_count': level.student_count
                }
                for level in levels
            ]
            
        except Exception as e:
            logger.error(f"Failed to get levels with counts: {str(e)}")
            # Return empty list if level selection is not implemented
            return []
    
    def build_recipient_list(self, recipient_config: Dict[str, Any]) -> Tuple[List[str], Dict[str, Any]]:
        """
        Build a list of email addresses based on recipient configuration.
        
        Args:
            recipient_config: Configuration dictionary specifying recipients
            
        Returns:
            Tuple of (email_list, metadata)
        """
        try:
            recipient_type = recipient_config.get('type', 'all')
            emails = []
            metadata = {'type': recipient_type, 'sources': []}
            
            if recipient_type == 'all':
                students = self.get_all_students()
                emails = [student.user.email for student in students if student.user and student.user.email]
                metadata['sources'].append(f"All students ({len(emails)} recipients)")
                
            elif recipient_type == 'department':
                department_ids = recipient_config.get('departmentIds', [])
                if not department_ids:
                    department_ids = recipient_config.get('department_ids', [])  # Alternative field name
                
                if department_ids:
                    students = self.get_students_by_department(department_ids)
                    emails = [student.user.email for student in students if student.user and student.user.email]
                    
                    # Get department names for metadata
                    dept_names = [
                        dept.name for dept in Department.objects.filter(id__in=department_ids)
                    ]
                    metadata['sources'].append(f"Departments: {', '.join(dept_names)} ({len(emails)} recipients)")
                else:
                    raise ValueError("Department IDs are required for department-based recipient selection")
                
            elif recipient_type == 'level':
                levels = recipient_config.get('levels', [])
                if not levels:
                    levels = recipient_config.get('level_ids', [])  # Alternative field name
                
                department_id = recipient_config.get('departmentId') or recipient_config.get('department_id')
                
                if levels:
                    students = self.get_students_by_level(levels, department_id)
                    emails = [student.user.email for student in students if student.user and student.user.email]
                    metadata['sources'].append(f"Levels: {', '.join(map(str, levels))} ({len(emails)} recipients)")
                else:
                    raise ValueError("Level IDs are required for level-based recipient selection")
                
            elif recipient_type == 'specific':
                student_ids = recipient_config.get('studentIds', [])
                if not student_ids:
                    student_ids = recipient_config.get('student_ids', [])  # Alternative field name
                
                if student_ids:
                    students = self.get_students_by_ids(student_ids)
                    emails = [student.user.email for student in students if student.user and student.user.email]
                    metadata['sources'].append(f"Specific students ({len(emails)} recipients)")
                else:
                    raise ValueError("Student IDs are required for specific student selection")
                
            elif recipient_type == 'custom':
                custom_emails = recipient_config.get('emails', [])
                if custom_emails:
                    validation = self.validate_email_addresses(custom_emails)
                    emails = validation['valid_emails']
                    metadata['sources'].append(f"Custom emails ({len(emails)} valid, {validation['invalid_count']} invalid)")
                    if validation['invalid_emails']:
                        metadata['invalid_emails'] = validation['invalid_emails']
                else:
                    raise ValueError("Email addresses are required for custom email selection")
            
            else:
                raise ValueError(f"Invalid recipient type: {recipient_type}. Must be one of: all, department, level, specific, custom")
            
            # Remove duplicates while preserving order
            unique_emails = []
            seen = set()
            for email in emails:
                if email and email not in seen:
                    unique_emails.append(email)
                    seen.add(email)
            
            metadata['total_count'] = len(unique_emails)
            metadata['duplicate_count'] = len(emails) - len(unique_emails)
            
            if not unique_emails:
                raise ValueError(f"No valid email addresses found for recipient type '{recipient_type}'")
            
            return unique_emails, metadata
            
        except Exception as e:
            logger.error(f"Error building recipient list: {str(e)}")
            raise RecipientServiceError(f"Failed to build recipient list: {str(e)}")
            
        except Exception as e:
            logger.error(f"Failed to build recipient list: {str(e)}")
            raise RecipientServiceError(f"Failed to build recipient list: {str(e)}")
    
    def get_student_context_data(self, student: Student) -> Dict[str, Any]:
        """
        Get context data for a specific student for template rendering.
        
        Args:
            student: Student object
            
        Returns:
            Dictionary with student context data
        """
        try:
            context = {
                'student_name': student.full_name,
                'student_matric': student.matric_number,
                'student_email': student.user.email,
                'department_name': student.department.name,
                'faculty_name': student.faculty.name,
                'institution_name': student.institution.name,
            }
            
            # Add level information if available
            try:
                if hasattr(student, 'level_selection') and student.level_selection:
                    context.update({
                        'student_level': student.level_selection.level.name,
                        'student_level_code': getattr(student.level_selection.level, 'code', ''),
                    })
            except:
                pass
            
            return context
            
        except Exception as e:
            logger.error(f"Failed to get student context data: {str(e)}")
            return {
                'student_name': getattr(student, 'full_name', 'Unknown'),
                'student_matric': getattr(student, 'matric_number', 'Unknown'),
                'student_email': getattr(student.user, 'email', '') if hasattr(student, 'user') else '',
            }


# Global recipient service instance
recipient_service = RecipientService()