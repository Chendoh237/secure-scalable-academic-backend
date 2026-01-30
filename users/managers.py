# backend/users/managers.py
from django.contrib.auth.base_user import BaseUserManager
from django.db.models import Manager

class UserManager(BaseUserManager):
    """Custom user manager"""
    
    def create_user(self, username, email=None, password=None, **extra_fields):
        """Create and save a regular user"""
        if not username:
            raise ValueError('The given username must be set')
        
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """Create and save a superuser"""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'super_admin')
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(username, email, password, **extra_fields)

class AdminActivityManager(Manager):
    """Custom manager for admin activities"""
    
    def by_admin(self, admin):
        """Get activities by specific admin"""
        return self.filter(admin=admin)
    
    def recent(self, days=7):
        """Get recent activities within specified days"""
        from datetime import timedelta
        from django.utils import timezone
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(timestamp__gte=cutoff)
    
    def by_action(self, action):
        """Get activities by action type"""
        return self.filter(action=action)

class LoginLogManager(Manager):
    """Custom manager for login logs"""
    
    def successful(self):
        """Get successful logins"""
        return self.filter(success=True)
    
    def failed(self):
        """Get failed logins"""
        return self.filter(success=False)
    
    def today(self):
        """Get today's logins"""
        from datetime import date
        return self.filter(timestamp__date=date.today())
    
    def by_ip(self, ip_address):
        """Get logins by IP address"""
        return self.filter(ip_address=ip_address)