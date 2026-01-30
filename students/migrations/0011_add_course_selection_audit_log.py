# Generated manually for course selection audit log

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('institutions', '0003_academicprogram_alter_faculty_program'),
        ('courses', '0003_departmenttimetable_lecturer_level_timetableslot'),
        ('students', '0010_add_student_timetable_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseSelectionAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('CREATE', 'Created'), ('UPDATE', 'Updated'), ('DELETE', 'Deleted')], help_text='Type of action performed', max_length=10)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('old_is_offered', models.BooleanField(blank=True, help_text='Previous offering status (null for CREATE actions)', null=True)),
                ('new_is_offered', models.BooleanField(help_text='New offering status')),
                ('user_agent', models.TextField(blank=True, help_text='User agent string from the request')),
                ('ip_address', models.GenericIPAddressField(blank=True, help_text='IP address of the user making the change', null=True)),
                ('session_key', models.CharField(blank=True, help_text='Session key for tracking user sessions', max_length=40)),
                ('change_reason', models.TextField(blank=True, help_text='Optional reason for the change')),
                ('batch_id', models.UUIDField(blank=True, help_text='UUID for grouping related changes made in the same operation', null=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.course')),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='institutions.department')),
                ('level', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.level')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_selection_audit_logs', to='students.student')),
            ],
            options={
                'verbose_name': 'Course Selection Audit Log',
                'verbose_name_plural': 'Course Selection Audit Logs',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='courseselectionauditlog',
            index=models.Index(fields=['student', '-timestamp'], name='students_co_student_b8e7c8_idx'),
        ),
        migrations.AddIndex(
            model_name='courseselectionauditlog',
            index=models.Index(fields=['course', '-timestamp'], name='students_co_course__c7b8a9_idx'),
        ),
        migrations.AddIndex(
            model_name='courseselectionauditlog',
            index=models.Index(fields=['action', '-timestamp'], name='students_co_action__d9c1b2_idx'),
        ),
        migrations.AddIndex(
            model_name='courseselectionauditlog',
            index=models.Index(fields=['timestamp'], name='students_co_timesta_e2d4f5_idx'),
        ),
        migrations.AddIndex(
            model_name='courseselectionauditlog',
            index=models.Index(fields=['batch_id'], name='students_co_batch_i_f6g8h9_idx'),
        ),
    ]