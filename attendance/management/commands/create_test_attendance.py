from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from students.models import Student
from courses.models import Course
from attendance.models import Attendance, CourseRegistration
import random

class Command(BaseCommand):
    help = 'Create test attendance records for students'

    def add_arguments(self, parser):
        parser.add_argument(
            '--students',
            type=int,
            default=5,
            help='Number of students to create attendance for'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days back to create attendance for'
        )

    def handle(self, *args, **options):
        students_count = options['students']
        days_back = options['days']
        
        # Get approved students
        students = Student.objects.filter(is_approved=True)[:students_count]
        
        if not students.exists():
            self.stdout.write(
                self.style.ERROR('No approved students found. Please create and approve some students first.')
            )
            return
        
        # Get available courses
        courses = Course.objects.all()
        
        if not courses.exists():
            self.stdout.write(
                self.style.ERROR('No courses found. Please create some courses first.')
            )
            return
        
        created_registrations = 0
        created_attendance = 0
        
        # Create course registrations and attendance for each student
        for student in students:
            self.stdout.write(f'Creating attendance for student: {student.full_name}')
            
            # Register student for 2-3 random courses
            student_courses = random.sample(list(courses), min(3, len(courses)))
            
            for course in student_courses:
                # Create or get course registration
                registration, created = CourseRegistration.objects.get_or_create(
                    student=student,
                    course=course,
                    defaults={
                        'academic_year': '2024/2025',
                        'semester': 'Semester 1'
                    }
                )
                
                if created:
                    created_registrations += 1
                
                # Create attendance records for the past days
                for i in range(days_back):
                    date = timezone.now().date() - timedelta(days=i)
                    
                    # Skip weekends (assuming classes are Mon-Fri)
                    if date.weekday() >= 5:
                        continue
                    
                    # Random chance of having class on this day (70% chance)
                    if random.random() > 0.7:
                        continue
                    
                    # Check if attendance already exists
                    if Attendance.objects.filter(
                        student=student,
                        course_registration=registration,
                        date=date
                    ).exists():
                        continue
                    
                    # Random attendance status (80% present, 10% late, 10% absent)
                    rand = random.random()
                    if rand < 0.8:
                        status = 'present'
                    elif rand < 0.9:
                        status = 'late'
                    else:
                        status = 'absent'
                    
                    # Create attendance record
                    Attendance.objects.create(
                        student=student,
                        course_registration=registration,
                        date=date,
                        status=status,
                        is_manual_override=False
                    )
                    created_attendance += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created {created_registrations} course registrations '
                f'and {created_attendance} attendance records'
            )
        )