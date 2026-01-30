from attendance.models import Attendance
from courses.models import Course
from django.db.models import Count, Q

def get_attendance_summary(student):
    try:
        records = (
            Attendance.objects
            .filter(student=student)
            .values(
                "course_registration__course__code",
                "course_registration__course__title",
                "course_registration__course__attendance_threshold",
            )
            .annotate(
                total_classes=Count("id"),
                attended=Count("id", filter=Q(status__in=["present", "late"]))
            )
        )

        summary = []
        for r in records:
            if r["total_classes"] > 0:  # Only include courses with attendance records
                percentage = (
                    (r["attended"] / r["total_classes"]) * 100
                    if r["total_classes"] > 0 else 0
                )

                summary.append({
                    "course_code": r["course_registration__course__code"] or "N/A",
                    "course_title": r["course_registration__course__title"] or "Unknown Course",
                    "attendance_percentage": round(percentage, 2),
                    "eligible_for_exam": percentage >= (r["course_registration__course__attendance_threshold"] or 75)
                })

        return summary
    except Exception as e:
        # Return empty summary if there's an error
        return []
