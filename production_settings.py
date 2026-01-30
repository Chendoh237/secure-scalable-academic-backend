"""
Production-Ready Django Settings
Comprehensive configuration for attendance management system
"""

import os
import sys
from pathlib import Path
from datetime import timedelta
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-this-in-production')
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', SECRET_KEY)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')

# Allowed hosts configuration
ALLOWED_HOSTS = []
if DEBUG:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']
else:
    # Production hosts from environment
    hosts = os.environ.get('ALLOWED_HOSTS', '')
    if hosts:
        ALLOWED_HOSTS = [host.strip() for host in hosts.split(',')]

# CORS configuration for frontend
CORS_ALLOWED_ORIGINS = []
if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
else:
    # Production CORS origins from environment
    origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
    if origins:
        CORS_ALLOWED_ORIGINS = [origin.strip() for origin in origins.split(',')]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Only in development

# Application definition
DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'django_extensions',
]

LOCAL_APPS = [
    'users',
    'students',
    'academics',
    'courses',
    'attendance',
    'institutions',
    'live_sessions',
    'notifications',
    'audit',
    'recognition',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'authentication.jwt_auth.JWTAuthenticationMiddleware',  # Custom JWT middleware
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'

# Database configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Production database configuration
if not DEBUG or os.environ.get('DATABASE_URL'):
    # Use PostgreSQL in production or if DATABASE_URL is provided
    DATABASES['default'] = dj_database_url.parse(
        os.environ.get('DATABASE_URL', 'postgresql://user:password@localhost:5432/attendance_db')
    )

# Custom user model
AUTH_USER_MODEL = 'users.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Static files storage for production
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}

# Caching configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'attendance_system',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# Fallback to local memory cache if Redis is not available
if DEBUG and not os.environ.get('REDIS_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'attendance-cache',
        }
    }

# Session configuration
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# CSRF configuration
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

# Security settings for production
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_SSL_REDIRECT = True
    X_FRAME_OPTIONS = 'DENY'

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'attendance': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'authentication': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'administration': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'notifications': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Ensure logs directory exists
os.makedirs(BASE_DIR / 'logs', exist_ok=True)

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# Celery configuration for background tasks
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE

# WhatsApp API configuration
WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL', '')
WHATSAPP_API_TOKEN = os.environ.get('WHATSAPP_API_TOKEN', '')

# Face recognition configuration
FACE_RECOGNITION_MODEL_PATH = BASE_DIR / 'ml_models'
FACE_RECOGNITION_CONFIDENCE_THRESHOLD = float(os.environ.get('FACE_RECOGNITION_CONFIDENCE_THRESHOLD', '0.6'))
FACE_RECOGNITION_DETECTION_INTERVAL = int(os.environ.get('FACE_RECOGNITION_DETECTION_INTERVAL', '30'))

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
FILE_UPLOAD_PERMISSIONS = 0o644

# Attendance system specific settings
ATTENDANCE_PRESENCE_THRESHOLD_PRESENT = float(os.environ.get('ATTENDANCE_PRESENCE_THRESHOLD_PRESENT', '75.0'))
ATTENDANCE_PRESENCE_THRESHOLD_PARTIAL = float(os.environ.get('ATTENDANCE_PRESENCE_THRESHOLD_PARTIAL', '50.0'))
ATTENDANCE_PRESENCE_THRESHOLD_LATE = float(os.environ.get('ATTENDANCE_PRESENCE_THRESHOLD_LATE', '25.0'))
ATTENDANCE_EXAM_ELIGIBILITY_THRESHOLD = float(os.environ.get('ATTENDANCE_EXAM_ELIGIBILITY_THRESHOLD', '75.0'))

# API rate limiting
API_THROTTLE_RATES = {
    'login': '5/min',
    'face_recognition': '60/min',
    'notifications': '100/hour',
    'dashboard': '200/hour',
}

# Development-specific settings
if DEBUG:
    # Django Debug Toolbar
    try:
        import debug_toolbar
        INSTALLED_APPS.append('debug_toolbar')
        MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
        INTERNAL_IPS = ['127.0.0.1', 'localhost']
    except ImportError:
        pass
    
    # Allow all origins in development
    CORS_ALLOW_ALL_ORIGINS = True
    
    # Disable some security features in development
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Production-specific settings
if not DEBUG:
    # Sentry error tracking (optional)
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    if SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[
                DjangoIntegration(auto_enabling=True),
                CeleryIntegration(auto_enabling=True),
            ],
            traces_sample_rate=0.1,
            send_default_pii=True,
            environment=ENVIRONMENT,
        )

# Health check configuration
HEALTH_CHECK_ENABLED = True
HEALTH_CHECK_ENDPOINTS = [
    'database',
    'cache',
    'storage',
]

# API documentation settings
API_DOCUMENTATION = {
    'title': 'Attendance Management System API',
    'description': 'Production-ready facial recognition attendance management system',
    'version': '1.0.0',
    'contact': {
        'name': 'System Administrator',
        'email': 'admin@example.com',
    },
    'license': {
        'name': 'MIT License',
    },
}

# Custom settings validation
def validate_settings():
    """Validate critical settings"""
    errors = []
    
    if not SECRET_KEY or SECRET_KEY == 'django-insecure-change-this-in-production':
        if not DEBUG:
            errors.append("SECRET_KEY must be set in production")
    
    if not DEBUG and not ALLOWED_HOSTS:
        errors.append("ALLOWED_HOSTS must be set in production")
    
    if not DEBUG and not os.environ.get('DATABASE_URL'):
        errors.append("DATABASE_URL must be set in production")
    
    if errors:
        raise ValueError("Settings validation failed:\n" + "\n".join(errors))

# Run settings validation
if not os.environ.get('SKIP_SETTINGS_VALIDATION'):
    validate_settings()

# Feature flags
FEATURES = {
    'FACE_RECOGNITION': True,
    'WHATSAPP_NOTIFICATIONS': bool(WHATSAPP_API_URL and WHATSAPP_API_TOKEN),
    'EMAIL_NOTIFICATIONS': bool(EMAIL_HOST_USER and EMAIL_HOST_PASSWORD),
    'ANALYTICS_DASHBOARD': True,
    'REAL_TIME_TRACKING': True,
    'MULTI_DEPARTMENT_SUPPORT': True,
    'EXAM_ELIGIBILITY_TRACKING': True,
    'AUDIT_LOGGING': True,
}

# System information
SYSTEM_INFO = {
    'name': 'Attendance Management System',
    'version': '1.0.0',
    'environment': ENVIRONMENT,
    'debug': DEBUG,
    'features': FEATURES,
}

print(f"🚀 Attendance Management System v1.0.0 starting in {ENVIRONMENT} mode")
print(f"📊 Features enabled: {', '.join([k for k, v in FEATURES.items() if v])}")
if DEBUG:
    print("⚠️  Running in DEBUG mode - not suitable for production!")
else:
    print("✅ Running in production mode")