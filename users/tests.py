from django.test import TestCase

# Create your tests here.
# backend/users/tests.py
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from institutions.models import Institution, Faculty, Department
from students.models import Student

User = get_user_model()

class UserModelTests(TestCase):
    """Test User model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.institution = Institution.objects.create(name="Test University")
        self.faculty = Faculty.objects.create(name="Test Faculty", institution=self.institution)
        self.department = Department.objects.create(name="Test Department", faculty=self.faculty, institution=self.institution)
    
    def test_create_user(self):
        """Test creating a regular user"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('testpass123'))
        self.assertEqual(user.role, 'student')
        self.assertTrue(user.is_approved)
    
    def test_create_admin_user(self):
        """Test creating an admin user"""
        admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            role='admin'
        )
        self.assertEqual(admin.role, 'admin')
        self.assertTrue(admin.is_admin_user())
    
    def test_create_super_user(self):
        """Test creating a super user"""
        super_user = User.objects.create_superuser(
            username='super',
            email='super@example.com',
            password='superpass123'
        )
        self.assertTrue(super_user.is_superuser)
        self.assertTrue(super_user.is_staff)
        self.assertEqual(super_user.role, 'student')  # Default role
    
    def test_user_str_representation(self):
        """Test user string representation"""
        user = User.objects.create_user(
            username='testuser',
            first_name='John',
            last_name='Doe',
            email='test@example.com'
        )
        self.assertEqual(str(user), 'John Doe (Student)')
    
    def test_admin_user_check(self):
        """Test admin user check method"""
        admin = User.objects.create_user(
            username='admin',
            role='admin'
        )
        student = User.objects.create_user(
            username='student',
            role='student'
        )
        self.assertTrue(admin.is_admin_user())
        self.assertFalse(student.is_admin_user())
    
    def test_institution_permissions(self):
        """Test institution permission checks"""
        super_admin = User.objects.create_user(username='super', role='super_admin')
        inst_admin = User.objects.create_user(
            username='inst_admin',
            role='institution_admin',
            institution=self.institution
        )
        dept_admin = User.objects.create_user(
            username='dept_admin',
            role='department_admin',
            department=self.department
        )
        
        # Super admin can manage any institution
        self.assertTrue(super_admin.can_manage_institution(self.institution))
        
        # Institution admin can manage their own institution
        self.assertTrue(inst_admin.can_manage_institution(self.institution))
        
        # Department admin cannot manage institution
        self.assertFalse(dept_admin.can_manage_institution(self.institution))


class AdminLoginAPITests(APITestCase):
    """Test admin login API"""
    
    def setUp(self):
        """Set up test data"""
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            role='admin'
        )
        self.student = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='studentpass123',
            role='student'
        )
    
    def test_admin_login_success(self):
        """Test successful admin login"""
        url = '/api/users/admin/login/'
        data = {
            'username': 'admin',
            'password': 'adminpass123'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('access_token', response.data)
        self.assertIn('refresh_token', response.data)
        self.assertEqual(response.data['user']['role'], 'admin')
    
    def test_admin_login_invalid_credentials(self):
        """Test admin login with invalid credentials"""
        url = '/api/users/admin/login/'
        data = {
            'username': 'admin',
            'password': 'wrongpassword'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])
    
    def test_student_login_blocked(self):
        """Test that students cannot use admin login"""
        url = '/api/users/admin/login/'
        data = {
            'username': 'student',
            'password': 'studentpass123'
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data['success'])
    
    def test_login_missing_credentials(self):
        """Test login with missing credentials"""
        url = '/api/users/admin/login/'
        data = {
            'username': 'admin'
            # Missing password
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(response.data['success'])


class StudentManagementAPITests(APITestCase):
    """Test student management APIs"""
    
    def setUp(self):
        """Set up test data"""
        self.institution = Institution.objects.create(name="Test University")
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            role='admin'
        )
        self.student = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='studentpass123',
            role='student',
            is_approved=False
        )
        # Authenticate admin
        self.client.force_authenticate(user=self.admin)
    
    def test_students_list(self):
        """Test getting students list"""
        url = '/api/users/admin/students/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('students', response.data)
        self.assertIn('pagination', response.data)
    
    def test_approve_student(self):
        """Test approving a student"""
        url = f'/api/users/admin/students/{self.student.id}/approve/'
        data = {'approve': True}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Refresh student from database
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_approved)
    
    def test_reject_student(self):
        """Test rejecting a student"""
        url = f'/api/users/admin/students/{self.student.id}/approve/'
        data = {'approve': False, 'reason': 'Invalid documents'}
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
    
    def test_create_student(self):
        """Test creating a new student"""
        url = '/api/users/admin/students/create/'
        data = {
            'username': 'newstudent',
            'email': 'newstudent@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'Student',
            'matricule': 'MAT001',
            'full_name': 'New Student',
            'auto_approve': True
        }
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Verify student was created
        new_user = User.objects.get(username='newstudent')
        self.assertEqual(new_user.role, 'student')
        self.assertTrue(new_user.is_approved)
    
    def test_unauthorized_access(self):
        """Test that non-admins cannot access student management"""
        # Logout admin
        self.client.force_authenticate(user=None)
        
        url = '/api/users/admin/students/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class DashboardStatsTests(APITestCase):
    """Test dashboard statistics API"""
    
    def setUp(self):
        """Set up test data"""
        self.admin = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            role='admin'
        )
        self.student = User.objects.create_user(
            username='student',
            email='student@example.com',
            password='studentpass123',
            role='student'
        )
        # Authenticate admin
        self.client.force_authenticate(user=self.admin)
    
    def test_dashboard_stats(self):
        """Test getting dashboard statistics"""
        url = '/api/users/admin/dashboard/stats/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertIn('stats', response.data)
        self.assertIn('recent_activities', response.data)
        
        stats = response.data['stats']
        self.assertIn('total_students', stats)
        self.assertIn('total_admins', stats)
        self.assertIn('today_logins', stats)
    
    def test_unauthorized_dashboard_access(self):
        """Test that non-admins cannot access dashboard"""
        # Logout admin and login as student
        self.client.force_authenticate(user=self.student)
        
        url = '/api/users/admin/dashboard/stats/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)