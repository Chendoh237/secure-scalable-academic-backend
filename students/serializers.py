# In students/serializers.py
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from pathlib import Path
from .models import Student, PreApprovedStudent, StudentPhoto
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram
from courses.models import Course, CourseRegistration 

User = get_user_model()
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff']
        read_only_fields = ['id', 'is_staff']

class StudentRegistrationSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField()
    last_name = serializers.CharField()
    matric_number = serializers.CharField()
    email = serializers.EmailField(required=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    program = serializers.IntegerField()  # Program ID
    faculty = serializers.IntegerField()  # Faculty ID
    department = serializers.IntegerField()  # Department ID
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)
    photos = serializers.ListField(
        child=serializers.ImageField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Student
        fields = [
            'first_name',
            'last_name',
            'matric_number',
            'email',
            'phone',
            'program',
            'faculty',
            'department',
            'password',
            'confirm_password',
            'photos',
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'confirm_password': {'write_only': True},
        }


    def validate(self, data):
        # Check password match
        if data['password'] != data.pop('confirm_password'):
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})

        # Convert string IDs to integers
        try:
            program_id = int(data['program'])
            faculty_id = int(data['faculty']) 
            department_id = int(data['department'])
        except (ValueError, TypeError):
            raise serializers.ValidationError("Invalid program, faculty, or department selection.")

        # Validate program, faculty, department hierarchy
        try:
            program = AcademicProgram.objects.get(id=program_id)
            faculty = Faculty.objects.get(id=faculty_id, program=program)
            department = Department.objects.get(id=department_id, faculty=faculty)
            
            data['program_obj'] = program
            data['faculty_obj'] = faculty
            data['department_obj'] = department
        except (AcademicProgram.DoesNotExist, Faculty.DoesNotExist, Department.DoesNotExist):
            raise serializers.ValidationError("Invalid program, faculty, or department selection.")

        # Image count validation (optional for now)
        photos = data.get('photos', [])
        if photos and (len(photos) < 5 or len(photos) > 12):
            raise serializers.ValidationError(
                {"photos": "Please provide between 5 and 12 images."}
            )

        return data

    def create(self, validated_data):
        # Get the validated objects
        program_obj = validated_data.pop('program_obj')
        faculty_obj = validated_data.pop('faculty_obj')
        department_obj = validated_data.pop('department_obj')
        
        # Combine first and last name
        full_name = f"{validated_data['first_name']} {validated_data['last_name']}"
        
        # Check for existing user
        if User.objects.filter(email=validated_data['email']).exists():
            raise serializers.ValidationError({"email": "Email already registered"})
        if User.objects.filter(username=validated_data['matric_number'].lower()).exists():
            raise serializers.ValidationError({"matric_number": "Matricule already registered"})
    
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=validated_data['matric_number'].lower(),
                email=validated_data['email'],
                password=validated_data['password'],
                first_name=validated_data['first_name'],
                last_name=validated_data['last_name'],
            )
            
            # Get institution from program
            institution = program_obj.institution
            
            # Create student using Django ORM
            student = Student.objects.create(
                user=user,
                full_name=full_name,
                matric_number=validated_data['matric_number'],
                institution=institution,
                faculty=faculty_obj,
                department=department_obj,
                program=program_obj,
                is_active=True,
                face_trained=False,
                is_approved=True
            )
        
            # Handle photos
            for photo in validated_data.get('photos', []):
                StudentPhoto.objects.create(student=student, image=photo)
        
        return student


class StudentLoginSerializer(serializers.Serializer):
    matricule = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        matricule = data.get('matricule')
        password = data.get('password')

        # Try to find the user by matricule (username)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            user = User.objects.get(username=matricule.lower())
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid credentials")

        # Authenticate the user
        from django.contrib.auth import authenticate
        student = authenticate(username=user.username, password=password)

        if not student:
            raise serializers.ValidationError("Invalid credentials")

        if not student.is_active:
            raise serializers.ValidationError("Account is disabled")

        # Generate JWT tokens
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(student)
        
        return {
            'user': student,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'student_id': student.student_profile.id if hasattr(student, 'student_profile') else None
        }

        
class StudentProfileSerializer(serializers.Serializer):
    full_name = serializers.CharField()
    matricule = serializers.CharField()
    program = serializers.CharField()
    role = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()

    def get_role(self, obj):
        return "Student"

    def get_initials(self, obj):
        parts = obj.full_name.split()
        return "".join(p[0].upper() for p in parts[:2])
    
class StudentDashboardOverviewSerializer(serializers.Serializer):
    class Meta:
        model = Student
        fields = [
            'id',
            'full_name',
            'email',
            'matricule',
            'department',
        ]

class StudentSerializer(serializers.ModelSerializer):
    """
    Serializer for the Student model.
    """
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    
    class Meta:
        model = Student
        fields = [
            'id',
            'matric_number',
            'full_name',
            'email',
            'program',
            'department',
            'is_active',
            'date_joined',
            'face_trained',
        ]
        read_only_fields = ['id', 'matric_number', 'face_trained']

class StudentPhotoSerializer(serializers.ModelSerializer):
    """
    Serializer for the StudentPhoto model.
    """
    image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentPhoto
        fields = ['id', 'image', 'image_url', 'uploaded_at']
        read_only_fields = ['id', 'uploaded_at']
    
    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

class CourseRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer for course registrations.
    """
    course_code = serializers.CharField(source='course_offering.course.code', read_only=True)
    course_title = serializers.CharField(source='course_offering.course.title', read_only=True)
    credits = serializers.IntegerField(source='course_offering.course.credit_units', read_only=True)
    semester = serializers.SerializerMethodField()
    instructor = serializers.SerializerMethodField()
    
    class Meta:
        model = CourseRegistration
        fields = [
            'id',
            'course_code',
            'course_title',
            'credits',
            'semester',
            'instructor',
            'enrollment_date',
            'is_active',
        ]
        read_only_fields = ['id', 'enrollment_date']
    
    def get_semester(self, obj):
        return f"{obj.course_offering.get_semester_display()}"
    
    def get_instructor(self, obj):
        return obj.course_offering.instructor_name

class AvailableCourseSerializer(serializers.ModelSerializer):
    """
    Serializer for available courses.
    """
    instructor = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()
    available_slots = serializers.SerializerMethodField()
    prerequisites = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id',
            'code',
            'title',
            'description',
            'credit_units',
            'instructor',
            'schedule',
            'available_slots',
            'prerequisites',
        ]
    
    def get_instructor(self, obj):
        offering = getattr(self.context.get('request'), 'offering', None)
        if offering and offering.instructor:
            return f"{offering.instructor.get_full_name()}"
        return "Not Assigned"
    
    def get_schedule(self, obj):
        offering = getattr(self.context.get('request'), 'offering', None)
        if offering:
            return f"{offering.day} {offering.start_time}-{offering.end_time}"
        return "Schedule not available"
    
    def get_available_slots(self, obj):
        offering = getattr(self.context.get('request'), 'offering', None)
        if offering:
            return offering.capacity - offering.current_enrollment
        return 0
    
    def get_prerequisites(self, obj):
        return [{"code": p.code} for p in obj.prerequisites.all()]
