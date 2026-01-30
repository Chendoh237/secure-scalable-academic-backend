# students/analytics.py
def compute_course_attendance_percentage(student, course_offering):
    from attendance.models import Attendance
    from courses.models import TimetableEntry

    course_days = TimetableEntry.objects.filter(
        course_offering=course_offering
    ).values_list('day_of_week', flat=True)

    total_sessions = Attendance.objects.filter(
        student=student,
        date__week_day__in=[1,2,3,4,5,6,7]
    ).count()

    attended = Attendance.objects.filter(
        student=student,
        date__week_day__in=[1,2,3,4,5,6,7]
    ).count()

    if total_sessions == 0:
        return 0

    return int((attended / total_sessions) * 100)
