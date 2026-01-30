# Email Configuration Template
# Add these settings to your Django settings.py file

# Email Backend Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# SMTP Configuration (Gmail Example)
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'  # Use App Password for Gmail
DEFAULT_FROM_EMAIL = 'Academic System <noreply@yourschool.edu>'

# Email Settings
EMAIL_FROM_NAME = 'Academic System'
EMAIL_TIMEOUT = 30

# For development/testing (console backend)
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# For production with different providers:

# Outlook/Hotmail
# EMAIL_HOST = 'smtp-mail.outlook.com'
# EMAIL_PORT = 587

# Yahoo
# EMAIL_HOST = 'smtp.mail.yahoo.com'
# EMAIL_PORT = 587

# Custom SMTP
# EMAIL_HOST = 'your-smtp-server.com'
# EMAIL_PORT = 587  # or 465 for SSL