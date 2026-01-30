from django.contrib import admin, messages
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import redirect
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import Student, PreApprovedStudent, StudentPhoto, StudentLevelSelection, StudentCourseSelection, CourseSelectionAuditLog
from students.services.face_training import train_face_model
from students.services.audit_service import CourseSelectionAuditService

User = get_user_model()

@admin.register(PreApprovedStudent)
class PreApprovedStudentAdmin(admin.ModelAdmin):
    list_display = ('matric_number', 'institution', 'program', 'is_used')
    search_fields = ('matric_number',)
    list_filter = ('institution', 'is_used')
    actions = ['mark_as_unused']
    
    def mark_as_unused(self, request, queryset):
        updated = queryset.update(is_used=False)
        self.message_user(
            request,
            f"Marked {updated} pre-approved student(s) as unused.",
            messages.SUCCESS
        )
    mark_as_unused.short_description = "Mark selected as unused"

@admin.register(StudentPhoto)
class StudentPhotoAdmin(admin.ModelAdmin):
    list_display = ('student', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('student__matric_number', 'student__full_name')
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 200px;" />', obj.image.url)
        return "No image"
    image_preview.short_description = 'Preview'

class StudentPhotoInline(admin.TabularInline):
    model = StudentPhoto
    extra = 5
    readonly_fields = ('image_preview',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 60px; height: 60px; object-fit: cover;" />', obj.image.url)
        return "No image"
    image_preview.short_description = 'Preview'
    
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ("matric_number", "full_name", "photo_count", "is_approved", "face_trained", "actions_column")
    list_filter = ("is_approved", "face_trained", "institution", "faculty", "department")
    search_fields = ("matric_number", "full_name", "user__email")
    readonly_fields = ("created_at", "face_trained", "approval_status", "photo_preview")
    exclude = ("user",)  # Hide user field from admin form
    actions = ["approve_students", "train_faces_action"]
    inlines = [StudentPhotoInline]
    
    def save_model(self, request, obj, form, change):
        if not change:  # Creating new student
            # Generate unique username from matricule
            username = obj.matric_number.lower()
            email = f"{username}@student.edu"
            
            # Check if user already exists, if so, use it
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                # Create new user
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password='temp123',
                    first_name=obj.full_name.split()[0] if obj.full_name else '',
                    last_name=' '.join(obj.full_name.split()[1:]) if len(obj.full_name.split()) > 1 else ''
                )
            obj.user = user
        super().save_model(request, obj, form, change)
    
    def photo_count(self, obj):
        count = obj.photos.count()
        if count >= 5:
            return format_html('<span style="color: green; font-weight: bold;">{} photos</span>', count)
        else:
            return format_html('<span style="color: red; font-weight: bold;">{} photos (need {})</span>', count, 5-count)
    photo_count.short_description = 'Face Photos'
    
    def photo_preview(self, obj):
        photos = obj.photos.all()[:6]  # Show first 6 photos
        if photos:
            html = '<div style="display: flex; gap: 10px; flex-wrap: wrap;">'  
            for photo in photos:
                html += f'<img src="{photo.image.url}" style="width: 80px; height: 80px; object-fit: cover; border-radius: 8px; border: 2px solid #ddd;" />'
            if obj.photos.count() > 6:
                html += f'<div style="display: flex; align-items: center; padding: 10px; background: #f0f0f0; border-radius: 8px; font-weight: bold;">+{obj.photos.count() - 6} more</div>'
            html += '</div>'
            return format_html(html)
        return "No photos uploaded"
    photo_preview.short_description = 'Photo Preview'
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:student_id>/approve/',
                self.admin_site.admin_view(self.approve_student),
                name='approve_student',
            ),
            path(
                '<int:student_id>/train-face/',
                self.admin_site.admin_view(self.train_student_face),
                name='train_student_face',
            ),
        ]
        return custom_urls + urls
    
    def actions_column(self, obj):
        actions = []
        if not obj.is_approved:
            if obj.photos.count() >= 5:
                approve_url = reverse('admin:approve_student', args=[obj.id])
                actions.append(f'<a class="button" href="{approve_url}" style="background: #28a745; color: white;">Approve</a>')
            else:
                actions.append('<span style="color: #dc3545; font-weight: bold;">Need 5+ photos</span>')
        elif not obj.face_trained:
            train_url = reverse('admin:train_student_face', args=[obj.id])
            actions.append(f'<a class="button" href="{train_url}" style="background: #007bff; color: white;">Train Face</a>')
        else:
            actions.append('<span style="color: #28a745; font-weight: bold;">✓ Complete</span>')
        
        return format_html(' '.join(actions))
    actions_column.short_description = 'Actions'
    
    def approve_student(self, request, student_id):
        student = Student.objects.get(id=student_id)
        if student.photos.count() < 5:
            self.message_user(
                request,
                f"Cannot approve {student.full_name}. Student needs at least 5 face photos (currently has {student.photos.count()}).",
                messages.ERROR
            )
        else:
            student.is_approved = True
            student.save()
            self.message_user(
                request,
                f"Successfully approved {student.full_name} with {student.photos.count()} face photos.",
                messages.SUCCESS
            )
        return redirect('admin:students_student_changelist')
    
    def train_student_face(self, request, student_id):
        success, message = train_face_model(student_ids=[student_id])
        if success:
            self.message_user(request, message, messages.SUCCESS)
        else:
            self.message_user(request, f"Training failed: {message}", messages.ERROR)
        return redirect('admin:students_student_changelist')
    
    def approve_students(self, request, queryset):
        approved_count = 0
        insufficient_photos = []
        
        for student in queryset:
            if student.photos.count() >= 5:
                student.is_approved = True
                student.save()
                approved_count += 1
            else:
                insufficient_photos.append(f"{student.full_name} ({student.photos.count()} photos)")
        
        if approved_count > 0:
            self.message_user(
                request, 
                f"Successfully approved {approved_count} student(s).",
                messages.SUCCESS
            )
        
        if insufficient_photos:
            self.message_user(
                request,
                f"Could not approve {len(insufficient_photos)} student(s) - insufficient photos: {', '.join(insufficient_photos[:3])}{'...' if len(insufficient_photos) > 3 else ''}",
                messages.WARNING
            )
    approve_students.short_description = "Approve selected students (with 5+ photos)"
    
    def train_faces_action(self, request, queryset):
        # Only train approved students
        students = queryset.filter(is_approved=True)
        student_count = students.count()
        
        if student_count == 0:
            self.message_user(
                request,
                "No approved students selected for training.",
                messages.WARNING
            )
            return
            
        student_ids = list(students.values_list('id', flat=True))
        success, message = train_face_model(student_ids=student_ids)
        
        if success:
            self.message_user(request, message, messages.SUCCESS)
        else:
            self.message_user(request, f"Training failed: {message}", messages.ERROR)
    
    train_faces_action.short_description = "Train face recognition for selected approved students"
    
    def approval_status(self, obj):
        if obj.is_approved:
            if obj.face_trained:
                return "Approved & Trained"
            return "Approved - Pending Training"
        return "Pending Approval"
    approval_status.short_description = "Status"


