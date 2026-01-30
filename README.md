# Secure Scalable Academic System - Backend

Django REST API backend for the Secure Scalable Academic System.

## Features

- **User Management**: Custom user model with role-based authentication
- **Student Portal**: Course registration, timetables, attendance tracking
- **Admin Dashboard**: Student management, course management, analytics
- **Face Recognition**: Attendance tracking with face recognition
- **Email System**: Automated notifications and email management
- **Real-time Features**: Live sessions and notifications
- **Security**: JWT authentication, CORS protection, audit trails

## Quick Deploy

### Railway (Recommended)
1. Fork this repository
2. Connect to Railway
3. Set environment variables:
   - `DJANGO_SETTINGS_MODULE=backend.production_settings`
   - `SECRET_KEY=your-secret-key`
4. Deploy

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

## Environment Variables

- `SECRET_KEY`: Django secret key
- `DEBUG`: Set to False in production
- `DATABASE_URL`: Database connection string (optional)
- `EMAIL_HOST`: SMTP server host
- `EMAIL_HOST_USER`: SMTP username
- `EMAIL_HOST_PASSWORD`: SMTP password

## API Endpoints

- `/api/health/` - Health check
- `/api/token/` - JWT authentication
- `/api/students/` - Student management
- `/api/courses/` - Course management
- `/api/attendance/` - Attendance tracking
- `/api/face/` - Face recognition
- `/api/notifications/` - Notifications

## Architecture

- **Django 5.2**: Web framework
- **Django REST Framework**: API framework
- **JWT Authentication**: Secure token-based auth
- **SQLite/PostgreSQL**: Database
- **Face Recognition**: OpenCV + face_recognition
- **Email**: SMTP integration
- **File Storage**: Local/Cloud storage support

## License

MIT License