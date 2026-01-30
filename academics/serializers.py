from rest_framework import serializers
from .models import (
    AcademicYear, Semester, Holiday, Department, Program, Course, CourseOffering
)


class AcademicYearSerializer(serializers.ModelSerializer):
    """Serializer for Academic Year"""
    class Meta:
        model = AcademicYear
        fields = ['id', 'name', 'start_date', 'end_date', 'is_current', 'created_at']
        read_only_fields = ['created_at']


class SemesterSerializer(serializers.ModelSerializer):
    """Serializer for Semester"""
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    name_display = serializers.CharField(source='get_name_display', read_only=True)
    
    class Meta:
        model = Semester
        fields = [
            'id', 'academic_year', 'academic_year_name', 'name', 'name_display',
            'start_date', 'end_date', 'is_current', 'created_at'
        ]
        read_only_fields = ['created_at']


class HolidaySerializer(serializers.ModelSerializer):
    """Serializer for Holiday"""
    academic_year_name = serializers.CharField(source='academic_year.name', read_only=True)
    
    class Meta:
        model = Holiday
        fields = [
            'id', 'academic_year', 'academic_year_name', 'name', 
            'start_date', 'end_date', 'description', 'created_at'
        ]
        read_only_fields = ['created_at']


class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for Department"""
    head_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = [
            'id', 'name', 'code', 'description', 'head_of_department', 
            'head_name', 'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_head_name(self, obj):
        if obj.head_of_department:
            return f"{obj.head_of_department.first_name} {obj.head_of_department.last_name}".strip()
        return ""


class ProgramSerializer(serializers.ModelSerializer):
    """Serializer for Program"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    class Meta:
        model = Program
        fields = [
            'id', 'name', 'code', 'department', 'department_name', 
            'program_type', 'duration_years', 'credit_requirement', 
            'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course"""
    department_name = serializers.CharField(source='department.name', read_only=True)
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    
    class Meta:
        model = Course
        fields = [
            'id', 'code', 'title', 'description', 'department', 'department_name',
            'credit_units', 'level', 'level_display', 'prerequisites', 
            'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']


class CourseOfferingSerializer(serializers.ModelSerializer):
    """Serializer for Course Offering"""
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    semester_name = serializers.CharField(source='semester.get_name_display', read_only=True)
    lecturer_name = serializers.SerializerMethodField()
    enrollment_count = serializers.SerializerMethodField()
    
    class Meta:
        model = CourseOffering
        fields = [
            'id', 'course', 'course_code', 'course_title', 'semester', 'semester_name',
            'lecturer', 'lecturer_name', 'max_enrollment', 'enrollment_count',
            'is_active', 'created_at'
        ]
        read_only_fields = ['created_at']
    
    def get_lecturer_name(self, obj):
        if obj.lecturer:
            return f"{obj.lecturer.first_name} {obj.lecturer.last_name}".strip()
        return ""
    
    def get_enrollment_count(self, obj):
        return obj.get_enrollment_count()
