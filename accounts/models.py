from django.db import models

# Create your models here.
from django.contrib.auth.models import User
from django.db import models

class UserRole(models.TextChoices):
    STUDENT = "STUDENT"
    ADMIN = "ADMIN"
