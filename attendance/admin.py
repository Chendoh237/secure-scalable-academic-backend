from django.contrib import admin
from .models import Attendance, Timetable

# Unregister any existing registrations to avoid conflicts
for model in [Attendance, Timetable]:
    try:
        admin.site.unregister(model)
    except admin.sites.NotRegistered:
        pass

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = [
        'student_matric_number', 
        'course_code', 
        'date', 
        'status', 
        'presence_percentage_display',
        'presence_duration_display',
        'detection_count',
        'is_manual_override',
        'is_locked'
    ]
    list_filter = [
        'status', 
        'date', 
        'is_manual_override', 
        'is_locked',
        'course_registration__course'
    ]
    search_fields = [
        'student__matric_number', 
        'student__user__first_name', 
        'student__user__last_name',
        'course_registration__course__code'
    ]
    readonly_fields = [
        'recorded_at', 
        'updated_at',
        'presence_percentage_display',
        'presence_duration_display',
        'total_class_duration_display',
        'presence_summary_display'
    ]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('student', 'course_registration', 'timetable_entry', 'date', 'status')
        }),
        ('Presence Tracking', {
            'fields': (
                'presence_duration', 
                'total_class_duration', 
                'presence_percentage',
                'presence_percentage_display',
                'presence_duration_display',
                'total_class_duration_display'
            ),
            'classes': ('collapse',)
        }),
        ('Detection Data', {
            'fields': (
                'first_detected_at',
                'last_detected_at', 
                'detection_count'
            ),
            'classes': ('collapse',)
        }),
        ('System Fields', {
            'fields': (
                'is_manual_override', 
                'is_locked', 
                'recorded_at', 
                'updated_at',
                'presence_summary_display'
            ),
            'classes': ('collapse',)
        }),
    )
    
    def student_matric_number(self, obj):
        return obj.student.matric_number
    student_matric_number.short_description = 'Matric Number'
    student_matric_number.admin_order_field = 'student__matric_number'
    
    def course_code(self, obj):
        return obj.course_registration.course.code
    course_code.short_description = 'Course'
    course_code.admin_order_field = 'course_registration__course__code'
    
    def presence_percentage_display(self, obj):
        if obj.presence_percentage is not None:
            return f"{obj.presence_percentage:.1f}%"
        return "Not calculated"
    presence_percentage_display.short_description = 'Presence %'
    
    def presence_duration_display(self, obj):
        if obj.presence_duration:
            total_seconds = obj.presence_duration.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        return "No data"
    presence_duration_display.short_description = 'Present Duration'
    
    def total_class_duration_display(self, obj):
        if obj.total_class_duration:
            total_seconds = obj.total_class_duration.total_seconds()
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            if hours > 0:
                return f"{hours}h {minutes}m"
            return f"{minutes}m"
        return "No data"
    total_class_duration_display.short_description = 'Class Duration'
    
    def presence_summary_display(self, obj):
        try:
            summary = obj.get_presence_summary()
            return f"""
            Presence: {summary['presence_duration_minutes']:.1f} min / {summary['total_class_duration_minutes']:.1f} min
            Percentage: {summary['presence_percentage']:.1f}%
            Detections: {summary['detection_count']}
            Status: {summary['status']}
            Manual Override: {summary['is_manual_override']}
            """
        except Exception as e:
            return f"Error: {str(e)}"
    presence_summary_display.short_description = 'Presence Summary'

@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ['course', 'day', 'start_time', 'end_time', 'level', 'department']
    list_filter = ['day', 'department', 'level']
    search_fields = ['course__code', 'course__title']
