from django.core.management.base import BaseCommand
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram
from courses.models import Course

class Command(BaseCommand):
    help = 'Create proper academic hierarchy: Program → Faculty → Department → Courses'

    def handle(self, *args, **options):
        # Create institution
        institution, _ = Institution.objects.get_or_create(
            code='CATUC',
            defaults={'name': 'Catholic University of Technology Cameroon'}
        )

        # Create Academic Programs (distinct from departments)
        programs_data = [
            {'name': 'Bachelor of Engineering', 'code': 'BENG', 'years': 4},
            {'name': 'Higher National Diploma', 'code': 'HND', 'years': 2},
            {'name': 'Bachelor of Science', 'code': 'BSC', 'years': 3},
            {'name': 'Master of Engineering', 'code': 'MENG', 'years': 2},
        ]

        for prog_data in programs_data:
            program, created = AcademicProgram.objects.get_or_create(
                code=prog_data['code'],
                defaults={
                    'name': prog_data['name'],
                    'institution': institution,
                    'duration_years': prog_data['years']
                }
            )
            if created:
                self.stdout.write(f'Created program: {program.name}')

        # Create Faculties under Programs
        faculties_data = [
            {'name': 'School of Engineering', 'program_code': 'BENG'},
            {'name': 'School of Engineering Technology', 'program_code': 'HND'},
            {'name': 'School of Pure and Applied Sciences', 'program_code': 'BSC'},
            {'name': 'School of Postgraduate Studies', 'program_code': 'MENG'},
        ]

        for fac_data in faculties_data:
            program = AcademicProgram.objects.get(code=fac_data['program_code'])
            faculty, created = Faculty.objects.get_or_create(
                name=fac_data['name'],
                program=program
            )
            if created:
                self.stdout.write(f'Created faculty: {faculty.name} under {program.name}')

        # Create Departments under Faculties
        departments_data = [
            # Bachelor of Engineering departments
            {'name': 'Computer Engineering', 'faculty': 'School of Engineering'},
            {'name': 'Electrical Engineering', 'faculty': 'School of Engineering'},
            {'name': 'Mechanical Engineering', 'faculty': 'School of Engineering'},
            
            # HND departments
            {'name': 'Computer Science', 'faculty': 'School of Engineering Technology'},
            {'name': 'Software Engineering', 'faculty': 'School of Engineering Technology'},
            {'name': 'Civil Engineering Technology', 'faculty': 'School of Engineering Technology'},
            
            # BSC departments
            {'name': 'Mathematics', 'faculty': 'School of Pure and Applied Sciences'},
            {'name': 'Physics', 'faculty': 'School of Pure and Applied Sciences'},
            {'name': 'Chemistry', 'faculty': 'School of Pure and Applied Sciences'},
            
            # Masters departments
            {'name': 'Advanced Computer Engineering', 'faculty': 'School of Postgraduate Studies'},
        ]

        for dept_data in departments_data:
            faculty = Faculty.objects.get(name=dept_data['faculty'])
            department, created = Department.objects.get_or_create(
                name=dept_data['name'],
                faculty=faculty
            )
            if created:
                self.stdout.write(f'Created department: {department.name} under {faculty.name}')

        # Create Courses for Departments
        courses_data = [
            # Computer Engineering (BENG)
            {'code': 'CE301', 'title': 'Advanced Computer Architecture', 'dept': 'Computer Engineering', 'level': 'Level 3', 'semester': 'Semester 1', 'credits': 3},
            {'code': 'CE302', 'title': 'Embedded Systems Design', 'dept': 'Computer Engineering', 'level': 'Level 3', 'semester': 'Semester 2', 'credits': 4},
            
            # Computer Science (HND)
            {'code': 'CS201', 'title': 'Advanced Programming', 'dept': 'Computer Science', 'level': 'HND 2', 'semester': 'Semester 1', 'credits': 4},
            {'code': 'CS202', 'title': 'Database Management Systems', 'dept': 'Computer Science', 'level': 'HND 2', 'semester': 'Semester 2', 'credits': 3},
            
            # Software Engineering (HND)
            {'code': 'SE201', 'title': 'Software Project Management', 'dept': 'Software Engineering', 'level': 'HND 2', 'semester': 'Semester 1', 'credits': 3},
            {'code': 'SE202', 'title': 'Mobile App Development', 'dept': 'Software Engineering', 'level': 'HND 2', 'semester': 'Semester 2', 'credits': 4},
            
            # Mathematics (BSC)
            {'code': 'MTH301', 'title': 'Advanced Calculus', 'dept': 'Mathematics', 'level': 'Level 3', 'semester': 'Semester 1', 'credits': 3},
            {'code': 'MTH302', 'title': 'Linear Algebra', 'dept': 'Mathematics', 'level': 'Level 3', 'semester': 'Semester 2', 'credits': 3},
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
                self.stdout.write(f'Department {course_data["dept"]} not found')

        self.stdout.write(self.style.SUCCESS('Successfully created academic hierarchy: Program → Faculty → Department → Courses'))