@admin.register(StudentLevelSelection)
class StudentLevelSelectionAdmin(admin.ModelAdmin):
    list_display = ('student', 'level', 'selected_at', 'updated_at')
    list_filter = ('level', 'selected_at', 'updated_at')
    search_fields = ('student__matric_number', 'student__full_name', 'level__name')
    readonly_fields = ('selected_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student', 'level')


@admin.register(StudentCourseSelection)
class StudentCourseSelectionAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'level', 'is_offered', 'updated_at')
    list_filter = ('is_offered', 'level', 'department', 'updated_at')
    search_fields = ('student__matric_number', 'student__full_name', 'course__code', 'course__title')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student', 'course', 'level', 'department')


@admin.register(CourseSelectionAuditLog)
class CourseSelectionAuditLogAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'action', 'change_summary_short', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp', 'department', 'level')
    search_fields = ('student__matric_number', 'student__full_name', 'course__code', 'course__title', 'ip_address')
    readonly_fields = ('timestamp', 'change_summary', 'batch_id')
    date_hierarchy = 'timestamp'
    ordering = ('-timestamp',)
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('student', 'course', 'level', 'department', 'action', 'timestamp')
        }),
        ('Change Details', {
            'fields': ('old_is_offered', 'new_is_offered', 'change_summary', 'change_reason')
        }),
        ('Request Context', {
            'fields': ('ip_address', 'user_agent', 'session_key'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('batch_id',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student', 'course', 'level', 'department')
    
    def change_summary_short(self, obj):
        """Shortened version of change summary for list display"""
        summary = obj.change_summary
        if len(summary) > 50:
            return summary[:47] + "..."
        return summary
    change_summary_short.short_description = 'Change Summary'
    
    def has_add_permission(self, request):
        """Prevent manual creation of audit logs"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Prevent modification of audit logs"""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of individual audit logs"""
        return False
    
    actions = ['export_audit_logs']
    
    def export_audit_logs(self, request, queryset):
        """Export selected audit logs to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="course_selection_audit_logs.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Student Matric', 'Student Name', 'Course Code', 'Course Title',
            'Level', 'Department', 'Action', 'Old Status', 'New Status',
            'Change Summary', 'Timestamp', 'IP Address', 'Change Reason'
        ])
        
        for log in queryset.select_related('student', 'course', 'level', 'department'):
            writer.writerow([
                log.student.matric_number,
                log.student.full_name,
                log.course.code,
                log.course.title,
                log.level.name,
                log.department.name,
                log.action,
                'Offered' if log.old_is_offered else 'Not Offered' if log.old_is_offered is not None else 'N/A',
                'Offered' if log.new_is_offered else 'Not Offered',
                log.change_summary,
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                log.ip_address or 'N/A',
                log.change_reason
            ])
        
        return response
    export_audit_logs.short_description = "Export selected audit logs to CSV"


# Custom admin views for audit trail analysis
class AuditTrailAnalysisAdmin(admin.ModelAdmin):
    """
    Custom admin interface for audit trail analysis and reporting
    """
    change_list_template = 'admin/students/audit_analysis.html'
    
    def changelist_view(self, request, extra_context=None):
        # Get audit statistics
        total_logs = CourseSelectionAuditLog.objects.count()
        
        # Recent activity (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_logs = CourseSelectionAuditLog.objects.filter(timestamp__gte=week_ago)
        
        # Action counts
        action_stats = CourseSelectionAuditLog.objects.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Most active students (last 30 days)
        month_ago = timezone.now() - timedelta(days=30)
        active_students = CourseSelectionAuditLog.objects.filter(
            timestamp__gte=month_ago
        ).values(
            'student__matric_number', 'student__full_name'
        ).annotate(
            change_count=Count('id')
        ).order_by('-change_count')[:10]
        
        # Most modified courses (last 30 days)
        active_courses = CourseSelectionAuditLog.objects.filter(
            timestamp__gte=month_ago
        ).values(
            'course__code', 'course__title'
        ).annotate(
            change_count=Count('id')
        ).order_by('-change_count')[:10]
        
        # Department activity
        dept_activity = CourseSelectionAuditLog.objects.values(
            'department__name'
        ).annotate(
            change_count=Count('id')
        ).order_by('-change_count')
        
        extra_context = extra_context or {}
        extra_context.update({
            'total_logs': total_logs,
            'recent_logs_count': recent_logs.count(),
            'action_stats': action_stats,
            'active_students': active_students,
            'active_courses': active_courses,
            'dept_activity': dept_activity,
        })
        
        return super().changelist_view(request, extra_context=extra_context)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


# Register the analysis admin (this creates a separate menu item)
# Note: CourseSelectionAuditLog is already registered with @admin.register decorator above
