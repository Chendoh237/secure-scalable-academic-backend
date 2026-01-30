from django.db import models

class AcademicProgram(models.Model):
    """Academic programs like Bachelor of Engineering, HND Computer Science"""
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=20, unique=True)
    duration_years = models.PositiveSmallIntegerField(default=4)
    institution = models.ForeignKey(
        'Institution',
        on_delete=models.CASCADE,
        related_name='academic_programs'
    )
    
    def __str__(self):
        return self.name

    class Meta:
        db_table = 'institutions_academicprogram'