# academics/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date, datetime
import uuid

class AcademicYear(models.Model):
    """Academic Year model with start and end dates"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=20, unique=True, help_text="e.g., 2024/2025")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = "Academic Year"
        verbose_name_plural = "Academic Years"

    def clean(self):
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError("Start date must be before end date")
        
        # Ensure only one current academic year
        if self.is_current:
            existing_current = AcademicYear.objects.filter(is_current=True).exclude(pk=self.pk)
            if existing_current.exists():
                raise ValidationError("Only one academic year can be current at a time")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    @classmethod
    def get_current(cls):
        """Get the current academic year"""
        return cls.objects.filter(is_current=True).first()

class Semester(models.Model):
    """Semester model linked to academic year"""
    SEMESTER_CHOICES = [
        ('first', 'First Semester'),
        ('second', 'Second Semester'),
        ('summer', 'Summer Semester'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='semesters')
    name = models.CharField(max_length=20, choices=SEMESTER_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('academic_year', 'name')
        ordering = ['academic_year', 'start_date']
        verbose_name = "Semester"
        verbose_name_plural = "Semesters"

    def clean(self):
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                raise ValidationError("Start date must be before end date")
        
        # Ensure semester dates are within academic year
        if self.academic_year:
            if self.start_date < self.academic_year.start_date or self.end_date > self.academic_year.end_date:
                raise ValidationError("Semester dates must be within the academic year")
        
        # Ensure only one current semester per academic year
        if self.is_current:
            existing_current = Semester.objects.filter(
                academic_year=self.academic_year, 
                is_current=True
            ).exclude(pk=self.pk)
            if existing_current.exists():
                raise ValidationError("Only one semester can be current per academic year")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.academic_year.name} - {self.get_name_display()}"

    @classmethod
    def get_current(cls):
        """Get the current semester"""
        return cls.objects.filter(is_current=True).first()

class Holiday(models.Model):
    """Holiday/No-class dates model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='holidays')
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_date']
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"

    def clean(self):
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError("Start date cannot be after end date")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.start_date} - {self.end_date})"

    @classmethod
    def is_holiday(cls, date_to_check, academic_year=None):
        """Check if a given date is a holiday"""
        if not academic_year:
            academic_year = AcademicYear.get_current()
        
        if not academic_year:
            return False
        
        return cls.objects.filter(
            academic_year=academic_year,
            start_date__lte=date_to_check,
            end_date__gte=date_to_check
        ).exists()

class Department(models.Model):
    """Enhanced Department model"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, help_text="Department code (e.g., CS, ENG)")
    description = models.TextField(blank=True)
    head_of_department = models.ForeignKey(
        'users.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='headed_departments'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Department"
        verbose_name_plural = "Departments"

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_active_courses(self):
        """Get all active courses in this department"""
        return self.courses.filter(is_active=True)

    def get_active_students(self):
        """Get all active students in this department"""
        return self.students.filter(is_active=True, is_approved=True)

class Program(models.Model):
    """Academic Program model"""
    PROGRAM_TYPES = [
        ('undergraduate', 'Undergraduate'),
        ('postgraduate', 'Postgraduate'),
        ('diploma', 'Diploma'),
        ('certificate', 'Certificate'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='programs')
    program_type = models.CharField(max_length=20, choices=PROGRAM_TYPES)
    duration_years = models.PositiveIntegerField(help_text="Program duration in years")
    credit_requirement = models.PositiveIntegerField(help_text="Total credits required for graduation")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['department', 'name']
        verbose_name = "Program"
        verbose_name_plural = "Programs"

    def __str__(self):
        return f"{self.code} - {self.name}"

class Course(models.Model):
    """Enhanced Course model with global unique code"""
    COURSE_LEVELS = [
        (100, '100 Level'),
        (200, '200 Level'),
        (300, '300 Level'),
        (400, '400 Level'),
        (500, '500 Level'),
        (600, '600 Level'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=20, unique=True, help_text="Globally unique course code")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    credit_units = models.PositiveIntegerField()
    level = models.IntegerField(choices=COURSE_LEVELS)
    prerequisites = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='prerequisite_for')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['department', 'level', 'code']
        verbose_name = "Course"
        verbose_name_plural = "Courses"

    def __str__(self):
        return f"{self.code} - {self.title}"

    def get_level_display_short(self):
        """Get short level display (e.g., L100)"""
        return f"L{self.level}"

class CourseOffering(models.Model):
    """Course offering for a specific semester"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='offerings')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='course_offerings')
    lecturer = models.ForeignKey(
        'users.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='taught_courses'
    )
    max_enrollment = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('course', 'semester')
        ordering = ['semester', 'course']
        verbose_name = "Course Offering"
        verbose_name_plural = "Course Offerings"

    def __str__(self):
        return f"{self.course.code} - {self.semester}"

    def get_enrollment_count(self):
        """Get current enrollment count"""
        return self.registrations.filter(is_approved=True).count()

    def is_full(self):
        """Check if course is at maximum enrollment"""
        return self.get_enrollment_count() >= self.max_enrollment