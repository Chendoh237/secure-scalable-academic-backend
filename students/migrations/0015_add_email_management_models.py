# Generated migration for email management models

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0013_add_system_settings'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('smtp_host', models.CharField(help_text='SMTP server hostname', max_length=255)),
                ('smtp_port', models.IntegerField(default=587, help_text='SMTP server port')),
                ('smtp_username', models.CharField(help_text='SMTP username/email', max_length=255)),
                ('smtp_password', models.TextField(help_text='Encrypted SMTP password')),
                ('use_tls', models.BooleanField(default=True, help_text='Use TLS encryption')),
                ('use_ssl', models.BooleanField(default=False, help_text='Use SSL encryption')),
                ('from_email', models.EmailField(help_text='From email address', max_length=254)),
                ('from_name', models.CharField(default='Student Management System', help_text='From name', max_length=255)),
                ('is_active', models.BooleanField(default=True, help_text='Is this configuration active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Email Configuration',
                'verbose_name_plural': 'Email Configurations',
                'db_table': 'email_configuration',
            },
        ),
        migrations.CreateModel(
            name='EmailTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(help_text='Template name', max_length=255)),
                ('category', models.CharField(choices=[('attendance', 'Attendance'), ('course', 'Course Updates'), ('exam', 'Exam Notifications'), ('general', 'General Announcements')], help_text='Template category', max_length=100)),
                ('subject_template', models.CharField(help_text='Email subject template', max_length=500)),
                ('body_template', models.TextField(help_text='Email body template')),
                ('variables', models.JSONField(default=list, help_text='Available template variables')),
                ('description', models.TextField(blank=True, help_text='Template description')),
                ('is_active', models.BooleanField(default=True, help_text='Is this template active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Email Template',
                'verbose_name_plural': 'Email Templates',
                'db_table': 'email_template',
                'ordering': ['category', 'name'],
            },
        ),
        migrations.CreateModel(
            name='EmailHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('subject', models.CharField(help_text='Email subject', max_length=500)),
                ('body', models.TextField(help_text='Email body content')),
                ('recipient_count', models.IntegerField(default=0, help_text='Total number of recipients')),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[('sending', 'Sending'), ('completed', 'Completed'), ('failed', 'Failed'), ('cancelled', 'Cancelled')], default='sending', max_length=50)),
                ('success_count', models.IntegerField(default=0, help_text='Number of successful deliveries')),
                ('failure_count', models.IntegerField(default=0, help_text='Number of failed deliveries')),
                ('error_message', models.TextField(blank=True, help_text='Error message if sending failed')),
                ('sender', models.ForeignKey(help_text='User who sent the email', on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('template_used', models.ForeignKey(blank=True, help_text='Template used for this email', null=True, on_delete=django.db.models.deletion.SET_NULL, to='students.emailtemplate')),
            ],
            options={
                'verbose_name': 'Email History',
                'verbose_name_plural': 'Email History',
                'db_table': 'email_history',
                'ordering': ['-sent_at'],
            },
        ),
        migrations.CreateModel(
            name='EmailDelivery',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recipient_email', models.EmailField(help_text='Recipient email address', max_length=254)),
                ('recipient_name', models.CharField(blank=True, help_text='Recipient name', max_length=255)),
                ('delivery_status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('delivered', 'Delivered'), ('failed', 'Failed'), ('bounced', 'Bounced')], default='pending', max_length=50)),
                ('error_message', models.TextField(blank=True, help_text='Error message if delivery failed')),
                ('sent_at', models.DateTimeField(blank=True, help_text='When email was sent', null=True)),
                ('delivered_at', models.DateTimeField(blank=True, help_text='When email was delivered', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('email_history', models.ForeignKey(help_text='Associated email history record', on_delete=django.db.models.deletion.CASCADE, related_name='deliveries', to='students.emailhistory')),
                ('student', models.ForeignKey(blank=True, help_text='Associated student record', null=True, on_delete=django.db.models.deletion.SET_NULL, to='students.student')),
            ],
            options={
                'verbose_name': 'Email Delivery',
                'verbose_name_plural': 'Email Deliveries',
                'db_table': 'email_delivery',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='emaildelivery',
            index=models.Index(fields=['email_history', 'delivery_status'], name='email_deliv_email_h_b8c5a4_idx'),
        ),
        migrations.AddIndex(
            model_name='emaildelivery',
            index=models.Index(fields=['recipient_email'], name='email_deliv_recipie_8b5c2a_idx'),
        ),
        migrations.AddIndex(
            model_name='emaildelivery',
            index=models.Index(fields=['student'], name='email_deliv_student_f3d2a1_idx'),
        ),
    ]