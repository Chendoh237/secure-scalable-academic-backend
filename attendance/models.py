# attendance/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from courses.models import TimetableEntry, ClassSession, CourseRegistration
from students.models import Student
from academics.models import Department, Semester, Course
import uuid
from datetime import timedelta

User = get_user_model()

class Attendance(models.Model):
    """Enhanced attendance model with presence tracking and session lifecycle"""
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('late', 'Late'),
        ('absent', 'Absent'),
        ('partial', 'Partial'),  # Students who didn't meet minimum presence
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='attendance_records'
    )
    course_registration = models.ForeignKey(
        CourseRegistration,
        on_delete=models.CASCADE,
        related_name='attendance'
    )
    class_session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        null=True,
        blank=True
    )
    timetable_entry = models.ForeignKey(
        TimetableEntry,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    date = models.DateField(default=timezone.now)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='absent'
    )

    # Enhanced presence tracking fields
    presence_duration = models.DurationField(
        null=True, 
        blank=True,
        help_text="Total time student was detected/present during class"
    )
    total_class_duration = models.DurationField(
        null=True, 
        blank=True,
        help_text="Total duration of the class session"
    )
    presence_percentage = models.FloatField(
        null=True, 
        blank=True,
        help_text="Percentage of class time student was present (0-100)"
    )
    
    # Face detection tracking
    first_detected_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When student was first detected in class"
    )
    last_detected_at = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When student was last detected in class"
    )
    detection_count = models.IntegerField(
        default=0,
        help_text="Number of times student was detected during class"
    )
    
    # Recognition confidence and quality
    avg_confidence = models.FloatField(
        null=True,
        blank=True,
        help_text="Average face recognition confidence score"
    )
    recognition_quality = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
        ],
        blank=True
    )

    # System fields
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_locked = models.BooleanField(default=False, help_text="Prevents further modifications")
    is_manual_override = models.BooleanField(default=False, help_text="Manually set by admin")
    
    # Audit fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_attendance_records'
    )
    modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_attendance_records'
    )

    class Meta:
        unique_together = ('student', 'course_registration', 'date')
        ordering = ['-date', '-recorded_at']
        verbose_name = "Attendance"
        verbose_name_plural = "Attendance Records"
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['course_registration', 'date']),
            models.Index(fields=['class_session', 'status']),
            models.Index(fields=['date', 'status']),
            models.Index(fields=['is_locked']),
        ]

    def clean(self):
        """Validate attendance record"""
        # Ensure attendance is only recorded during active sessions
        if self.class_session and self.class_session.state != 'active' and not self.is_manual_override:
            raise ValidationError('Attendance can only be recorded during active sessions')
        
        # Validate that student is registered for the course
        if not self.course_registration.is_approved:
            raise ValidationError('Student must be approved for the course to record attendance')
        
        # Check if attendance is within timetable constraints
        if self.class_session:
            slot = self.class_session.timetable_slot
            # Validate date matches session date
            if self.date != self.class_session.date:
                raise ValidationError('Attendance date must match class session date')

    def save(self, *args, **kwargs):
        """Override save to handle business logic"""
        # Auto-calculate presence percentage if duration fields are set
        if self.presence_duration and self.total_class_duration and not self.presence_percentage:
            self.update_presence_percentage()
        
        # Auto-determine status based on presence if not manually overridden
        if not self.is_manual_override and self.presence_percentage is not None:
            self.status = self.determine_attendance_status()
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.matric_number} - {self.course_registration.course.code} - {self.date} - {self.status}"
    
    def calculate_presence_percentage(self):
        """Calculate presence percentage based on duration fields"""
        if not self.presence_duration or not self.total_class_duration:
            return 0.0
        
        presence_seconds = self.presence_duration.total_seconds()
        total_seconds = self.total_class_duration.total_seconds()
        
        if total_seconds == 0:
            return 0.0
            
        percentage = (presence_seconds / total_seconds) * 100
        return min(100.0, max(0.0, percentage))  # Clamp between 0-100
    
    def update_presence_percentage(self):
        """Update the presence_percentage field based on duration"""
        self.presence_percentage = self.calculate_presence_percentage()
        return self.presence_percentage
    
    def determine_attendance_status(self, minimum_presence_threshold=None):
        """Determine final attendance status based on presence percentage"""
        if self.is_manual_override:
            return self.status  # Don't change manually set status
        
        # Use session-specific threshold or default
        if minimum_presence_threshold is None:
            if self.class_session:
                minimum_presence_threshold = self.class_session.attendance_threshold
            else:
                minimum_presence_threshold = 75.0
            
        percentage = self.calculate_presence_percentage()
        
        if percentage >= minimum_presence_threshold:
            return 'present'
        elif percentage >= 50.0:  # Partial attendance threshold
            return 'partial'
        elif percentage > 0:
            return 'late'  # Some presence but not enough
        else:
            return 'absent'
    
    def finalize_attendance(self, minimum_presence_threshold=None):
        """Finalize attendance status based on presence data"""
        if not self.is_manual_override:
            self.update_presence_percentage()
            self.status = self.determine_attendance_status(minimum_presence_threshold)
        
        self.is_locked = True
        return self.status
    
    def get_presence_summary(self):
        """Get a summary of presence data for display"""
        return {
            'presence_duration_minutes': self.presence_duration.total_seconds() / 60 if self.presence_duration else 0,
            'total_class_duration_minutes': self.total_class_duration.total_seconds() / 60 if self.total_class_duration else 0,
            'presence_percentage': self.presence_percentage or 0,
            'detection_count': self.detection_count,
            'first_detected': self.first_detected_at,
            'last_detected': self.last_detected_at,
            'status': self.status,
            'is_manual_override': self.is_manual_override,
            'avg_confidence': self.avg_confidence,
            'recognition_quality': self.recognition_quality,
        }

    def can_be_modified(self, user):
        """Check if attendance record can be modified by user"""
        if self.is_locked and not user.is_admin():
            return False
        
        if user.is_admin():
            return True
        
        if user.is_lecturer() and self.course_registration.course in user.taught_courses.all():
            return True
        
        if user.is_department_admin() and user.can_manage_department(self.student.department):
            return True
        
        return False

