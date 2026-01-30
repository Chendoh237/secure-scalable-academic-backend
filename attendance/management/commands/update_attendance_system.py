"""
Management command to update the attendance system with course selection integration.

This command helps migrate from the old attendance system to the new enhanced system
that considers student course selections.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from attendance.compatibility import auto_mark_absent_enhanced
from attendance.enhanced_services import EnhancedAttendanceService
from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import TimetableSlot
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Update attendance system with course selection integration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto-mark-absent',
            action='store_true',
            help='Auto-mark students absent for ended classes (considering course selections)',
        )
        parser.add_argument(
            '--validate-students',
            action='store_true',
            help='Validate all students have proper level and course selections',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--student-matric',
            type=str,
            help='Process specific student by matric number',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Starting attendance system update...')
        )

        if options['auto_mark_absent']:
            self.auto_mark_absent(options['dry_run'])

        if options['validate_students']:
            self.validate_students(options['dry_run'])

        if options['student_matric']:
            self.process_specific_student(options['student_matric'], options['dry_run'])

        self.stdout.write(
            self.style.SUCCESS('Attendance system update completed!')
        )

    def auto_mark_absent(self, dry_run=False):
        """Auto-mark students absent for ended classes considering course selections"""
        self.stdout.write('Auto-marking absent students...')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        try:
            if not dry_run:
                auto_mark_absent_enhanced()
            
            self.stdout.write(
                self.style.SUCCESS('✓ Auto-mark absent completed')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Error auto-marking absent: {e}')
            )

    def validate_students(self, dry_run=False):
        """Validate all students have proper level and course selections"""
        self.stdout.write('Validating student configurations...')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        students = Student.objects.select_related('department').all()
        issues_found = 0
        
        for student in students:
            issues = self.validate_single_student(student, dry_run)
            if issues:
                issues_found += len(issues)
                self.stdout.write(
                    self.style.WARNING(f'Student {student.matric_number}:')
                )
                for issue in issues:
                    self.stdout.write(f'  - {issue}')
        
        if issues_found == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ All students have valid configurations')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Found {issues_found} configuration issues')
            )

    def validate_single_student(self, student, dry_run=False):
        """Validate a single student's configuration"""
        issues = []
        
        # Check if student has selected a level
        try:
            level_selection = StudentLevelSelection.objects.get(student=student)
        except StudentLevelSelection.DoesNotExist:
            issues.append('No level selection found')
            return issues
        
        # Check if student has course selections for their level
        level_courses = TimetableSlot.objects.filter(
            timetable__department=student.department,
            level=level_selection.level
        ).values_list('course', flat=True).distinct()
        
        student_selections = StudentCourseSelection.objects.filter(
            student=student,
            level=level_selection.level
        ).values_list('course', flat=True)
        
        missing_selections = set(level_courses) - set(student_selections)
        
        if missing_selections:
            issues.append(f'Missing course selections for {len(missing_selections)} courses')
            
            if not dry_run:
                # Auto-create missing course selections with default "offered" status
                for course_id in missing_selections:
                    try:
                        from courses.models import Course
                        course = Course.objects.get(id=course_id)
                        StudentCourseSelection.objects.create(
                            student=student,
                            department=student.department,
                            level=level_selection.level,
                            course=course,
                            is_offered=True,  # Default to offered
                            is_approved=True  # Auto-approve timetable courses
                        )
                        self.stdout.write(
                            f'  ✓ Created default course selection for {course.code}'
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'  ✗ Failed to create selection for course {course_id}: {e}')
                        )
        
        return issues

    def process_specific_student(self, matric_number, dry_run=False):
        """Process a specific student"""
        self.stdout.write(f'Processing student {matric_number}...')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))
        
        try:
            student = Student.objects.select_related('department').get(
                matric_number=matric_number
            )
        except Student.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'Student {matric_number} not found')
            )
            return
        
        # Validate student configuration
        issues = self.validate_single_student(student, dry_run)
        
        if issues:
            self.stdout.write(
                self.style.WARNING(f'Issues found for {matric_number}:')
            )
            for issue in issues:
                self.stdout.write(f'  - {issue}')
        else:
            self.stdout.write(
                self.style.SUCCESS(f'✓ {matric_number} configuration is valid')
            )
        
        # Get current timetable slot
        current_slot = EnhancedAttendanceService.get_current_timetable_slot_for_student(student)
        
        if current_slot:
            self.stdout.write(f'Current class: {current_slot.course.code}')
            
            # Validate attendance eligibility
            validation = EnhancedAttendanceService.validate_attendance_eligibility(student, current_slot)
            
            if validation['eligible']:
                self.stdout.write(
                    self.style.SUCCESS('✓ Student is eligible for attendance')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'✗ Not eligible: {validation["reason"]}')
                )
        else:
            self.stdout.write('No current class or student not offering current courses')
        
        # Get offered courses summary
        offered_courses = EnhancedAttendanceService.get_student_offered_courses(student)
        self.stdout.write(f'Offering {len(offered_courses)} courses:')
        for course in offered_courses:
            self.stdout.write(f'  - {course["course_code"]}: {course["course_title"]}')

    def style_message(self, message, style='SUCCESS'):
        """Helper to style messages"""
        if style == 'SUCCESS':
            return self.style.SUCCESS(message)
        elif style == 'WARNING':
            return self.style.WARNING(message)
        elif style == 'ERROR':
            return self.style.ERROR(message)
        else:
            return message