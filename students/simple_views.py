from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from users.models import User
from django.db import transaction
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from students.models import Student
from students.services.face_training import train_face_model
import os
from django.conf import settings
from pathlib import Path

class SimpleRegistrationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            # Handle both form data and JSON data
            if request.content_type.startswith('multipart/form-data'):
                data = request.POST
                face_images = request.FILES.getlist('face_images')
            else:
                data = request.data
                face_images = []

            # Basic validation
            required_fields = ['first_name', 'last_name', 'email', 'matric_number', 'password', 'program', 'faculty', 'department']
            for field in required_fields:
                if not data.get(field):
                    return Response({'error': f'{field} is required'}, status=400)

            # Validate email format
            try:
                validate_email(data['email'])
            except ValidationError:
                return Response({'error': 'Invalid email format'}, status=400)

            # Check for existing user
            if User.objects.filter(email=data['email']).exists():
                return Response({'error': 'Email already registered'}, status=400)

            if User.objects.filter(username=data['matric_number'].lower()).exists():
                return Response({'error': 'Matricule already registered'}, status=400)

            # Convert IDs to integers and validate they are not empty
            program_input = data.get('program', '').strip()
            faculty_input = data.get('faculty', '').strip()
            department_input = data.get('department', '').strip()

            if not program_input or not faculty_input or not department_input:
                return Response({'error': 'Program, faculty, and department are required'}, status=400)

            try:
                program_id = int(program_input)
                faculty_id = int(faculty_input)
                department_id = int(department_input)
            except ValueError:
                return Response({'error': 'Invalid program, faculty, or department ID'}, status=400)

            # Create user within a transaction
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data['matric_number'].lower(),
                    email=data['email'],
                    password=data['password'],
                    first_name=data['first_name'],
                    last_name=data['last_name']
                )

                # Validate that the academic entities exist
                from institutions.program_models import AcademicProgram
                from institutions.models import Faculty, Department

                try:
                    program_obj = AcademicProgram.objects.get(id=program_id)
                    institution_id = program_obj.institution_id
                except AcademicProgram.DoesNotExist:
                    return Response({'error': 'Invalid program selected'}, status=400)

                try:
                    faculty_obj = Faculty.objects.get(id=faculty_id)
                    # Verify that the faculty belongs to the program
                    if faculty_obj.program_id != program_id:
                        return Response({'error': 'Faculty does not belong to the selected program'}, status=400)
                except Faculty.DoesNotExist:
                    return Response({'error': 'Invalid faculty selected'}, status=400)

                try:
                    department_obj = Department.objects.get(id=department_id)
                    # Verify that the department belongs to the faculty
                    if department_obj.faculty_id != faculty_id:
                        return Response({'error': 'Department does not belong to the selected faculty'}, status=400)
                except Department.DoesNotExist:
                    return Response({'error': 'Invalid department selected'}, status=400)

                # Create student record
                student = Student.objects.create(
                    user=user,
                    full_name=f"{data['first_name']} {data['last_name']}",
                    matric_number=data['matric_number'],
                    institution_id=institution_id,
                    program_id=program_id,
                    faculty_id=faculty_id,
                    department_id=department_id,
                    is_active=True,
                    is_approved=True,
                    face_trained=False  # Will be trained after face images are processed
                )

                # Process face images if provided
                if face_images:
                    # Create directory for student photos if it doesn't exist
                    student_photo_dir = os.path.join(settings.MEDIA_ROOT, 'student_photos', student.matric_number)
                    os.makedirs(student_photo_dir, exist_ok=True)

                    # Save uploaded images to student's directory
                    for img_file in face_images:
                        # Validate file type
                        if not img_file.content_type.startswith('image/'):
                            return Response({'error': f'File {img_file.name} is not a valid image'}, status=400)

                        # Save the file
                        file_path = os.path.join(student_photo_dir, img_file.name)
                        with open(file_path, 'wb+') as destination:
                            for chunk in img_file.chunks():
                                destination.write(chunk)

                    # Attempt to train face recognition model with the images
                    try:
                        success, message = train_face_model([student.id])
                        if success:
                            student.face_trained = True
                            student.save()
                    except Exception as e:
                        # Log the error but don't fail the registration
                        print(f"Face training failed for student {student.matric_number}: {str(e)}")

                return Response({'detail': 'Registration successful'}, status=201)

        except Exception as e:
            return Response({'error': str(e)}, status=500)