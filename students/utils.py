from django.core.exceptions import MultipleObjectsReturned
from rest_framework.exceptions import AuthenticationFailed
from .models import Student

def get_student_from_request(request):
    if not request.user.is_authenticated:
        raise AuthenticationFailed('User is not authenticated')
    
    try:
        # Try to get the student profile using the related_name
        if hasattr(request.user, 'student_profile'):
            return request.user.student_profile
        else:
            # Fallback: try to get student by user
            return Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        raise AuthenticationFailed('Student profile not found')
    except Exception as e:
        raise AuthenticationFailed(f'Authentication error: {str(e)}')