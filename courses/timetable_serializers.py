from rest_framework import serializers
from .models import Level, Lecturer, DepartmentTimetable, TimetableSlot
from django.contrib.auth import get_user_model
from institutions.models import Department
from courses.models import Course

User = get_user_model()


class LevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Level
        fields = ['id', 'name', 'code', 'department', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class LecturerSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Lecturer
        fields = ['id', 'user', 'employee_id', 'department', 'specialization', 'created_at', 'updated_at']
    
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Include user details directly in the representation
        data['first_name'] = instance.user.first_name
        data['last_name'] = instance.user.last_name
        data['email'] = instance.user.email
        data['full_name'] = f"{instance.user.first_name} {instance.user.last_name}".strip()
        return data


class DepartmentTimetableSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepartmentTimetable
        fields = ['id', 'department', 'name', 'description', 'is_active', 'created_at', 'updated_at']


class TimetableSlotSerializer(serializers.ModelSerializer):
    level_name = serializers.CharField(source='level.name', read_only=True)
    course_code = serializers.CharField(source='course.code', read_only=True)
    course_title = serializers.CharField(source='course.title', read_only=True)
    lecturer_name = serializers.SerializerMethodField()
    lecturer_employee_id = serializers.CharField(source='lecturer.employee_id', read_only=True)
    department_name = serializers.CharField(source='timetable.department.name', read_only=True)

    class Meta:
        model = TimetableSlot
        fields = [
            'id', 'timetable', 'level', 'level_name', 'course', 'course_code', 'course_title',
            'lecturer', 'lecturer_name', 'lecturer_employee_id', 'day_of_week', 
            'start_time', 'end_time', 'venue', 'created_at', 'updated_at', 'department_name'
        ]

    def get_lecturer_name(self, obj):
        return f"{obj.lecturer.user.first_name} {obj.lecturer.user.last_name}".strip()


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