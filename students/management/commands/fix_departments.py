from django.core.management.base import BaseCommand
from institutions.models import Institution, Faculty, Department, Program
from students.models import Student

class Command(BaseCommand):
    help = 'Create correct departments and reassign students'

    def handle(self, *args, **options):
        # Get the existing faculty
        faculty = Faculty.objects.first()
        if not faculty:
            self.stdout.write(self.style.ERROR('No faculty found'))
            return

        # Create the correct departments
        cs_dept, created = Department.objects.get_or_create(
            name='COMPUTER SCIENCE',
            defaults={'faculty': faculty}
        )
        if created:
            self.stdout.write(f'Created department: {cs_dept.name}')

        se_dept, created = Department.objects.get_or_create(
            name='Software Engineering', 
            defaults={'faculty': faculty}
        )
        if created:
            self.stdout.write(f'Created department: {se_dept.name}')

        # Get all students
        students = Student.objects.all()
        total_students = students.count()
        
        if total_students == 0:
            self.stdout.write('No students to reassign')
            return

        # Split students between departments (roughly half each)
        cs_students = students[:total_students//2 + total_students%2]  # First half + remainder
        se_students = students[total_students//2 + total_students%2:]  # Second half

        # Reassign students to COMPUTER SCIENCE
        for student in cs_students:
            student.department = cs_dept
            student.save()
            self.stdout.write(f'Assigned {student.full_name} to COMPUTER SCIENCE')

        # Reassign students to Software Engineering  
        for student in se_students:
            student.department = se_dept
            student.save()
            self.stdout.write(f'Assigned {student.full_name} to Software Engineering')

        # Delete old Computer Engineering department if it exists and is empty
        try:
            old_dept = Department.objects.get(name='Computer Engineering')
            if old_dept.student_set.count() == 0:
                old_dept.delete()
                self.stdout.write('Removed old Computer Engineering department')
        except Department.DoesNotExist:
            pass

        self.stdout.write(self.style.SUCCESS(f'Successfully reassigned {total_students} students to correct departments'))