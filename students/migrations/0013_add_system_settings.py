# Generated manually for SystemSettings model

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('students', '0012_add_is_approved_to_course_selection'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('institution_name', models.CharField(default='University of Technology', max_length=200)),
                ('institution_code', models.CharField(default='UOT', max_length=20)),
                ('academic_year', models.CharField(default='2023-2024', max_length=20)),
                ('semester', models.CharField(default='Fall 2024', max_length=50)),
                ('timezone', models.CharField(default='UTC+0', max_length=50)),
                ('language', models.CharField(default='en', max_length=10)),
                ('attendance_threshold', models.IntegerField(default=75, help_text='Minimum attendance % for exam eligibility')),
                ('late_threshold', models.IntegerField(default=15, help_text='Minutes after class start considered late')),
                ('auto_mark_absent', models.BooleanField(default=True)),
                ('require_face_recognition', models.BooleanField(default=True)),
                ('allow_manual_override', models.BooleanField(default=True)),
                ('session_timeout', models.IntegerField(default=30, help_text='Session timeout in minutes')),
                ('email_notifications', models.BooleanField(default=True)),
                ('sms_notifications', models.BooleanField(default=False)),
                ('push_notifications', models.BooleanField(default=True)),
                ('low_attendance_alerts', models.BooleanField(default=True)),
                ('session_reminders', models.BooleanField(default=True)),
                ('weekly_reports', models.BooleanField(default=True)),
                ('password_min_length', models.IntegerField(default=8)),
                ('require_two_factor', models.BooleanField(default=False)),
                ('security_session_timeout', models.IntegerField(default=60, help_text='Security session timeout in minutes')),
                ('max_login_attempts', models.IntegerField(default=5)),
                ('require_password_change', models.BooleanField(default=False)),
                ('allow_student_registration', models.BooleanField(default=True)),
                ('maintenance_mode', models.BooleanField(default=False)),
                ('debug_mode', models.BooleanField(default=False)),
                ('data_retention_days', models.IntegerField(default=365)),
                ('backup_frequency', models.CharField(default='daily', max_length=20)),
                ('log_level', models.CharField(default='info', max_length=20)),
                ('max_file_size', models.IntegerField(default=10, help_text='Max file size in MB')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'System Settings',
                'verbose_name_plural': 'System Settings',
            },
        ),
    ]