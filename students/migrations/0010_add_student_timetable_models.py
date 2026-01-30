# Generated migration for Student Timetable Module

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0009_fix_user_foreign_key'),
        ('courses', '0003_departmenttimetable_lecturer_level_timetableslot'),
        ('institutions', '0003_academicprogram_alter_faculty_program'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentLevelSelection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('selected_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('level', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.level')),
                ('student', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='level_selection', to='students.student')),
            ],
        ),
        migrations.CreateModel(
            name='StudentCourseSelection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_offered', models.BooleanField(default=True, help_text='Whether the student is offering this course')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.course')),
                ('department', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='institutions.department')),
                ('level', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.level')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_selections', to='students.student')),
            ],
            options={
                'indexes': [
                    models.Index(fields=['student', 'level'], name='students_st_student_b8e8c5_idx'),
                    models.Index(fields=['student', 'is_offered'], name='students_st_student_0c7b8a_idx'),
                    models.Index(fields=['department', 'level'], name='students_st_departm_f8a9b2_idx'),
                ],
            },
        ),
        migrations.AlterUniqueTogether(
            name='studentcourseselection',
            unique_together={('student', 'course', 'level')},
        ),
    ]