from django.core.management.base import BaseCommand
from institutions.models import Institution, Faculty, Department, Program
from students.models import Student

class Command(BaseCommand):
    help = 'Clean up departments and sync with actual data'

    def handle(self, *args, **options):
        # Clear existing departments that don't have students
        empty_departments = Department.objects.filter(student__isnull=True).distinct()
        for dept in empty_departments:
            self.stdout.write(f'Removing empty department: {dept.name}')
            dept.delete()

        # Get departments that actually have students
        departments_with_students = Department.objects.filter(student__isnull=False).distinct()
        
        self.stdout.write('\nDepartments with students:')
        for dept in departments_with_students:
            student_count = Student.objects.filter(department=dept).count()
            self.stdout.write(f'- {dept.name}: {student_count} students')

        self.stdout.write(self.style.SUCCESS('\nDepartment cleanup completed'))