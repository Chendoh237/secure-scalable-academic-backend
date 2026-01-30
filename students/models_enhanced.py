# students/models_enhanced.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from users.models import User
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram
import uuid
import re
import hashlib
import os

User = get_user_model()

def student_photo_path(instance, filename):
    """
    Generate secure path for student photos with hashed directory structure.
    """
    # Create hash of matric number for privacy
    matric_hash = hashlib.sha256(instance.student.matric_number.encode()).hexdigest()[:16]
    return f"student_photos/{matric_hash}/{filename}"

def validate_matricule_format(value):
    """
    Validate matricule format - customize based on institution requirements
    """
    # Example: Allow alphanumeric with specific patterns
    if not re.match(r'^[A-Z0-9]{6,20}$', value.upper()):
        raise ValidationError(
            'Matricule must be 6-20 characters long and contain only letters and numbers'
        )

class ApprovedMatricule(models.Model):
    """Pre-approved matricule numbers for student registration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    matricule = models.CharField(
        max_length=30, 
        unique=True, 
        validators=[validate_matricule_format],
        help_text="Pre-approved matricule number"
    )
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    program = models.ForeignKey(AcademicProgram, on_delete=models.CASCADE)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Approved Matricule"
        verbose_name_plural = "Approved Matricules"
        indexes = [
            models.Index(fields=['matricule']),
            models.Index(fields=['institution', 'is_used']),
        ]

    def __str__(self):
        return f"{self.matricule} ({'Used' if self.is_used else 'Available'})"

    def mark_as_used(self, user):
        """Mark matricule as used by a specific user"""
        self.is_used = True
        self.used_at = timezone.now()
        self.used_by = user
        self.save()

class StudentEnhanced(models.Model):
    """Enhanced Student model with secure matricule enforcement"""
    ENROLLMENT_STATUS = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('graduated', 'Graduated'),
        ('withdrawn', 'Withdrawn'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile_enhanced'
    )
    full_name = models.CharField(max_length=255)
    matric_number = models.CharField(
        max_length=50, 
        unique=True, 
        db_index=True,
        validators=[validate_matricule_format],
        help_text="Unique matricule number (immutable)"
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        related_name='students_enhanced'
    )
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.PROTECT,
        related_name='students_enhanced'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='students_enhanced'
    )
    program = models.ForeignKey(
        AcademicProgram,
        on_delete=models.PROTECT,
        related_name='students_enhanced'
    )
    
    # Academic information
    entry_year = models.IntegerField(help_text="Year of entry")
    current_level = models.IntegerField(default=100, help_text="Current academic level")
    enrollment_status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS, default='active')
    
    # System flags
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(
        default=False,
        help_text="Designates whether this student has been approved by an admin."
    )
    face_trained = models.BooleanField(default=False)
    
    # Facial data security
    face_data_hash = models.CharField(max_length=64, blank=True, help_text="Hash of facial data for integrity")
    face_data_encrypted = models.BooleanField(default=False)
    face_consent_given = models.BooleanField(default=False, help_text="Student consent for facial recognition")
    face_consent_date = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Student Enhanced"
        verbose_name_plural = "Students Enhanced"
        ordering = ['matric_number']
        indexes = [
            models.Index(fields=['matric_number']),
            models.Index(fields=['department', 'is_active']),
            models.Index(fields=['enrollment_status']),
            models.Index(fields=['is_approved', 'is_active']),
        ]

    def clean(self):
        """Validate student data"""
        super().clean()
        
        # Validate matricule is approved
        if not self.pk:  # Only for new students
            try:
                approved_matricule = ApprovedMatricule.objects.get(
                    matricule=self.matric_number,
                    is_used=False
                )
                # Validate department and program match
                if (approved_matricule.department != self.department or 
                    approved_matricule.program != self.program):
                    raise ValidationError(
                        'Matricule is not approved for this department/program combination'
                    )
            except ApprovedMatricule.DoesNotExist:
                raise ValidationError(
                    'Matricule number is not pre-approved or has already been used'
                )

    def save(self, *args, **kwargs):
        """Override save to handle matricule approval"""
        is_new = not self.pk
        
        if is_new:
            self.clean()
            # Mark matricule as used
            try:
                approved_matricule = ApprovedMatricule.objects.get(
                    matricule=self.matric_number,
                    is_used=False
                )
                approved_matricule.mark_as_used(self.user)
            except ApprovedMatricule.DoesNotExist:
                pass  # Validation already handled in clean()
        
        # Prevent matricule changes after creation
        if self.pk:
            original = StudentEnhanced.objects.get(pk=self.pk)
            if original.matric_number != self.matric_number:
                raise ValidationError('Matricule number cannot be changed after creation')
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.matric_number})"

    def get_attendance_percentage(self, course=None, semester=None):
        """Calculate attendance percentage for student"""
        from attendance.models import Attendance
        
        filters = {'student': self}
        if course:
            filters['course_registration__course'] = course
        if semester:
            filters['date__range'] = [semester.start_date, semester.end_date]
        
        total_classes = Attendance.objects.filter(**filters).count()
        if total_classes == 0:
            return 0.0
        
        present_classes = Attendance.objects.filter(
            **filters,
            status__in=['present', 'partial']
        ).count()
        
        return (present_classes / total_classes) * 100

    def is_eligible_for_exam(self, course=None, threshold=75.0):
        """Check if student is eligible for exam based on attendance"""
        attendance_percentage = self.get_attendance_percentage(course)
        return attendance_percentage >= threshold

    def give_face_consent(self):
        """Record student consent for facial recognition"""
        self.face_consent_given = True
        self.face_consent_date = timezone.now()
        self.save()

    def revoke_face_consent(self):
        """Revoke student consent and remove facial data"""
        self.face_consent_given = False
        self.face_consent_date = None
        self.face_trained = False
        self.face_data_hash = ''
        self.face_data_encrypted = False
        
        # Remove all facial photos
        self.photos_enhanced.all().delete()
        self.save()

class StudentPhotoEnhanced(models.Model):
    """Secure student photo storage with encryption support"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        StudentEnhanced,
        on_delete=models.CASCADE,
        related_name='photos_enhanced'
    )
    image = models.ImageField(upload_to=student_photo_path)
    image_hash = models.CharField(max_length=64, help_text="SHA256 hash of image for integrity")
    is_encrypted = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    is_primary = models.BooleanField(default=False)
    quality_score = models.FloatField(null=True, blank=True, help_text="Face detection quality score")

    class Meta:
        verbose_name = "Student Photo Enhanced"
        verbose_name_plural = "Student Photos Enhanced"
        ordering = ['-is_primary', '-uploaded_at']

    def save(self, *args, **kwargs):
        """Generate hash on save"""
        if self.image and not self.image_hash:
            self.image_hash = self._generate_image_hash()
        super().save(*args, **kwargs)

    def _generate_image_hash(self):
        """Generate SHA256 hash of image"""
        if self.image:
            self.image.seek(0)
            return hashlib.sha256(self.image.read()).hexdigest()
        return ''

    def __str__(self):
        return f"{self.student.matric_number} photo ({self.uploaded_at})"