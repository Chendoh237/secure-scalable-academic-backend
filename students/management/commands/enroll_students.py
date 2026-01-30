from django.core.management.base import BaseCommand
from students.models import Student
from courses.models import Course, CourseOffering, StudentCourse
from django.utils import timezone

class Command(BaseCommand):
    help = 'Enroll approved students in available courses'

    def handle(self, *args, **options):
        # Get approved students
        students = Student.objects.filter(is_approved=True)
        
        if not students.exists():
            self.stdout.write(self.style.ERROR('No approved students found'))
            return
        
        # Get or create course offerings
        courses = Course.objects.all()
        
        if not courses.exists():
            self.stdout.write(self.style.ERROR('No courses found'))
            return
        
        enrollments_created = 0
        
        for student in students:
            self.stdout.write(f'Enrolling student: {student.full_name}')
            
            # Get courses from student's department
            dept_courses = courses.filter(department=student.department)
            
            for course in dept_courses[:3]:  # Enroll in first 3 courses
                # Create or get course offering
                offering, created = CourseOffering.objects.get_or_create(
                    course=course,
                    academic_year='2024/2025',
                    semester='1',
                    defaults={
                        'instructor_name': 'Dr. Sample Instructor'
                    }
                )
                
                # Create student course enrollment
                enrollment, created = StudentCourse.objects.get_or_create(
                    student=student,
                    course_offering=offering,
                    defaults={
                        'is_active': True
                    }
                )
                
                if created:
                    enrollments_created += 1
                    self.stdout.write(f'  - Enrolled in {course.code}')
        
        self.stdout.write(
            self.style.SUCCESS(f'Created {enrollments_created} course enrollments')
        )