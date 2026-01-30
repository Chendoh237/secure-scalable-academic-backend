from django.db import models
from .program_models import AcademicProgram

class Institution(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return self.name

class Faculty(models.Model):
    """Faculties within programs like School of Engineering, School of Science"""
    name = models.CharField(max_length=255)
    program = models.ForeignKey(
        AcademicProgram,
        on_delete=models.CASCADE,
        related_name='faculties'
    )

    def __str__(self):
        return self.name

class Department(models.Model):
    """Departments within faculties like Computer Science, Software Engineering"""
    name = models.CharField(max_length=255)
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.CASCADE,
        related_name='departments'
    )

    def __str__(self):
        return self.name
