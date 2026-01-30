"""
URL configuration for backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .health_views import health_check

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Health check for deployment
    path('api/health/', health_check, name='health_check'),
    
    # Authentication
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Student APIs (includes admin endpoints)
    path('api/', include('students.urls')),
    
    # Course APIs
    path('api/courses/', include('courses.urls')),
    
    # Institution APIs
    path('api/institutions/', include('institutions.urls_new')),
    
    # Academics APIs
    path('api/academics/', include('academics.urls')),
    
    # Attendance APIs
    path("api/attendance/", include("attendance.urls")),
    
    # Notification APIs
    path('api/notifications/', include('notifications.urls')),
    
    # Face recognition APIs
    path("api/face/", include("recognition.urls")),
    
    # Live sessions APIs
    path("api/live-sessions/", include("live_sessions.urls")),
    
    # User management
    path('api/users/', include('users.urls')),
    
    # Audit and Compliance APIs
    path('api/audit/', include('audit.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)