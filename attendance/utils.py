from datetime import date
from django.utils import timezone
from courses.models import CourseRegistration, TimetableEntry
from attendance.models import Timetable, Attendance

def auto_create_attendance_for_timetable(timetable_entry):
    """
    Automatically creates ABSENT attendance records
    for all enrolled students before class starts.
    """

    today = timezone.now().date()

    registrations = CourseRegistration.objects.filter(
        course_offering=timetable_entry.course_offering,
        is_active=True
    )

    created_count = 0

    for reg in registrations:
        attendance, created = Attendance.objects.get_or_create(
            student=reg.student,
            course_registration=reg,
            timetable_entry=timetable_entry,
            date=today,
            defaults={
                'status': 'absent'
            }
        )

        if created:
            created_count += 1

    return created_count


def get_today_timetable_for_student(student):
    """
    Returns today's timetable entries for a given student
    """

    today_day = timezone.now().strftime("%a").upper()[:3]  # MON, TUE...

    registrations = CourseRegistration.objects.filter(
        student=student,
        is_active=True
    )

    courses = registrations.values_list("course", flat=True)

    timetable = Timetable.objects.filter(
        day=today_day,
        course__in=courses,
        department=student.department,
        level=student.level,
        is_active=True
    )

    return timetable


def get_current_timetable_entry(student):
    """
    Returns the timetable entry happening right now for the student
    """
    now = timezone.localtime()
    current_day = now.strftime('%a').upper()[:3]  # MON, TUE...
    current_time = now.time()

    # Get student's active course offerings
    offerings = StudentCourse.objects.filter(
        student=student,
        is_active=True
    ).values_list('course_offering', flat=True)

    return TimetableEntry.objects.filter(
        course_offering__in=offerings,
        day_of_week=current_day,
        start_time__lte=current_time,
        end_time__gte=current_time
    ).first()


def determine_attendance_status(timetable_entry):
    """
    Determines Present / Late based on class start time
    """
    now = timezone.localtime().time()

    if now <= timetable_entry.start_time:
        return "present"
    return "late"

def calculate_attendance_percentage(student, course_offering):
    total_classes = Attendance.objects.filter(
        student=student,
        timetable_entry__course_offering=course_offering
    ).count()

    if total_classes == 0:
        return 0

    attended = Attendance.objects.filter(
        student=student,
        timetable_entry__course_offering=course_offering,
        status__in=["present", "late"]
    ).count()

    return round((attended / total_classes) * 100, 2)
