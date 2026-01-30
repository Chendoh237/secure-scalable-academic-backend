# Generated migration to populate default email templates

from django.db import migrations


def create_default_templates(apps, schema_editor):
    """Create default email templates"""
    EmailTemplate = apps.get_model('students', 'EmailTemplate')
    
    templates = [
        {
            'name': 'Attendance Warning',
            'category': 'attendance',
            'subject_template': 'Attendance Warning - Action Required',
            'body_template': '''Dear {student_name},

This is to inform you that your current attendance percentage is {attendance_percentage}%, which is below the required minimum of {minimum_percentage}%.

Please ensure regular attendance to avoid academic consequences.

If you have any questions or concerns, please contact your academic advisor or the administration office.

Best regards,
{institution_name}
Academic Administration''',
            'variables': ['student_name', 'attendance_percentage', 'minimum_percentage', 'institution_name'],
            'description': 'Warning email for students with low attendance'
        },
        {
            'name': 'Course Update',
            'category': 'course',
            'subject_template': 'Important Course Update - {course_name}',
            'body_template': '''Dear Students,

We have an important update regarding your course: {course_name}

{message}

Please take note of this information and act accordingly. If you have any questions, please contact your course instructor or the academic office.

Course Details:
- Course Code: {course_code}
- Instructor: {instructor_name}
- Department: {department_name}

Best regards,
{institution_name}
Academic Administration''',
            'variables': ['course_name', 'course_code', 'instructor_name', 'department_name', 'message', 'institution_name'],
            'description': 'General course updates and announcements'
        },
        {
            'name': 'Exam Notification',
            'category': 'exam',
            'subject_template': 'Upcoming Exam Notification - {exam_subject}',
            'body_template': '''Dear {student_name},

This is to notify you about the upcoming exam:

Exam Details:
- Subject: {exam_subject}
- Date: {exam_date}
- Time: {exam_time}
- Duration: {exam_duration}
- Venue: {exam_venue}
- Course Code: {course_code}

Important Instructions:
- Please arrive at least 15 minutes before the exam time
- Bring your student ID and required materials
- Late arrivals may not be permitted to take the exam

Please prepare accordingly and contact your instructor if you have any questions.

Best regards,
{institution_name}
Examination Office''',
            'variables': ['student_name', 'exam_subject', 'exam_date', 'exam_time', 'exam_duration', 'exam_venue', 'course_code', 'institution_name'],
            'description': 'Notification about upcoming exams'
        },
        {
            'name': 'General Announcement',
            'category': 'general',
            'subject_template': 'Important Announcement - {announcement_title}',
            'body_template': '''Dear Students,

{message}

This announcement is important for all students. Please read it carefully and take any necessary action.

If you have any questions or need clarification, please contact the administration office during business hours.

Contact Information:
- Email: {contact_email}
- Phone: {contact_phone}
- Office Hours: {office_hours}

Best regards,
{institution_name}
Administration''',
            'variables': ['announcement_title', 'message', 'contact_email', 'contact_phone', 'office_hours', 'institution_name'],
            'description': 'General announcements to students'
        },
        {
            'name': 'Registration Approval',
            'category': 'course',
            'subject_template': 'Course Registration Approved - {course_name}',
            'body_template': '''Dear {student_name},

Good news! Your registration for the following course has been approved:

Course Details:
- Course Name: {course_name}
- Course Code: {course_code}
- Level: {course_level}
- Credits: {course_credits}
- Instructor: {instructor_name}

You can now view this course in your "My Courses" section and attendance will be tracked for this course.

If you have any questions about the course schedule or requirements, please contact your academic advisor.

Best regards,
{institution_name}
Registration Office''',
            'variables': ['student_name', 'course_name', 'course_code', 'course_level', 'course_credits', 'instructor_name', 'institution_name'],
            'description': 'Notification when course registration is approved'
        },
        {
            'name': 'Registration Rejection',
            'category': 'course',
            'subject_template': 'Course Registration Update - {course_name}',
            'body_template': '''Dear {student_name},

We regret to inform you that your registration for the following course could not be approved:

Course Details:
- Course Name: {course_name}
- Course Code: {course_code}
- Level: {course_level}

Reason: {rejection_reason}

If you believe this decision was made in error or if you have questions about alternative options, please contact the registration office or your academic advisor.

You may also consider:
- Registering for alternative courses in your level
- Speaking with your academic advisor about course planning
- Checking for course availability in future semesters

Best regards,
{institution_name}
Registration Office''',
            'variables': ['student_name', 'course_name', 'course_code', 'course_level', 'rejection_reason', 'institution_name'],
            'description': 'Notification when course registration is rejected'
        }
    ]
    
    for template_data in templates:
        EmailTemplate.objects.get_or_create(
            name=template_data['name'],
            category=template_data['category'],
            defaults=template_data
        )


def remove_default_templates(apps, schema_editor):
    """Remove default email templates"""
    EmailTemplate = apps.get_model('students', 'EmailTemplate')
    
    template_names = [
        'Attendance Warning',
        'Course Update', 
        'Exam Notification',
        'General Announcement',
        'Registration Approval',
        'Registration Rejection'
    ]
    
    EmailTemplate.objects.filter(name__in=template_names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0015_add_email_management_models'),
    ]

    operations = [
        migrations.RunPython(create_default_templates, remove_default_templates),
    ]