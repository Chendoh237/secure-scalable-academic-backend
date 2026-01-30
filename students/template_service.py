"""
Template Service for the Email Management System

This service handles email template management, rendering, and variable substitution.
"""

import re
from typing import Dict, List, Any, Optional
import logging
from django.template import Template, Context
from django.template.exceptions import TemplateSyntaxError
from .email_models import EmailTemplate
from .models_settings import SystemSettings

logger = logging.getLogger(__name__)


class TemplateServiceError(Exception):
    """Base exception for template service errors"""
    pass


class TemplateRenderError(TemplateServiceError):
    """Raised when template rendering fails"""
    pass


class TemplateService:
    """
    Service for managing email templates and rendering them with dynamic content.
    """
    
    def __init__(self):
        """Initialize the template service"""
        pass
    
    def get_templates(self, category: Optional[str] = None, active_only: bool = True) -> List[EmailTemplate]:
        """
        Retrieve email templates, optionally filtered by category.
        
        Args:
            category: Optional category filter ('attendance', 'course', 'exam', 'general')
            active_only: Whether to return only active templates
            
        Returns:
            List of EmailTemplate objects
        """
        try:
            queryset = EmailTemplate.objects.all()
            
            if active_only:
                queryset = queryset.filter(is_active=True)
            
            if category:
                queryset = queryset.filter(category=category)
            
            return list(queryset.order_by('category', 'name'))
            
        except Exception as e:
            logger.error(f"Failed to retrieve templates: {str(e)}")
            raise TemplateServiceError(f"Failed to retrieve templates: {str(e)}")
    
    def get_template(self, template_id: int) -> Optional[EmailTemplate]:
        """
        Retrieve a specific email template by ID.
        
        Args:
            template_id: Template ID
            
        Returns:
            EmailTemplate object or None if not found
        """
        try:
            return EmailTemplate.objects.get(id=template_id, is_active=True)
        except EmailTemplate.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve template {template_id}: {str(e)}")
            raise TemplateServiceError(f"Failed to retrieve template: {str(e)}")
    
    def get_template_by_name(self, name: str) -> Optional[EmailTemplate]:
        """
        Retrieve a specific email template by name.
        
        Args:
            name: Template name
            
        Returns:
            EmailTemplate object or None if not found
        """
        try:
            return EmailTemplate.objects.get(name=name, is_active=True)
        except EmailTemplate.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Failed to retrieve template '{name}': {str(e)}")
            raise TemplateServiceError(f"Failed to retrieve template: {str(e)}")
    
    def extract_variables(self, template_text: str) -> List[str]:
        """
        Extract variable names from template text.
        Looks for variables in the format {variable_name}.
        
        Args:
            template_text: Template text to analyze
            
        Returns:
            List of unique variable names
        """
        try:
            # Find all variables in {variable_name} format
            variables = re.findall(r'\{([^}]+)\}', template_text)
            
            # Remove duplicates and return sorted list
            return sorted(list(set(variables)))
            
        except Exception as e:
            logger.error(f"Failed to extract variables: {str(e)}")
            return []
    
    def validate_template(self, subject_template: str, body_template: str) -> Dict[str, Any]:
        """
        Validate template syntax and extract variables.
        
        Args:
            subject_template: Subject template text
            body_template: Body template text
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Extract variables from both templates
            subject_vars = self.extract_variables(subject_template)
            body_vars = self.extract_variables(body_template)
            all_vars = sorted(list(set(subject_vars + body_vars)))
            
            # Test rendering with dummy data
            test_context = {var: f"[{var}]" for var in all_vars}
            
            try:
                rendered_subject = self.render_template_text(subject_template, test_context)
                rendered_body = self.render_template_text(body_template, test_context)
                
                return {
                    'valid': True,
                    'variables': all_vars,
                    'subject_variables': subject_vars,
                    'body_variables': body_vars,
                    'test_subject': rendered_subject,
                    'test_body': rendered_body
                }
                
            except Exception as render_error:
                return {
                    'valid': False,
                    'error': f"Template rendering failed: {str(render_error)}",
                    'variables': all_vars
                }
                
        except Exception as e:
            logger.error(f"Template validation failed: {str(e)}")
            return {
                'valid': False,
                'error': str(e),
                'variables': []
            }
    
    def render_template_text(self, template_text: str, context: Dict[str, Any]) -> str:
        """
        Render template text with provided context variables.
        
        Args:
            template_text: Template text with {variable} placeholders
            context: Dictionary of variable values
            
        Returns:
            Rendered text with variables substituted
        """
        try:
            # Simple string formatting approach
            rendered = template_text
            
            for key, value in context.items():
                placeholder = f"{{{key}}}"
                rendered = rendered.replace(placeholder, str(value))
            
            return rendered
            
        except Exception as e:
            logger.error(f"Template rendering failed: {str(e)}")
            raise TemplateRenderError(f"Failed to render template: {str(e)}")
    
    def render_template(self, template: EmailTemplate, context: Dict[str, Any]) -> Dict[str, str]:
        """
        Render an EmailTemplate with provided context variables.
        
        Args:
            template: EmailTemplate object
            context: Dictionary of variable values
            
        Returns:
            Dictionary with rendered subject and body
        """
        try:
            # Add system-wide variables to context
            enhanced_context = self._enhance_context(context)
            
            # Render subject and body
            rendered_subject = self.render_template_text(template.subject_template, enhanced_context)
            rendered_body = self.render_template_text(template.body_template, enhanced_context)
            
            return {
                'subject': rendered_subject,
                'body': rendered_body
            }
            
        except Exception as e:
            logger.error(f"Failed to render template {template.name}: {str(e)}")
            raise TemplateRenderError(f"Failed to render template: {str(e)}")
    
    def _enhance_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance context with system-wide variables.
        
        Args:
            context: Original context dictionary
            
        Returns:
            Enhanced context with system variables
        """
        enhanced = context.copy()
        
        try:
            # Add system settings
            settings_data = SystemSettings.get_settings()
            institution_settings = settings_data.get('institution', {})
            
            # Add institution information
            enhanced.update({
                'institution_name': institution_settings.get('name', 'Student Management System'),
                'institution_email': institution_settings.get('email', ''),
                'institution_phone': institution_settings.get('phone', ''),
                'institution_address': institution_settings.get('address', ''),
                'institution_website': institution_settings.get('website', ''),
            })
            
            # Add current date/time
            from django.utils import timezone
            now = timezone.now()
            enhanced.update({
                'current_date': now.strftime('%Y-%m-%d'),
                'current_time': now.strftime('%H:%M:%S'),
                'current_datetime': now.strftime('%Y-%m-%d %H:%M:%S'),
                'current_year': now.year,
            })
            
        except Exception as e:
            logger.warning(f"Failed to enhance context with system variables: {str(e)}")
        
        return enhanced
    
    def create_custom_template(self, name: str, category: str, subject_template: str,
                             body_template: str, description: str = "") -> EmailTemplate:
        """
        Create a new custom email template.
        
        Args:
            name: Template name
            category: Template category
            subject_template: Subject template text
            body_template: Body template text
            description: Optional description
            
        Returns:
            Created EmailTemplate object
        """
        try:
            # Validate template
            validation = self.validate_template(subject_template, body_template)
            if not validation['valid']:
                raise TemplateServiceError(f"Invalid template: {validation['error']}")
            
            # Create template
            template = EmailTemplate.objects.create(
                name=name,
                category=category,
                subject_template=subject_template,
                body_template=body_template,
                variables=validation['variables'],
                description=description,
                is_active=True
            )
            
            logger.info(f"Created custom template: {name}")
            return template
            
        except Exception as e:
            logger.error(f"Failed to create custom template: {str(e)}")
            raise TemplateServiceError(f"Failed to create template: {str(e)}")
    
    def update_template(self, template_id: int, **kwargs) -> EmailTemplate:
        """
        Update an existing email template.
        
        Args:
            template_id: Template ID to update
            **kwargs: Fields to update
            
        Returns:
            Updated EmailTemplate object
        """
        try:
            template = EmailTemplate.objects.get(id=template_id)
            
            # If updating template content, validate it
            subject_template = kwargs.get('subject_template', template.subject_template)
            body_template = kwargs.get('body_template', template.body_template)
            
            if 'subject_template' in kwargs or 'body_template' in kwargs:
                validation = self.validate_template(subject_template, body_template)
                if not validation['valid']:
                    raise TemplateServiceError(f"Invalid template: {validation['error']}")
                kwargs['variables'] = validation['variables']
            
            # Update fields
            for field, value in kwargs.items():
                if hasattr(template, field):
                    setattr(template, field, value)
            
            template.save()
            
            logger.info(f"Updated template: {template.name}")
            return template
            
        except EmailTemplate.DoesNotExist:
            raise TemplateServiceError("Template not found")
        except Exception as e:
            logger.error(f"Failed to update template {template_id}: {str(e)}")
            raise TemplateServiceError(f"Failed to update template: {str(e)}")
    
    def delete_template(self, template_id: int) -> bool:
        """
        Delete (deactivate) an email template.
        
        Args:
            template_id: Template ID to delete
            
        Returns:
            True if successful
        """
        try:
            template = EmailTemplate.objects.get(id=template_id)
            template.is_active = False
            template.save()
            
            logger.info(f"Deactivated template: {template.name}")
            return True
            
        except EmailTemplate.DoesNotExist:
            raise TemplateServiceError("Template not found")
        except Exception as e:
            logger.error(f"Failed to delete template {template_id}: {str(e)}")
            raise TemplateServiceError(f"Failed to delete template: {str(e)}")
    
    def get_template_categories(self) -> List[Dict[str, str]]:
        """
        Get available template categories.
        
        Returns:
            List of category dictionaries with code and name
        """
        return [
            {'code': 'attendance', 'name': 'Attendance'},
            {'code': 'course', 'name': 'Course Updates'},
            {'code': 'exam', 'name': 'Exam Notifications'},
            {'code': 'general', 'name': 'General Announcements'},
        ]
    
    def render_template_for_student(self, template: EmailTemplate, student, 
                                  additional_context: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Render template with student-specific context.
        
        Args:
            template: EmailTemplate object
            student: Student object
            additional_context: Additional context variables
            
        Returns:
            Dictionary with rendered subject and body
        """
        try:
            # Build student context
            context = {
                'student_name': student.full_name,
                'student_matric': student.matric_number,
                'student_email': getattr(student.user, 'email', ''),
                'department_name': student.department.name,
                'faculty_name': student.faculty.name,
                'institution_name': student.institution.name,
            }
            
            # Add additional context if provided
            if additional_context:
                context.update(additional_context)
            
            # Render template
            return self.render_template(template, context)
            
        except Exception as e:
            logger.error(f"Failed to render template for student {student.matric_number}: {str(e)}")
            raise TemplateRenderError(f"Failed to render template for student: {str(e)}")


# Global template service instance
template_service = TemplateService()