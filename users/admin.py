

# Register your models here.
# backend/users/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserProfile, DepartmentAdmin, AuditLog

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin with role-based access"""
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_approved', 'created_at')
    list_filter = ('role', 'is_approved', 'is_staff', 'is_superuser', 'created_at')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email', 'phone_number')}),
        (_('Role & Permissions'), {
            'fields': ('role', 'is_approved', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Additional Info'), {
            'fields': ('profile_picture', 'date_of_birth', 'address', 'emergency_contact', 'emergency_phone'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2', 'role'),
        }),
    )
    
    def get_queryset(self, request):
        """Filter queryset based on admin role"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        elif request.user.role == 'department_admin':
            # Department admins can only see users in their departments
            return qs.filter(managed_departments__user=request.user)
        return qs.filter(id=request.user.id)

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """User profile admin"""
    list_display = ('user', 'preferred_language', 'timezone', 'created_at')
    list_filter = ('preferred_language', 'timezone', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Profile Info'), {
            'fields': ('user', 'bio', 'website', 'linkedin', 'twitter'),
        }),
        (_('Preferences'), {
            'fields': ('preferred_language', 'timezone', 'notification_preferences', 'privacy_settings'),
        }),
    )

@admin.register(DepartmentAdmin)
class DepartmentAdminAdmin(admin.ModelAdmin):
    """Department administrator assignment admin"""
    list_display = ('user', 'department', 'assigned_at', 'assigned_by', 'is_active')
    list_filter = ('is_active', 'assigned_at', 'department')
    search_fields = ('user__username', 'user__email', 'department__name')
    ordering = ('-assigned_at',)
    
    def get_queryset(self, request):
        """Filter based on admin role"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        elif request.user.role == 'department_admin':
            return qs.filter(user=request.user)
        return qs.filter(id__in=[])

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Audit log monitoring"""
    list_display = ('user', 'action', 'model_name', 'object_repr', 'ip_address', 'timestamp')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'action', 'model_name', 'object_repr', 'ip_address')
    ordering = ('-timestamp',)
    readonly_fields = ('user', 'action', 'model_name', 'object_id', 'object_repr', 
                      'changes', 'ip_address', 'user_agent', 'timestamp', 'additional_data')
    
    def get_queryset(self, request):
        """Filter audit logs based on admin role"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(user=request.user)
    
    def has_add_permission(self, request):
        """Prevent manual addition of audit logs"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Audit logs are read-only"""
        return False