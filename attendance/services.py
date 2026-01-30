from django.utils import timezone
from attendance.models import Attendance
from students.models import Student
from courses.models import TimetableEntry, CourseRegistration
from attendance.utils import get_current_timetable_entry


def record_attendance(student):
    timetable_entry = get_current_timetable_entry(student)

    if not timetable_entry:
        return None

    attendance, created = Attendance.objects.get_or_create(
        student=student,
        timetable_entry=timetable_entry,
        defaults={"status": "present"}
    )

    if not created:
        return attendance

    attendance.mark_attendance()
    return attendance

def auto_mark_absent():
    """
    Marks students ABSENT if class ended and no attendance was recorded
    """
    now = timezone.localtime()
    current_day = now.strftime('%a').upper()[:3]

    ended_classes = TimetableEntry.objects.filter(
        day_of_week=current_day,
        end_time__lt=now.time()
    )

    for entry in ended_classes:
        students = StudentCourse.objects.filter(
            course_offering=entry.course_offering,
            is_active=True
        ).values_list('student', flat=True)

        for student_id in students:
            Attendance.objects.get_or_create(
                student_id=student_id,
                timetable_entry=entry,
                defaults={"status": "absent"}
            )
            
def lock_finished_attendance():
    now = timezone.localtime()
    attendances = Attendance.objects.filter(
        timetable_entry__end_time__lt=now.time(),
        is_locked=False
    )

    for record in attendances:
        record.lock()

def mark_attendance(student_matric):
    try:
        student = Student.objects.get(matric_number=student_matric)
    except Student.DoesNotExist:
        return {"error": "Student not found"}

    timetable_entry = get_current_timetable_entry(student)

    if not timetable_entry:
        return {"error": "No class ongoing now"}

    attendance, created = Attendance.objects.get_or_create(
        student=student,
        timetable_entry=timetable_entry,
        date=timezone.now().date(),
        defaults={"status": "present"}
    )

    if not created:
        return {"message": "Attendance already marked"}

    return {
        "student": student.matric_number,
        "course": timetable_entry.course_offering.course.code,
        "status": "PRESENT"
    }
