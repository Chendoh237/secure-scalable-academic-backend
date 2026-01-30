from django.contrib import admin
from .models import AcademicYear, Semester, Holiday, Department, Program, Course, CourseOffering

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current', 'created_at')
    list_filter = ('is_current', 'created_at')
    search_fields = ('name',)
    ordering = ('-start_date',)

@admin.register(Semester)
class SemesterAdmin(admin.ModelAdmin):
    list_display = ('academic_year', 'name', 'start_date', 'end_date', 'is_current')
    list_filter = ('name', 'is_current', 'academic_year')
    search_fields = ('academic_year__name',)
    ordering = ('-start_date',)

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'academic_year', 'start_date', 'end_date')
    list_filter = ('academic_year', 'start_date')
    search_fields = ('name', 'description')
    ordering = ('-start_date',)

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'head_of_department', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department', 'program_type', 'duration_years', 'is_active')
    list_filter = ('program_type', 'department', 'is_active', 'duration_years')
    search_fields = ('name', 'code', 'department__name')
    ordering = ('department', 'name')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'department', 'level', 'credit_units', 'is_active')
    list_filter = ('department', 'level', 'is_active', 'credit_units')
    search_fields = ('code', 'title', 'description')
    ordering = ('department', 'level', 'code')
    filter_horizontal = ('prerequisites',)

@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ('course', 'semester', 'lecturer', 'max_enrollment', 'is_active')
    list_filter = ('semester', 'course__department', 'is_active')
    search_fields = ('course__code', 'course__title', 'lecturer__first_name', 'lecturer__last_name')
    ordering = ('-semester__start_date', 'course__code')
