from django.contrib import admin
from .models import Level, CourseRegistration, Timetable, TimetableSlot, ClassSession, TimetableEntry

@admin.register(Level)
class LevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department', 'is_active', 'created_at')
    list_filter = ('department', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'department__name')
    ordering = ('department', 'code')

@admin.register(CourseRegistration)
class CourseRegistrationAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'semester', 'status', 'registered_at', 'approved_by')
    list_filter = ('status', 'semester', 'course__department', 'registered_at')
    search_fields = ('student__matric_number', 'student__user__first_name', 'student__user__last_name', 'course__code', 'course__title')
    ordering = ('-registered_at',)
    readonly_fields = ('registered_at', 'approved_at')
    
    fieldsets = (
        ('Registration Info', {
            'fields': ('student', 'course', 'semester', 'status')
        }),
        ('Approval', {
            'fields': ('approved_by', 'approved_at', 'rejection_reason')
        }),
        ('Academic', {
            'fields': ('grade', 'grade_points', 'is_retake')
        }),
    )

@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'level', 'semester', 'is_active', 'is_published', 'created_at')
    list_filter = ('department', 'level', 'semester', 'is_active', 'is_published', 'created_at')
    search_fields = ('name', 'department__name', 'level__name')
    ordering = ('-created_at',)

@admin.register(TimetableSlot)
class TimetableSlotAdmin(admin.ModelAdmin):
    list_display = ('course', 'day_of_week', 'start_time', 'end_time', 'venue', 'lecturer', 'session_type')
    list_filter = ('day_of_week', 'session_type', 'timetable__department', 'timetable__level')
    search_fields = ('course__code', 'course__title', 'venue', 'lecturer__first_name', 'lecturer__last_name')
    ordering = ('day_of_week', 'start_time')

@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('timetable_slot', 'date', 'state', 'managed_by', 'opened_at', 'closed_at')
    list_filter = ('state', 'date', 'timetable_slot__timetable__department')
    search_fields = ('timetable_slot__course__code', 'timetable_slot__course__title', 'managed_by__first_name', 'managed_by__last_name')
    ordering = ('-date', 'timetable_slot__start_time')
    readonly_fields = ('opened_at', 'activated_at', 'closed_at')

@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('course', 'day_of_week', 'start_time', 'end_time', 'venue', 'created_at')
    list_filter = ('day_of_week', 'course__department', 'created_at')
    search_fields = ('course__code', 'course__title', 'venue')
    ordering = ('day_of_week', 'start_time')
