# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError
import uuid

class User(AbstractUser):
    """Enhanced User model with role-based system"""
    USER_ROLES = [
        ('admin', 'System Administrator'),
        ('student', 'Student'),
        ('lecturer', 'Lecturer'),
        ('department_admin', 'Department Administrator'),
        ('staff', 'Staff'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=USER_ROLES, default='student')
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    profile_picture = models.ImageField(upload_to='profile_pictures/', blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Override username to use email
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"

    def get_full_name(self):
        """Return full name"""
        return f"{self.first_name} {self.last_name}".strip()

    def get_role_display_verbose(self):
        """Get verbose role display"""
        return dict(self.USER_ROLES).get(self.role, self.role)

    def is_admin(self):
        """Check if user is admin"""
        return self.role == 'admin' or self.is_superuser

    def is_student(self):
        """Check if user is student"""
        return self.role == 'student'

    def is_lecturer(self):
        """Check if user is lecturer"""
        return self.role == 'lecturer'

    def is_department_admin(self):
        """Check if user is department admin"""
        return self.role == 'department_admin'

    def can_manage_department(self, department):
        """Check if user can manage a specific department"""
        if self.is_admin():
            return True
        if self.is_department_admin():
            return hasattr(self, 'managed_departments') and self.managed_departments.filter(id=department.id).exists()
        return False

    def can_access_student_data(self):
        """Check if user can access student data"""
        return self.role in ['admin', 'lecturer', 'department_admin']

    def can_modify_attendance(self):
        """Check if user can modify attendance records"""
        return self.role in ['admin', 'lecturer', 'department_admin']

class UserProfile(models.Model):
    """Extended user profile for additional information"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(blank=True, max_length=500)
    website = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    twitter = models.CharField(max_length=50, blank=True)
    preferred_language = models.CharField(max_length=10, default='en')
    timezone = models.CharField(max_length=50, default='UTC')
    notification_preferences = models.JSONField(default=dict, blank=True)
    privacy_settings = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} Profile"

class DepartmentAdmin(models.Model):
    """Department Administrator role assignment"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='managed_departments')
    department = models.ForeignKey('academics.Department', on_delete=models.CASCADE, related_name='administrators')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='assigned_dept_admins')
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('user', 'department')
        verbose_name = "Department Administrator"
        verbose_name_plural = "Department Administrators"

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.department.name}"

class AuditLog(models.Model):
    """Audit log for tracking user actions"""
    ACTION_TYPES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('view', 'View'),
        ('export', 'Export'),
        ('import', 'Import'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    additional_data = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['model_name', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user} - {self.action} - {self.timestamp}"

    @classmethod
    def log_action(cls, user, action, model_name=None, object_id=None, object_repr=None, 
                   changes=None, ip_address=None, user_agent=None, additional_data=None):
        """Helper method to create audit log entries"""
        return cls.objects.create(
            user=user,
            action=action,
            model_name=model_name or '',
            object_id=str(object_id) if object_id else '',
            object_repr=object_repr or '',
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent or '',
            additional_data=additional_data or {}
        )