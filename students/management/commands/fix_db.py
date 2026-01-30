from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Fix database foreign key constraints'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            # Disable foreign key checks
            cursor.execute('PRAGMA foreign_keys=OFF')
            
            # Drop problematic tables
            cursor.execute('DROP TABLE IF EXISTS students_student')
            cursor.execute('DROP TABLE IF EXISTS students_preapprovedstudent')
            cursor.execute('DROP TABLE IF EXISTS students_studentphoto')
            
            # Recreate tables with correct schema
            cursor.execute('''
                CREATE TABLE students_student (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE REFERENCES auth_user(id),
                    full_name VARCHAR(255) NOT NULL,
                    matric_number VARCHAR(50) NOT NULL UNIQUE,
                    institution_id INTEGER NOT NULL REFERENCES institutions_institution(id),
                    faculty_id INTEGER NOT NULL REFERENCES institutions_faculty(id),
                    department_id INTEGER NOT NULL REFERENCES institutions_department(id),
                    program_id INTEGER NOT NULL REFERENCES institutions_academicprogram(id),
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    face_trained BOOLEAN NOT NULL DEFAULT 0,
                    is_approved BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE students_preapprovedstudent (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    matric_number VARCHAR(50) NOT NULL UNIQUE,
                    institution_id INTEGER NOT NULL REFERENCES institutions_institution(id),
                    faculty_id INTEGER NOT NULL REFERENCES institutions_faculty(id),
                    department_id INTEGER NOT NULL REFERENCES institutions_department(id),
                    program_id INTEGER NOT NULL REFERENCES institutions_academicprogram(id),
                    is_used BOOLEAN NOT NULL DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE students_studentphoto (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id INTEGER NOT NULL REFERENCES students_student(id),
                    image VARCHAR(100) NOT NULL,
                    uploaded_at DATETIME NOT NULL
                )
            ''')
            
            # Re-enable foreign key checks
            cursor.execute('PRAGMA foreign_keys=ON')
            
        self.stdout.write(self.style.SUCCESS('Successfully fixed database schema'))