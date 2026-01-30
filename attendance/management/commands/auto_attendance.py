from django.core.management.base import BaseCommand
from attendance.services import auto_mark_absent, lock_finished_attendance


class Command(BaseCommand):
    help = "Auto mark absent and lock attendance"

    def handle(self, *args, **kwargs):
        auto_mark_absent()
        lock_finished_attendance()
        self.stdout.write("Attendance automation complete.")
