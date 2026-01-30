from django.core.management.base import BaseCommand
from django.utils import timezone
from attendance.utils import auto_create_attendance_for_timetable
from courses.models import TimetableEntry


class Command(BaseCommand):
    help = "Auto-create attendance records for today's classes"

    def handle(self, *args, **kwargs):
        today = timezone.now().strftime('%a').upper()[:3]

        entries = TimetableEntry.objects.filter(
            day_of_week=today
        )

        total = 0
        for entry in entries:
            total += auto_create_attendance_for_timetable(entry)

        self.stdout.write(
            self.style.SUCCESS(
                f"Attendance seeded successfully ({total} records created)"
            )
        )
