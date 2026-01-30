from django.core.management.base import BaseCommand
from institutions.models import Institution, Program, Faculty, Department
from courses.models import Course

class Command(BaseCommand):
    help = 'Populate academic data with proper hierarchy'

    def handle(self, *args, **options):
        # Create institution
        institution, _ = Institution.objects.get_or_create(
            code='CATUC',
            defaults={'name': 'Catholic University of Technology Cameroon'}
        )

        # Create Programs
        programs_data = [
            {'name': 'Bachelor of Engineering', 'code': 'BENG'},
            {'name': 'HND Computer Science', 'code': 'HND-CS'},
            {'name': 'Bachelor of Science', 'code': 'BSC'},
            {'name': 'Higher National Diploma', 'code': 'HND'},
        ]

        for prog_data in programs_data:
            program, created = Program.objects.get_or_create(
                code=prog_data['code'],
                defaults={
                    'name': prog_data['name'],
                    'institution': institution
                }
            )
            if created:
                self.stdout.write(f'Created program: {program.name}')

        # Create Faculties for each program
        faculties_data = [
            {'name': 'School of Engineering', 'program_code': 'BENG'},
            {'name': 'School of Engineering', 'program_code': 'HND'},
            {'name': 'School of Computer Science', 'program_code': 'HND-CS'},
            {'name': 'School of Science', 'program_code': 'BSC'},
        ]

        for fac_data in faculties_data:
            program = Program.objects.get(code=fac_data['program_code'])
            faculty, created = Faculty.objects.get_or_create(
                name=fac_data['name'],
                program=program
            )
            if created:
                self.stdout.write(f'Created faculty: {faculty.name} under {program.name}')

        # Create Departments for each faculty
        departments_data = [
            {'name': 'Computer Engineering', 'faculty': 'School of Engineering', 'program': 'BENG'},
            {'name': 'Electrical Engineering', 'faculty': 'School of Engineering', 'program': 'BENG'},
            {'name': 'Computer Science', 'faculty': 'School of Computer Science', 'program': 'HND-CS'},
            {'name': 'Software Engineering', 'faculty': 'School of Computer Science', 'program': 'HND-CS'},
            {'name': 'Mathematics', 'faculty': 'School of Science', 'program': 'BSC'},
            {'name': 'Physics', 'faculty': 'School of Science', 'program': 'BSC'},
        ]

        for dept_data in departments_data:
            program = Program.objects.get(code=dept_data['program'])
            faculty = Faculty.objects.get(name=dept_data['faculty'], program=program)
            department, created = Department.objects.get_or_create(
                name=dept_data['name'],
                faculty=faculty
            )
            if created:
                self.stdout.write(f'Created department: {department.name} under {faculty.name}')

        # Create Courses for each department
        courses_data = [
            # Computer Engineering courses
            {'code': 'CE101', 'title': 'Introduction to Computer Engineering', 'dept': 'Computer Engineering', 'level': 'Level 1', 'semester': 'Semester 1', 'credits': 3},
            {'code': 'CE102', 'title': 'Digital Logic Design', 'dept': 'Computer Engineering', 'level': 'Level 1', 'semester': 'Semester 2', 'credits': 4},
            {'code': 'CE201', 'title': 'Computer Architecture', 'dept': 'Computer Engineering', 'level': 'Level 2', 'semester': 'Semester 1', 'credits': 3},
            
            # Computer Science courses
            {'code': 'CS101', 'title': 'Introduction to Programming', 'dept': 'Computer Science', 'level': 'HND 1', 'semester': 'Semester 1', 'credits': 4},
            {'code': 'CS102', 'title': 'Data Structures', 'dept': 'Computer Science', 'level': 'HND 1', 'semester': 'Semester 2', 'credits': 3},
            {'code': 'CS201', 'title': 'Database Systems', 'dept': 'Computer Science', 'level': 'HND 2', 'semester': 'Semester 1', 'credits': 3},
            
            # Software Engineering courses
            {'code': 'SE101', 'title': 'Software Engineering Principles', 'dept': 'Software Engineering', 'level': 'HND 1', 'semester': 'Semester 1', 'credits': 3},
            {'code': 'SE102', 'title': 'Object-Oriented Programming', 'dept': 'Software Engineering', 'level': 'HND 1', 'semester': 'Semester 2', 'credits': 4},
            {'code': 'SE201', 'title': 'Web Development', 'dept': 'Software Engineering', 'level': 'HND 2', 'semester': 'Semester 1', 'credits': 4},
        ]

        for course_data in courses_data:
            try:
                department = Department.objects.get(name=course_data['dept'])
                course, created = Course.objects.get_or_create(
                    code=course_data['code'],
                    defaults={
                        'title': course_data['title'],
                        'department': department,
                        'level': course_data['level'],
                        'semester': course_data['semester'],
                        'credit_units': course_data['credits'],
                        'attendance_threshold': 75
                    }
                )
                if created:
                    self.stdout.write(f'Created course: {course.code} - {course.title}')
            except Department.DoesNotExist:
                self.stdout.write(f'Department {course_data["dept"]} not found for course {course_data["code"]}')

        self.stdout.write(self.style.SUCCESS('Successfully populated academic data'))