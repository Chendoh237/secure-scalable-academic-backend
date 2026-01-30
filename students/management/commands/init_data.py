from django.core.management.base import BaseCommand
from institutions.models import Institution, Faculty, Department, Program

class Command(BaseCommand):
    help = 'Initialize basic institution data'

    def handle(self, *args, **options):
        # Create default institution if none exists
        institution, created = Institution.objects.get_or_create(
            code='DEFAULT',
            defaults={'name': 'Default Institution'}
        )
        if created:
            self.stdout.write(f'Created institution: {institution.name}')

        # Create default faculty if none exists
        faculty, created = Faculty.objects.get_or_create(
            name='Default Faculty',
            defaults={'institution': institution}
        )
        if created:
            self.stdout.write(f'Created faculty: {faculty.name}')

        # Create some default departments
        departments = [
            'Computer Science',
            'Engineering',
            'Business Administration',
            'Mathematics',
            'Physics'
        ]

        for dept_name in departments:
            department, created = Department.objects.get_or_create(
                name=dept_name,
                defaults={'faculty': faculty}
            )
            if created:
                self.stdout.write(f'Created department: {department.name}')

                # Create a default program for each department
                program, created = Program.objects.get_or_create(
                    name=f'{dept_name} Program',
                    defaults={'department': department}
                )
                if created:
                    self.stdout.write(f'Created program: {program.name}')

        self.stdout.write(self.style.SUCCESS('Successfully initialized institution data'))