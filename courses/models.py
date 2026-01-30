# courses/models.py
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model
from academics.models import Department, Course, Semester, AcademicYear
import uuid
from datetime import datetime, time

User = get_user_model()

class Level(models.Model):
    """Academic levels within departments"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, help_text="e.g., 100 Level, 200 Level")
    code = models.IntegerField(help_text="Numeric code: 100, 200, 300, etc.")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='levels')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('department', 'code')
        ordering = ['department', 'code']
        verbose_name = "Level"
        verbose_name_plural = "Levels"

    def __str__(self):
        return f"{self.department.code} - {self.name}"

class CourseRegistration(models.Model):
    """Enhanced course registration with approval workflow"""
    REGISTRATION_STATUS = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('auto_approved', 'Auto-Approved'),
        ('withdrawn', 'Withdrawn'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name="course_registrations_enhanced"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="registrations_enhanced")
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name="course_registrations")
    
    # Registration workflow
    status = models.CharField(max_length=20, choices=REGISTRATION_STATUS, default='pending')
    registered_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='approved_registrations'
    )
    rejection_reason = models.TextField(blank=True)
    
    # Academic tracking
    grade = models.CharField(max_length=5, blank=True, help_text="Final grade")
    grade_points = models.FloatField(null=True, blank=True)
    is_retake = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'course', 'semester')
        verbose_name = "Course Registration"
        verbose_name_plural = "Course Registrations"
        indexes = [
            models.Index(fields=['student', 'semester']),
            models.Index(fields=['course', 'semester']),
            models.Index(fields=['status']),
        ]

    def clean(self):
        """Validate course registration"""
        # Check if student belongs to same department as course
        if self.student.department != self.course.department:
            raise ValidationError('Student must belong to the same department as the course')
        
        # Check prerequisites
        if self.course.prerequisites.exists():
            for prerequisite in self.course.prerequisites.all():
                if not CourseRegistration.objects.filter(
                    student=self.student,
                    course=prerequisite,
                    status__in=['approved', 'auto_approved'],
                    grade__in=['A', 'B', 'C', 'D']  # Passing grades
                ).exists():
                    raise ValidationError(f'Prerequisite course {prerequisite.code} not completed')

    def approve(self, approved_by_user):
        """Approve the course registration"""
        self.status = 'approved'
        self.approved_by = approved_by_user
        self.approved_at = timezone.now()
        self.rejection_reason = ''
        self.save()

    def reject(self, rejected_by_user, reason=''):
        """Reject the course registration"""
        self.status = 'rejected'
        self.approved_by = rejected_by_user
        self.approved_at = timezone.now()
        self.rejection_reason = reason
        self.save()

    def auto_approve(self):
        """Auto-approve based on department rules"""
        self.status = 'auto_approved'
        self.approved_at = timezone.now()
        self.save()

    @property
    def is_approved(self):
        """Check if registration is approved"""
        return self.status in ['approved', 'auto_approved']

    def __str__(self):
        return f"{self.student.matric_number} → {self.course.code} ({self.get_status_display()})"

class Timetable(models.Model):
    """Department-based timetable"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="e.g., CS 100 Level - First Semester 2024/2025")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='timetables')
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='timetables')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='timetables')
    is_active = models.BooleanField(default=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ('department', 'level', 'semester')
        verbose_name = "Timetable"
        verbose_name_plural = "Timetables"
        ordering = ['department', 'level', 'semester']

    def __str__(self):
        return self.name

    def get_conflicts(self):
        """Check for scheduling conflicts in this timetable"""
        conflicts = []
        slots = self.slots.all().order_by('day_of_week', 'start_time')
        
        for i, slot1 in enumerate(slots):
            for slot2 in slots[i+1:]:
                if (slot1.day_of_week == slot2.day_of_week and 
                    slot1.overlaps_with(slot2)):
                    conflicts.append((slot1, slot2))
        
        return conflicts

    def publish(self):
        """Publish the timetable"""
        conflicts = self.get_conflicts()
        if conflicts:
            raise ValidationError(f'Cannot publish timetable with {len(conflicts)} conflicts')
        
        self.is_published = True
        self.save()

class TimetableSlot(models.Model):
    """Individual time slots in a timetable"""
    DAYS_OF_WEEK = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
        ('SAT', 'Saturday'),
        ('SUN', 'Sunday'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='slots')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='timetable_slots')
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='timetable_slots')
    lecturer = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='teaching_slots'
    )
    
    # Time details
    day_of_week = models.CharField(max_length=3, choices=DAYS_OF_WEEK)
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField(max_length=100, blank=True)
    
    # Additional info
    session_type = models.CharField(
        max_length=20,
        choices=[
            ('lecture', 'Lecture'),
            ('tutorial', 'Tutorial'),
            ('practical', 'Practical'),
            ('seminar', 'Seminar'),
        ],
        default='lecture'
    )
    max_capacity = models.PositiveIntegerField(default=100)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Timetable Slot"
        verbose_name_plural = "Timetable Slots"
        ordering = ['day_of_week', 'start_time']
        indexes = [
            models.Index(fields=['timetable', 'day_of_week', 'start_time']),
            models.Index(fields=['course', 'level']),
            models.Index(fields=['lecturer']),
        ]

    def clean(self):
        """Validate timetable slot"""
        if self.start_time >= self.end_time:
            raise ValidationError('Start time must be before end time')
        
        # Check for conflicts within the same timetable
        conflicts = TimetableSlot.objects.filter(
            timetable=self.timetable,
            day_of_week=self.day_of_week
        ).exclude(pk=self.pk)
        
        for conflict in conflicts:
            if self.overlaps_with(conflict):
                raise ValidationError(
                    f'Time slot conflicts with {conflict.course.code} '
                    f'({conflict.start_time}-{conflict.end_time})'
                )

    def overlaps_with(self, other_slot):
        """Check if this slot overlaps with another slot"""
        return (self.day_of_week == other_slot.day_of_week and
                self.start_time < other_slot.end_time and
                self.end_time > other_slot.start_time)

    def get_duration_minutes(self):
        """Get duration of the slot in minutes"""
        start_datetime = datetime.combine(datetime.today(), self.start_time)
        end_datetime = datetime.combine(datetime.today(), self.end_time)
        return int((end_datetime - start_datetime).total_seconds() / 60)

    def is_currently_active(self):
        """Check if this slot is currently active"""
        now = timezone.now()
        current_day = now.strftime('%a').upper()[:3]  # MON, TUE, etc.
        current_time = now.time()
        
        return (self.day_of_week == current_day and
                self.start_time <= current_time <= self.end_time)

    def __str__(self):
        return f"{self.course.code} - {self.get_day_of_week_display()} {self.start_time}-{self.end_time}"

