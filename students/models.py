from django.db import models
from users.models import User
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram


def student_photo_path(instance, filename):
    """
    Generate path for student photos.
    Move this function outside the Student class to avoid circular reference.
    """
    # media/student_photos/<matric_number>/<filename>
    return f"student_photos/{instance.student.matric_number}/{filename}"

class ApprovedMatricule(models.Model):
    matricule = models.CharField(max_length=30, unique=True)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE)
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return self.matricule


class Student(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='student_profile'  # Add this line
    )
    full_name = models.CharField(max_length=255)
    matric_number = models.CharField(max_length=50, unique=True, db_index=True)
    institution = models.ForeignKey(
        'institutions.Institution',  # Use string reference to avoid import issues
        on_delete=models.PROTECT
    )
    faculty = models.ForeignKey(
        'institutions.Faculty',
        on_delete=models.PROTECT
    )
    department = models.ForeignKey(
        'institutions.Department',
        on_delete=models.PROTECT
    )
    program = models.ForeignKey(
        'institutions.AcademicProgram',
        on_delete=models.PROTECT
    )
    is_active = models.BooleanField(default=True)
    face_trained = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Add the is_approved field
    is_approved = models.BooleanField(
        default=False,
        help_text="Designates whether this student has been approved by an admin."
    )
    def __str__(self):
        return f"{self.full_name} ({self.matric_number})"


class StudentPhoto(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    # Use the standalone function, not Student.student_photo_path
    image = models.ImageField(upload_to=student_photo_path)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.matric_number} photo"
    
    
    
class PreApprovedStudent(models.Model):
    matric_number = models.CharField(max_length=50, unique=True)

    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT
    )
    faculty = models.ForeignKey(
        Faculty,
        on_delete=models.PROTECT
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT
    )
    program = models.ForeignKey(
        AcademicProgram,
        on_delete=models.PROTECT
    )

    is_used = models.BooleanField(default=False)

    def __str__(self):
        return self.matric_number


class StudentLevelSelection(models.Model):
    """
    Tracks the academic level selected by each student.
    Each student can have only one selected level at a time.
    """
    student = models.OneToOneField(
        Student,
        on_delete=models.CASCADE,
        related_name='level_selection'
    )
    level = models.ForeignKey(
        'courses.Level',  # Use string reference to avoid import issues
        on_delete=models.CASCADE
    )
    selected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def clean(self):
        from django.core.exceptions import ValidationError
        # Validate that level belongs to student's department
        if self.level.department != self.student.department:
            raise ValidationError(
                'Selected level must belong to student\'s department'
            )
    
    def __str__(self):
        return f"{self.student.full_name} - {self.level.name}"


class StudentCourseSelection(models.Model):
    """
    Tracks which courses a student is offering within their selected level.
    This allows students to opt out of specific courses while maintaining
    the overall timetable structure.
    
    The is_approved field supports two enrollment workflows:
    1. Timetable-based: Auto-approved (is_approved=True) when marked as offering
    2. Direct registration: Requires admin approval (is_approved=False initially)
    """
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='course_selections'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE
    )
    level = models.ForeignKey(
        'courses.Level',  # Use string reference to avoid import issues
        on_delete=models.CASCADE
    )
    course = models.ForeignKey(
        'academics.Course',  # Use string reference to avoid import issues
        on_delete=models.CASCADE
    )
    is_offered = models.BooleanField(
        default=True,
        help_text="Whether the student is offering this course"
    )
    is_approved = models.BooleanField(
        default=False,
        help_text="Whether the course selection has been approved (auto-approved for timetable, requires admin approval for direct registration)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'course', 'level']
        indexes = [
            models.Index(fields=['student', 'level']),
            models.Index(fields=['student', 'is_offered']),
            models.Index(fields=['department', 'level']),
            models.Index(fields=['student', 'is_offered', 'is_approved']),
            models.Index(fields=['is_approved']),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(is_offered=False, is_approved=True),
                name='prevent_approved_without_offered'
            )
        ]
    
    def clean(self):
        from django.core.exceptions import ValidationError
        
        # Validate that course belongs to the same department as student
        if self.course.department != self.student.department:
            raise ValidationError(
                'Course must belong to student\'s department'
            )
        
        # Validate that level belongs to the same department as student
        if self.level.department != self.student.department:
            raise ValidationError(
                'Level must belong to student\'s department'
            )
        
        # Validate that department matches student's department
        if self.department != self.student.department:
            raise ValidationError(
                'Department must match student\'s department'
            )
        
        # Validate that course belongs to the specified level
        # This requires checking if the course is scheduled for this level in the timetable
        from courses.models import TimetableSlot
        if not TimetableSlot.objects.filter(
            course=self.course,
            level=self.level,
            timetable__department=self.department
        ).exists():
            raise ValidationError(
                'Course is not scheduled for this level in the timetable'
            )
    
    def __str__(self):
        status = "Offered" if self.is_offered else "Not Offered"
        return f"{self.student.full_name} - {self.course.code} ({status})"


class CourseSelectionAuditLog(models.Model):
    """
    Audit trail for all course selection changes.
    Maintains a complete history of student course selection modifications
    for compliance and debugging purposes.
    """
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
    ]
    
    # Core audit fields
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='course_selection_audit_logs'
    )
    course = models.ForeignKey(
        'academics.Course',
        on_delete=models.CASCADE
    )
    level = models.ForeignKey(
        'courses.Level',
        on_delete=models.CASCADE
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE
    )
    
    # Action details
    action = models.CharField(
        max_length=10,
        choices=ACTION_CHOICES,
        help_text="Type of action performed"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Change tracking
    old_is_offered = models.BooleanField(
        null=True,
        blank=True,
        help_text="Previous offering status (null for CREATE actions)"
    )
    new_is_offered = models.BooleanField(
        help_text="New offering status"
    )
    
    # Context information
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string from the request"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user making the change"
    )
    session_key = models.CharField(
        max_length=40,
        blank=True,
        help_text="Session key for tracking user sessions"
    )
    
    # Additional metadata
    change_reason = models.TextField(
        blank=True,
        help_text="Optional reason for the change"
    )
    batch_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="UUID for grouping related changes made in the same operation"
    )
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['student', '-timestamp']),
            models.Index(fields=['course', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['batch_id']),
        ]
        verbose_name = "Course Selection Audit Log"
        verbose_name_plural = "Course Selection Audit Logs"
    
    def __str__(self):
        return (
            f"{self.student.matric_number} - {self.course.code} - "
            f"{self.action} - {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
    
    @property
    def change_summary(self):
        """Human-readable summary of the change"""
        if self.action == 'CREATE':
            status = "offered" if self.new_is_offered else "not offered"
            return f"Added course as {status}"
        elif self.action == 'UPDATE':
            old_status = "offered" if self.old_is_offered else "not offered"
            new_status = "offered" if self.new_is_offered else "not offered"
            return f"Changed from {old_status} to {new_status}"
        elif self.action == 'DELETE':
            old_status = "offered" if self.old_is_offered else "not offered"
            return f"Removed course (was {old_status})"
        return f"Unknown action: {self.action}"
# Import SystemSettings from models_settings
from .models_settings import SystemSettings

# Import email models
from .email_models import (
    EmailConfiguration,
    EmailTemplate,
    EmailHistory,
    EmailDelivery
)