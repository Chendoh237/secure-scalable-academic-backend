from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import TimetableEntry, Level, TimetableSlot
from academics.models import Course, CourseOffering
from institutions.models import Department

User = get_user_model()

class CourseSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'code', 'title', 'description', 'credit_units', 'department', 'department_name', 'attendance_threshold']

class CourseOfferingSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)

    class Meta:
        model = CourseOffering
        fields = ['id', 'course', 'course_code', 'course_title', 'semester', 'academic_year', 'instructor_name']

class TimetableEntrySerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)
    course_name = serializers.CharField(source='course_offering.course.title', read_only=True)

    class Meta:
        model = TimetableEntry
        fields = ['id', 'course_offering', 'course_code', 'course_name', 'day_of_week', 'start_time', 'end_time', 'room']

class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = ['id', 'name', 'code', 'department', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class TimetableSlotSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source='level.name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    lecturer_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source='timetable.department.name', read_only=True)

    class Meta:
        model = TimetableSlot
        fields = [
            'id', 'timetable', 'level', 'level_name', 'course', 'course_code', 'course_title',
            'lecturer', 'lecturer_name', 'day_of_week',
            'start_time', 'end_time', 'venue', 'created_at', 'updated_at', 'department_name'
        ]

    def get_lecturer_name(self, obj):
        if obj.lecturer:
            return f"{obj.lecturer.first_name} {obj.lecturer.last_name}".strip()
        return ""


class TimetableSlotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetableSlot
        fields = [
            'level', 'course', 'lecturer', 'day_of_week',
            'start_time', 'end_time', 'venue'
        ]

    def validate(self, data):
        start_time = data['start_time']
        end_time = data['end_time']

        if start_time >= end_time:
            raise serializers.ValidationError('Start time must be before end time')

        # Additional validation can be added here
        return data