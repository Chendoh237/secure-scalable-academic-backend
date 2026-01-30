# backend/users/signals.py
from django.db.models.signals import post_save, user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import LoginLog, AdminActivity, SystemStats
from datetime import date

User = get_user_model()

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Log successful login attempts"""
    LoginLog.objects.create(
        user=user,
        username=user.username,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', ''),
        success=True
    )

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Handle user creation"""
    if created:
        # Log admin activity if user is created by admin
        if hasattr(instance, '_created_by_admin'):
            AdminActivity.objects.create(
                admin=instance._created_by_admin,
                action='CREATE_USER',
                description=f'Created user: {instance.username}',
                ip_address=getattr(instance, '_ip_address', '127.0.0.1'),
                user_agent=getattr(instance, '_user_agent', '')
            )

def get_client_ip(request):
    """Get client IP address"""
    if not request:
        return '127.0.0.1'
    
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Log admin logout"""
    if user and user.is_admin_user():
        AdminActivity.objects.create(
            admin=user,
            action='LOGOUT',
            description=f'Admin {user.username} logged out',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )