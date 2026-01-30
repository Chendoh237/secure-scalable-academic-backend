"""
Student Data Integration Service for Email Management System

This service provides comprehensive integration with the existing student management
system, handling missing or invalid email addresses gracefully and ensuring
real-time data access and updates.

**Validates: Requirements 6.1, 6.2, 6.3, 6.5**
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from django.db import models, transaction
from django.core.cache import cache
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q, Count, Prefetch
from collections import defaultdict

from .models import Student, StudentLevelSelection
from institutions.models import Department, Faculty, Institution
from courses.models import Course, Level
from .recipient_service import RecipientService, RecipientServiceError

logger = logging.getLogger(__name__)


class StudentDataIntegrationError(Exception):
    """Base exception for student data integration errors"""
    pass


class EmailValidationResult:
    """Container for email validation results"""
    
    def __init__(self):
        self.valid_students: List[Student] = []
        self.invalid_email_students: List[Student] = []
        self.missing_email_students: List[Student] = []
        self.duplicate_emails: Dict[str, List[Student]] = defaultdict(list)
        self.total_processed: int = 0
        self.validation_errors: List[str] = []
    
    @property
    def valid_count(self) -> int:
        return len(self.valid_students)
    
    @property
    def invalid_count(self) -> int:
        return len(self.invalid_email_students)
    
    @property
    def missing_count(self) -> int:
        return len(self.missing_email_students)
    
    @property
    def duplicate_count(self) -> int:
        return sum(len(students) - 1 for students in self.duplicate_emails.values() if len(students) > 1)
    
    @property
    def success_rate(self) -> float:
        if self.total_processed == 0:
            return 0.0
        return (self.valid_count / self.total_processed) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses"""
        return {
            'total_processed': self.total_processed,
            'valid_count': self.valid_count,
            'invalid_count': self.invalid_count,
            'missing_count': self.missing_count,
            'duplicate_count': self.duplicate_count,
            'success_rate': round(self.success_rate, 2),
            'validation_errors': self.validation_errors,
            'duplicate_emails': {
                email: [{'id': s.id, 'name': s.full_name, 'matric': s.matric_number} 
                       for s in students]
                for email, students in self.duplicate_emails.items()
                if len(students) > 1
            }
        }


