# Generated migration for presence tracking fields (SQLite compatible)

from django.db import migrations, models
import datetime

class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0007_remove_timetable_is_locked_attendance_is_locked'),
    ]

    operations = [
        # Add presence_duration field (using CharField for SQLite compatibility)
        migrations.AddField(
            model_name='attendance',
            name='presence_duration',
            field=models.DurationField(null=True, blank=True, help_text="Total time student was detected/present during class"),
        ),
        
        # Add total_class_duration field
        migrations.AddField(
            model_name='attendance',
            name='total_class_duration',
            field=models.DurationField(null=True, blank=True, help_text="Total duration of the class session"),
        ),
        
        # Add presence_percentage field
        migrations.AddField(
            model_name='attendance',
            name='presence_percentage',
            field=models.FloatField(null=True, blank=True, help_text="Percentage of class time student was present (0-100)"),
        ),
        
        # Add first_detected_at field
        migrations.AddField(
            model_name='attendance',
            name='first_detected_at',
            field=models.DateTimeField(null=True, blank=True, help_text="When student was first detected in class"),
        ),
        
        # Add last_detected_at field
        migrations.AddField(
            model_name='attendance',
            name='last_detected_at',
            field=models.DateTimeField(null=True, blank=True, help_text="When student was last detected in class"),
        ),
        
        # Add detection_count field
        migrations.AddField(
            model_name='attendance',
            name='detection_count',
            field=models.IntegerField(default=0, help_text="Number of times student was detected during class"),
        ),
        
        # Update status field choices to include 'partial'
        migrations.AlterField(
            model_name='attendance',
            name='status',
            field=models.CharField(
                max_length=10,
                choices=[
                    ('present', 'Present'),
                    ('late', 'Late'),
                    ('absent', 'Absent'),
                    ('partial', 'Partial'),
                ],
                default='absent'
            ),
        ),
    ]