from rest_framework import serializers
from .models import Institution, Faculty, Department, Program

class InstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = ['id', 'name', 'code', 'address', 'is_active']

class FacultySerializer(serializers.ModelSerializer):
    institution_name = serializers.CharField(source='institution.name', read_only=True)
    
    class Meta:
        model = Faculty
        fields = ['id', 'name', 'code', 'institution', 'institution_name', 'is_active']

class DepartmentSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    institution_name = serializers.CharField(source='faculty.institution.name', read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'faculty', 'faculty_name', 'institution_name', 'is_active']

class ProgramSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    faculty_name = serializers.CharField(source='department.faculty.name', read_only=True)
    
    class Meta:
        model = Program
        fields = ['id', 'name', 'code', 'degree', 'duration', 'department', 'department_name', 'faculty_name', 'is_active']