class StudentDataIntegrationService:
    """
    Comprehensive service for integrating email system with existing student management system.
    
    Features:
    - Real-time data access with optimized queries
    - Graceful handling of missing/invalid email addresses
    - Data consistency validation and reporting
    - Cache management for performance
    - Integration with all existing models (Student, Department, Course, Level)
    """
    
    def __init__(self):
        """Initialize the integration service"""
        self.recipient_service = RecipientService()
        self.cache_timeout = 300  # 5 minutes
    
    def get_real_time_student_data(self, student_ids: Optional[List[int]] = None,
                                 force_refresh: bool = False) -> List[Student]:
        """
        Get real-time student data with optimized queries and caching.
        
        Args:
            student_ids: Optional list of specific student IDs
            force_refresh: Force refresh from database, bypassing cache
            
        Returns:
            List of Student objects with related data
        """
        try:
            cache_key = f"student_data_{hash(str(sorted(student_ids)) if student_ids else 'all')}"
            
            if not force_refresh:
                cached_data = cache.get(cache_key)
                if cached_data:
                    logger.debug(f"Retrieved {len(cached_data)} students from cache")
                    return cached_data
            
            # Optimized query with all related data
            queryset = Student.objects.select_related(
                'user',
                'institution',
                'faculty', 
                'department',
                'program'
            ).prefetch_related(
                Prefetch(
                    'studentlevelselection_set',
                    queryset=StudentLevelSelection.objects.select_related('level')
                ),
                'photos'
            )
            
            if student_ids:
                queryset = queryset.filter(id__in=student_ids)
            
            # Only get active students by default
            queryset = queryset.filter(is_active=True)
            
            students = list(queryset.order_by('full_name'))
            
            # Cache the results
            cache.set(cache_key, students, self.cache_timeout)
            
            logger.info(f"Retrieved {len(students)} students from database with real-time data")
            return students
            
        except Exception as e:
            logger.error(f"Failed to get real-time student data: {str(e)}")
            raise StudentDataIntegrationError(f"Failed to retrieve student data: {str(e)}")
    
    def validate_student_email_addresses(self, students: Optional[List[Student]] = None) -> EmailValidationResult:
        """
        Validate email addresses for all or specified students.
        
        Args:
            students: Optional list of students to validate (defaults to all active students)
            
        Returns:
            EmailValidationResult with comprehensive validation information
        """
        try:
            if students is None:
                students = self.get_real_time_student_data()
            
            result = EmailValidationResult()
            result.total_processed = len(students)
            
            email_to_students = defaultdict(list)
            
            for student in students:
                # Check if student has a user account
                if not hasattr(student, 'user') or not student.user:
                    result.missing_email_students.append(student)
                    result.validation_errors.append(f"Student {student.matric_number} has no user account")
                    continue
                
                # Check if email exists
                email = getattr(student.user, 'email', None)
                if not email or not email.strip():
                    result.missing_email_students.append(student)
                    result.validation_errors.append(f"Student {student.matric_number} has no email address")
                    continue
                
                email = email.strip().lower()
                
                # Validate email format
                try:
                    validate_email(email)
                    result.valid_students.append(student)
                    email_to_students[email].append(student)
                except ValidationError:
                    result.invalid_email_students.append(student)
                    result.validation_errors.append(f"Student {student.matric_number} has invalid email: {email}")
            
            # Check for duplicate emails
            result.duplicate_emails = {
                email: students_list for email, students_list in email_to_students.items()
                if len(students_list) > 1
            }
            
            logger.info(f"Email validation completed: {result.valid_count} valid, "
                       f"{result.invalid_count} invalid, {result.missing_count} missing")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to validate student email addresses: {str(e)}")
            raise StudentDataIntegrationError(f"Email validation failed: {str(e)}")
    
    def get_students_with_missing_data(self) -> Dict[str, List[Student]]:
        """
        Identify students with missing or incomplete data that affects email delivery.
        
        Returns:
            Dictionary categorizing students by missing data type
        """
        try:
            students = self.get_real_time_student_data()
            
            missing_data = {
                'no_user_account': [],
                'no_email': [],
                'invalid_email': [],
                'no_department': [],
                'no_level_selection': [],
                'inactive_students': []
            }
            
            # Also check inactive students
            inactive_students = Student.objects.filter(is_active=False).select_related('user', 'department')
            missing_data['inactive_students'] = list(inactive_students)
            
            for student in students:
                # Check user account
                if not hasattr(student, 'user') or not student.user:
                    missing_data['no_user_account'].append(student)
                    continue
                
                # Check email
                email = getattr(student.user, 'email', None)
                if not email or not email.strip():
                    missing_data['no_email'].append(student)
                else:
                    try:
                        validate_email(email.strip())
                    except ValidationError:
                        missing_data['invalid_email'].append(student)
                
                # Check department
                if not student.department:
                    missing_data['no_department'].append(student)
                
                # Check level selection
                if not hasattr(student, 'studentlevelselection_set') or not student.studentlevelselection_set.exists():
                    missing_data['no_level_selection'].append(student)
            
            # Log summary
            total_issues = sum(len(students_list) for students_list in missing_data.values())
            logger.info(f"Found {total_issues} students with missing data across {len(missing_data)} categories")
            
            return missing_data
            
        except Exception as e:
            logger.error(f"Failed to identify students with missing data: {str(e)}")
            raise StudentDataIntegrationError(f"Failed to identify missing data: {str(e)}")
    
    def get_integration_health_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive health report for student data integration.
        
        Returns:
            Dictionary with integration health metrics
        """
        try:
            report = {
                'timestamp': timezone.now().isoformat(),
                'overall_health': 'unknown',
                'metrics': {},
                'issues': [],
                'recommendations': []
            }
            
            # Get basic counts
            total_students = Student.objects.count()
            active_students = Student.objects.filter(is_active=True).count()
            
            # Email validation
            email_validation = self.validate_student_email_addresses()
            
            # Missing data analysis
            missing_data = self.get_students_with_missing_data()
            
            # Department integration
            departments_with_students = Department.objects.annotate(
                student_count=Count('student', filter=Q(student__is_active=True))
            ).filter(student_count__gt=0).count()
            
            total_departments = Department.objects.count()
            
            # Level integration
            levels_with_students = Level.objects.annotate(
                student_count=Count('studentlevelselection', 
                                  filter=Q(studentlevelselection__student__is_active=True))
            ).filter(student_count__gt=0).count()
            
            total_levels = Level.objects.count()
            
            # Compile metrics
            report['metrics'] = {
                'total_students': total_students,
                'active_students': active_students,
                'email_validation': email_validation.to_dict(),
                'departments': {
                    'total': total_departments,
                    'with_students': departments_with_students,
                    'utilization_rate': round((departments_with_students / total_departments) * 100, 2) if total_departments > 0 else 0
                },
                'levels': {
                    'total': total_levels,
                    'with_students': levels_with_students,
                    'utilization_rate': round((levels_with_students / total_levels) * 100, 2) if total_levels > 0 else 0
                },
                'missing_data_summary': {
                    category: len(students) for category, students in missing_data.items()
                }
            }
            
            # Determine overall health
            email_success_rate = email_validation.success_rate
            missing_data_rate = (sum(len(students) for students in missing_data.values()) / active_students) * 100 if active_students > 0 else 100
            
            if email_success_rate >= 95 and missing_data_rate <= 5:
                report['overall_health'] = 'excellent'
            elif email_success_rate >= 90 and missing_data_rate <= 10:
                report['overall_health'] = 'good'
            elif email_success_rate >= 80 and missing_data_rate <= 20:
                report['overall_health'] = 'fair'
            else:
                report['overall_health'] = 'poor'
            
            # Generate issues and recommendations
            if email_validation.missing_count > 0:
                report['issues'].append(f"{email_validation.missing_count} students have missing email addresses")
                report['recommendations'].append("Update student records to include email addresses")
            
            if email_validation.invalid_count > 0:
                report['issues'].append(f"{email_validation.invalid_count} students have invalid email addresses")
                report['recommendations'].append("Validate and correct invalid email addresses")
            
            if email_validation.duplicate_count > 0:
                report['issues'].append(f"{email_validation.duplicate_count} students have duplicate email addresses")
                report['recommendations'].append("Resolve duplicate email addresses to ensure unique delivery")
            
            if missing_data['no_level_selection']:
                count = len(missing_data['no_level_selection'])
                report['issues'].append(f"{count} students have no level selection")
                report['recommendations'].append("Ensure all students have selected their academic level")
            
            if departments_with_students < total_departments:
                unused = total_departments - departments_with_students
                report['issues'].append(f"{unused} departments have no active students")
                report['recommendations'].append("Review department structure and student assignments")
            
            logger.info(f"Integration health report generated: {report['overall_health']} health with {len(report['issues'])} issues")
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate integration health report: {str(e)}")
            raise StudentDataIntegrationError(f"Health report generation failed: {str(e)}")
    
    def refresh_student_data_cache(self, student_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Refresh cached student data to ensure real-time accuracy.
        
        Args:
            student_ids: Optional list of specific student IDs to refresh
            
        Returns:
            Dictionary with refresh results
        """
        try:
            # Clear relevant cache entries
            if student_ids:
                cache_keys = [f"student_data_{hash(str(sorted(student_ids)))}"]
            else:
                # Clear all student data cache entries
                cache_keys = [
                    "student_data_all",
                    f"student_data_{hash(str([]))}"
                ]
            
            cleared_count = 0
            for key in cache_keys:
                if cache.delete(key):
                    cleared_count += 1
            
            # Also clear recipient service cache
            cache.delete_many([
                key for key in cache._cache.keys() 
                if key.startswith('recipients_')
            ])
            
            # Refresh data
            refreshed_students = self.get_real_time_student_data(student_ids, force_refresh=True)
            
            result = {
                'success': True,
                'cache_entries_cleared': cleared_count,
                'students_refreshed': len(refreshed_students),
                'refresh_timestamp': timezone.now().isoformat()
            }
            
            logger.info(f"Student data cache refreshed: {len(refreshed_students)} students, {cleared_count} cache entries cleared")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to refresh student data cache: {str(e)}")
            raise StudentDataIntegrationError(f"Cache refresh failed: {str(e)}")
    
    def get_student_email_delivery_readiness(self, recipient_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess readiness for email delivery based on recipient configuration.
        
        Args:
            recipient_config: Recipient selection configuration
            
        Returns:
            Dictionary with delivery readiness assessment
        """
        try:
            # Build recipient list using existing service
            email_list, metadata = self.recipient_service.build_recipient_list(recipient_config)
            
            # Get students for the selected recipients
            if recipient_config.get('type') == 'all':
                students = self.get_real_time_student_data()
            elif recipient_config.get('type') == 'department':
                department_ids = recipient_config.get('departmentIds', [])
                students = self.recipient_service.get_students_by_department(department_ids)
            elif recipient_config.get('type') == 'level':
                levels = recipient_config.get('levels', [])
                department_id = recipient_config.get('departmentId')
                students = self.recipient_service.get_students_by_level(levels, department_id)
            elif recipient_config.get('type') == 'specific':
                student_ids = recipient_config.get('studentIds', [])
                students = self.recipient_service.get_students_by_ids(student_ids)
            else:
                students = []
            
            # Validate email addresses for selected students
            email_validation = self.validate_student_email_addresses(students) if students else EmailValidationResult()
            
            # Assess readiness
            readiness_score = 0
            readiness_factors = []
            
            if email_list:
                readiness_score += 40
                readiness_factors.append(f"✓ {len(email_list)} valid email addresses found")
            else:
                readiness_factors.append("✗ No valid email addresses found")
            
            if email_validation.success_rate >= 95:
                readiness_score += 30
                readiness_factors.append(f"✓ High email validity rate ({email_validation.success_rate:.1f}%)")
            elif email_validation.success_rate >= 80:
                readiness_score += 20
                readiness_factors.append(f"⚠ Moderate email validity rate ({email_validation.success_rate:.1f}%)")
            else:
                readiness_factors.append(f"✗ Low email validity rate ({email_validation.success_rate:.1f}%)")
            
            if email_validation.duplicate_count == 0:
                readiness_score += 15
                readiness_factors.append("✓ No duplicate email addresses")
            else:
                readiness_factors.append(f"⚠ {email_validation.duplicate_count} duplicate email addresses")
            
            if email_validation.missing_count == 0:
                readiness_score += 15
                readiness_factors.append("✓ All students have email addresses")
            else:
                readiness_factors.append(f"⚠ {email_validation.missing_count} students missing email addresses")
            
            # Determine readiness level
            if readiness_score >= 90:
                readiness_level = 'excellent'
            elif readiness_score >= 75:
                readiness_level = 'good'
            elif readiness_score >= 60:
                readiness_level = 'fair'
            else:
                readiness_level = 'poor'
            
            result = {
                'readiness_level': readiness_level,
                'readiness_score': readiness_score,
                'readiness_factors': readiness_factors,
                'email_count': len(email_list),
                'email_validation': email_validation.to_dict(),
                'metadata': metadata,
                'recommendations': []
            }
            
            # Add recommendations
            if email_validation.invalid_count > 0:
                result['recommendations'].append(f"Fix {email_validation.invalid_count} invalid email addresses")
            
            if email_validation.missing_count > 0:
                result['recommendations'].append(f"Add email addresses for {email_validation.missing_count} students")
            
            if email_validation.duplicate_count > 0:
                result['recommendations'].append(f"Resolve {email_validation.duplicate_count} duplicate email addresses")
            
            if not result['recommendations']:
                result['recommendations'].append("Email delivery is ready to proceed")
            
            logger.info(f"Email delivery readiness assessed: {readiness_level} ({readiness_score}/100) for {len(email_list)} recipients")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to assess email delivery readiness: {str(e)}")
            raise StudentDataIntegrationError(f"Delivery readiness assessment failed: {str(e)}")
    
    def sync_with_external_systems(self) -> Dict[str, Any]:
        """
        Placeholder for syncing with external student information systems.
        This can be extended to integrate with university SIS, LDAP, etc.
        
        Returns:
            Dictionary with sync results
        """
        try:
            # This is a placeholder for future external system integration
            # Could include:
            # - LDAP synchronization
            # - Student Information System (SIS) integration
            # - External email directory sync
            # - Academic calendar integration
            
            result = {
                'success': True,
                'sync_timestamp': timezone.now().isoformat(),
                'systems_synced': [],
                'records_updated': 0,
                'errors': []
            }
            
            logger.info("External system sync completed (placeholder implementation)")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to sync with external systems: {str(e)}")
            raise StudentDataIntegrationError(f"External system sync failed: {str(e)}")


# Global integration service instance
student_data_integration_service = StudentDataIntegrationService()