class ClassSession(models.Model):
    """Individual class session with state management"""
    SESSION_STATES = [
        ('scheduled', 'Scheduled'),
        ('open', 'Open'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timetable_slot = models.ForeignKey(TimetableSlot, on_delete=models.CASCADE, related_name='sessions')
    date = models.DateField()
    state = models.CharField(max_length=20, choices=SESSION_STATES, default='scheduled')
    
    # Session management
    opened_at = models.DateTimeField(null=True, blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    managed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        related_name='managed_sessions'
    )
    
    # Attendance settings
    attendance_threshold = models.FloatField(
        default=50.0,
        help_text="Minimum presence percentage for attendance"
    )
    scan_interval = models.PositiveIntegerField(
        default=30,
        help_text="Face recognition scan interval in seconds"
    )
    
    # Session notes
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('timetable_slot', 'date')
        verbose_name = "Class Session"
        verbose_name_plural = "Class Sessions"
        ordering = ['-date', 'timetable_slot__start_time']
        indexes = [
            models.Index(fields=['date', 'state']),
            models.Index(fields=['timetable_slot', 'date']),
            models.Index(fields=['state']),
        ]

    def clean(self):
        """Validate class session"""
        # Check if date falls within semester
        semester = self.timetable_slot.timetable.semester
        if not (semester.start_date <= self.date <= semester.end_date):
            raise ValidationError('Session date must be within the semester period')
        
        # Check if date is not a holiday
        from academics.models import Holiday
        if Holiday.is_holiday(self.date, semester.academic_year):
            raise ValidationError('Cannot schedule session on a holiday')

    def open_session(self, user):
        """Open the session for attendance"""
        if self.state != 'scheduled':
            raise ValidationError(f'Cannot open session in {self.state} state')
        
        self.state = 'open'
        self.opened_at = timezone.now()
        self.managed_by = user
        self.save()

    def activate_session(self, user):
        """Activate the session (start attendance tracking)"""
        if self.state != 'open':
            raise ValidationError(f'Cannot activate session in {self.state} state')
        
        self.state = 'active'
        self.activated_at = timezone.now()
        self.managed_by = user
        self.save()

    def close_session(self, user):
        """Close the session (finalize attendance)"""
        if self.state not in ['open', 'active']:
            raise ValidationError(f'Cannot close session in {self.state} state')
        
        self.state = 'closed'
        self.closed_at = timezone.now()
        self.managed_by = user
        self.save()
        
        # Finalize all attendance records for this session
        self._finalize_attendance()

    def cancel_session(self, user, reason=''):
        """Cancel the session"""
        self.state = 'cancelled'
        self.managed_by = user
        self.notes = f"Cancelled: {reason}" if reason else "Cancelled"
        self.save()

    def _finalize_attendance(self):
        """Finalize attendance records for this session"""
        from attendance.models import Attendance
        from attendance.presence_tracking_service import presence_tracking_service
        
        # Get all course registrations for this session
        course_registrations = CourseRegistration.objects.filter(
            course=self.timetable_slot.course,
            semester=self.timetable_slot.timetable.semester,
            status__in=['approved', 'auto_approved']
        )
        
        for registration in course_registrations:
            presence_tracking_service.finalize_class_session(registration, self.date)

    def get_expected_students(self):
        """Get list of students expected to attend this session"""
        return CourseRegistration.objects.filter(
            course=self.timetable_slot.course,
            semester=self.timetable_slot.timetable.semester,
            status__in=['approved', 'auto_approved']
        ).select_related('student')

    def get_attendance_summary(self):
        """Get attendance summary for this session"""
        from attendance.models import Attendance
        
        expected_students = self.get_expected_students()
        total_expected = expected_students.count()
        
        if total_expected == 0:
            return {
                'total_expected': 0,
                'present': 0,
                'partial': 0,
                'late': 0,
                'absent': 0,
                'attendance_rate': 0.0
            }
        
        attendance_records = Attendance.objects.filter(
            course_registration__in=expected_students,
            date=self.date
        )
        
        present = attendance_records.filter(status='present').count()
        partial = attendance_records.filter(status='partial').count()
        late = attendance_records.filter(status='late').count()
        absent = total_expected - (present + partial + late)
        
        return {
            'total_expected': total_expected,
            'present': present,
            'partial': partial,
            'late': late,
            'absent': absent,
            'attendance_rate': ((present + partial + late) / total_expected) * 100
        }

    def __str__(self):
        return f"{self.timetable_slot.course.code} - {self.date} ({self.get_state_display()})"

# Legacy model for backward compatibility
class TimetableEntry(models.Model):
    """Legacy timetable entry - kept for backward compatibility"""
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    day_of_week = models.CharField(max_length=10)
    start_time = models.TimeField()
    end_time = models.TimeField()
    venue = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course.code} - {self.day_of_week} {self.start_time}-{self.end_time}"