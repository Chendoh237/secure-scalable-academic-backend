from django.urls import path
from .api import FaceRecognitionAPI, FaceRegistrationAPI

urlpatterns = [
    # Face recognition endpoint
    path('recognize/', FaceRecognitionAPI.as_view(), name='face-recognize'),
    
    # Face registration endpoint
    path('register/', FaceRegistrationAPI.as_view(), name='face-register'),
]