class AttendanceDetection(models.Model):
    """Individual face detection events during class"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.CASCADE,
        related_name='detections'
    )
    detected_at = models.DateTimeField(auto_now_add=True)
    confidence_score = models.FloatField(help_text="Face recognition confidence (0-1)")
    bounding_box = models.JSONField(
        null=True,
        blank=True,
        help_text="Face bounding box coordinates"
    )
    image_quality = models.FloatField(
        null=True,
        blank=True,
        help_text="Image quality score for this detection"
    )
    
    # Detection context
    camera_id = models.CharField(max_length=50, blank=True)
    session_context = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional context about the detection session"
    )

    class Meta:
        ordering = ['-detected_at']
        verbose_name = "Attendance Detection"
        verbose_name_plural = "Attendance Detections"
        indexes = [
            models.Index(fields=['attendance', 'detected_at']),
            models.Index(fields=['detected_at']),
        ]

    def __str__(self):
        return f"{self.attendance.student.matric_number} - {self.detected_at} (conf: {self.confidence_score:.2f})"

class ExamEligibility(models.Model):
    """Track exam eligibility based on attendance"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_eligibilities')
    course_registration = models.ForeignKey(
        CourseRegistration,
        on_delete=models.CASCADE,
        related_name='exam_eligibilities'
    )
    
    # Eligibility status
    is_eligible = models.BooleanField(default=False)
    attendance_percentage = models.FloatField(help_text="Current attendance percentage")
    required_percentage = models.FloatField(default=75.0, help_text="Required attendance percentage")
    
    # Calculation details
    total_classes = models.PositiveIntegerField(default=0)
    attended_classes = models.PositiveIntegerField(default=0)
    last_calculated = models.DateTimeField(auto_now=True)
    
    # Warning system
    warning_sent = models.BooleanField(default=False)
    warning_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ('student', 'course_registration')
        verbose_name = "Exam Eligibility"
        verbose_name_plural = "Exam Eligibilities"
        indexes = [
            models.Index(fields=['student', 'is_eligible']),
            models.Index(fields=['course_registration', 'is_eligible']),
        ]

    def calculate_eligibility(self):
        """Calculate current exam eligibility"""
        # Get all attendance records for this registration
        attendance_records = Attendance.objects.filter(
            course_registration=self.course_registration
        )
        
        self.total_classes = attendance_records.count()
        if self.total_classes == 0:
            self.attendance_percentage = 0.0
            self.is_eligible = False
        else:
            # Count present, partial, and late as attended
            self.attended_classes = attendance_records.filter(
                status__in=['present', 'partial', 'late']
            ).count()
            
            self.attendance_percentage = (self.attended_classes / self.total_classes) * 100
            self.is_eligible = self.attendance_percentage >= self.required_percentage
        
        self.save()
        return self.is_eligible

    def send_warning_if_needed(self):
        """Send warning if attendance is below threshold and warning not sent"""
        if (not self.is_eligible and 
            not self.warning_sent and 
            self.attendance_percentage < self.required_percentage):
            
            # Send warning notification
            from notifications.models import Notification
            Notification.objects.create(
                user=self.student.user,
                title="Low Attendance Warning",
                message=f"Your attendance for {self.course_registration.course.code} is {self.attendance_percentage:.1f}%. "
                       f"You need {self.required_percentage}% to be eligible for exams.",
                notification_type='warning',
                related_object_id=str(self.id)
            )
            
            self.warning_sent = True
            self.warning_sent_at = timezone.now()
            self.save()

    def __str__(self):
        status = "Eligible" if self.is_eligible else "Not Eligible"
        return f"{self.student.matric_number} - {self.course_registration.course.code} - {status}"

# Legacy model for backward compatibility
class Timetable(models.Model):
    """Legacy timetable model"""
    DAYS_OF_WEEK = [
        ("MON", "Monday"),
        ("TUE", "Tuesday"),
        ("WED", "Wednesday"),
        ("THU", "Thursday"),
        ("FRI", "Friday"),
        ("SAT", "Saturday"),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="timetables"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE
    )
    day = models.CharField(
        max_length=3,
        choices=DAYS_OF_WEEK
    )
    start_time = models.TimeField()
    end_time = models.TimeField()
    level = models.CharField(
        max_length=10,
        help_text="Example: 100, 200, 300"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["day", "start_time"]
        unique_together = ("course", "day", "start_time", "department")

    def __str__(self):
        return f"{self.course.code} - {self.day} ({self.start_time}-{self.end_time})"

def lock(self):
    """Lock attendance record"""
    self.is_locked = True
    self.save()
