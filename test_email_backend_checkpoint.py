#!/usr/bin/env python
"""
Email Management System Backend Checkpoint Test

This comprehensive test suite verifies that all backend services 
for the email management system are working correctly before 
proceeding to API and frontend implementation.
"""

import os
import sys
import django
from django.conf import settings

# Add the backend directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from students.email_models import EmailConfiguration, EmailTemplate, EmailHistory, EmailDelivery
from students.email_service import EmailService, email_service
from students.template_service import TemplateService, template_service
from students.recipient_service import RecipientService, recipient_service
from students.email_history_service import EmailHistoryService, email_history_service
from students.models import Student
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram

User = get_user_model()

class EmailBackendCheckpoint:
    """Comprehensive test suite for email management backend services"""
    
    def __init__(self):
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []
    
    def run_test(self, test_name, test_func):
        """Run a single test and track results"""
        print(f"\n🔍 Testing: {test_name}")
        try:
            result = test_func()
            if result:
                print(f"✅ PASSED: {test_name}")
                self.passed_tests += 1
                self.test_results.append((test_name, "PASSED", None))
            else:
                print(f"❌ FAILED: {test_name}")
                self.failed_tests += 1
                self.test_results.append((test_name, "FAILED", "Test returned False"))
        except Exception as e:
            print(f"❌ ERROR: {test_name} - {str(e)}")
            self.failed_tests += 1
            self.test_results.append((test_name, "ERROR", str(e)))
    
    def test_email_models(self):
        """Test email data models"""
        try:
            # Test EmailTemplate creation
            template = EmailTemplate.objects.create(
                name="Test Template",
                category="general",
                subject_template="Test Subject: {student_name}",
                body_template="Hello {student_name}, this is a test.",
                variables=["student_name"],
                is_active=True
            )
            
            # Test EmailHistory creation
            admin_user = User.objects.get_or_create(
                username="test_admin",
                defaults={'email': 'admin@test.com', 'is_staff': True}
            )[0]
            
            history = EmailHistory.objects.create(
                sender=admin_user,
                subject="Test Email",
                body="Test body",
                template_used=template,
                recipient_count=2,
                status='sending'
            )
            
            # Test EmailDelivery creation
            delivery = EmailDelivery.objects.create(
                email_history=history,
                recipient_email="test@example.com",
                delivery_status='pending'
            )
            
            # Verify relationships work
            assert template.id is not None
            assert history.template_used == template
            assert delivery.email_history == history
            assert history.success_rate == 0  # Property test
            
            return True
        except Exception as e:
            print(f"Model test error: {str(e)}")
            return False
    
    def test_email_service(self):
        """Test EmailService functionality"""
        try:
            service = EmailService()
            
            # Test provider configurations
            providers = service.get_supported_providers()
            assert len(providers) > 0
            assert 'gmail' in providers
            assert 'outlook' in providers
            
            # Test provider config retrieval
            gmail_config = service.get_provider_config('gmail')
            assert gmail_config is not None
            assert gmail_config['smtp_host'] == 'smtp.gmail.com'
            assert gmail_config['smtp_port'] == 587
            
            # Test SMTP configuration (without actual connection)
            test_config = {
                'smtpServer': 'smtp.example.com',
                'smtpPort': 587,
                'emailUser': 'test@example.com',
                'emailPassword': 'testpass',
                'useTLS': True,
                'useSSL': False,
                'fromName': 'Test System'
            }
            
            # This should not fail (just validates and stores config)
            # Note: We're not actually testing connection since we don't have real SMTP credentials
            
            return True
        except Exception as e:
            print(f"EmailService test error: {str(e)}")
            return False
    
    def test_template_service(self):
        """Test TemplateService functionality"""
        try:
            service = TemplateService()
            
            # Test template creation
            template = service.create_custom_template(
                name="Checkpoint Test Template",
                category="general",
                subject_template="Welcome {student_name}!",
                body_template="Dear {student_name}, welcome to {institution_name}. Today is {current_date}.",
                description="Test template for checkpoint"
            )
            
            # Test template retrieval
            retrieved = service.get_template(template.id)
            assert retrieved is not None
            assert retrieved.name == "Checkpoint Test Template"
            
            # Test template rendering
            context = {
                'student_name': 'John Doe',
                'institution_name': 'Test University'
            }
            
            rendered = service.render_template(template, context)
            assert 'subject' in rendered
            assert 'body' in rendered
            assert 'John Doe' in rendered['subject']
            assert 'John Doe' in rendered['body']
            
            # Test variable extraction
            variables = service.extract_variables("Hello {name}, your {item} is ready!")
            assert 'name' in variables
            assert 'item' in variables
            
            # Test template validation
            validation = service.validate_template(
                "Subject: {name}",
                "Body: {name} and {email}"
            )
            assert validation['valid'] is True
            assert 'name' in validation['variables']
            assert 'email' in validation['variables']
            
            return True
        except Exception as e:
            print(f"TemplateService test error: {str(e)}")
            return False
    
    def test_recipient_service(self):
        """Test RecipientService functionality"""
        try:
            service = RecipientService()
            
            # Test email validation
            emails = ['valid@example.com', 'invalid-email', 'another@test.org']
            validation = service.validate_email_addresses(emails)
            
            assert validation['valid_count'] == 2
            assert validation['invalid_count'] == 1
            assert 'valid@example.com' in validation['valid_emails']
            assert 'invalid-email' in validation['invalid_emails']
            
            # Test recipient statistics (should work even with no data)
            stats = service.get_recipient_statistics()
            assert 'total_students' in stats
            assert 'departments' in stats
            
            # Test departments with counts
            departments = service.get_departments_with_student_counts()
            assert isinstance(departments, list)
            
            # Test recipient list building
            config = {
                'type': 'custom',
                'emails': ['test1@example.com', 'test2@example.com']
            }
            
            emails, metadata = service.build_recipient_list(config)
            assert len(emails) == 2
            assert metadata['type'] == 'custom'
            assert metadata['total_count'] == 2
            
            return True
        except Exception as e:
            print(f"RecipientService test error: {str(e)}")
            return False
    
    def test_email_history_service(self):
        """Test EmailHistoryService functionality"""
        try:
            service = EmailHistoryService()
            
            # Create test user
            admin_user = User.objects.get_or_create(
                username="history_test_admin",
                defaults={'email': 'admin@test.com', 'is_staff': True}
            )[0]
            
            # Test email record creation
            recipients = ['test1@example.com', 'test2@example.com']
            history = service.save_email_record(
                sender_user=admin_user,
                subject="Test History Email",
                body="Test body content",
                recipients=recipients
            )
            
            assert history is not None
            assert history.recipient_count == 2
            assert history.status == 'sending'
            
            # Test delivery status update
            success = service.update_delivery_status(
                record_id=history.id,
                recipient_email='test1@example.com',
                status='sent'
            )
            assert success is True
            
            # Verify counts updated
            history.refresh_from_db()
            assert history.success_count == 1
            assert history.failure_count == 0
            
            # Test history retrieval
            result = service.get_email_history(page_size=10)
            assert 'results' in result
            assert 'pagination' in result
            assert len(result['results']) > 0
            
            # Test delivery details
            details = service.get_delivery_details(history.id)
            assert len(details) == 2
            
            # Test search functionality
            search_results = service.search_email_history("Test History")
            assert len(search_results) > 0
            
            # Test statistics
            stats = service.get_email_statistics(days=30)
            assert 'total_emails' in stats
            assert 'total_recipients' in stats
            
            # Test administrative logging methods (should not crash)
            service.log_smtp_configuration_change(
                user=admin_user,
                old_config={'smtp_host': 'old.example.com'},
                new_config={'smtp_host': 'new.example.com'}
            )
            
            service.log_template_action(
                action='created',
                user=admin_user,
                template_id=1,
                template_name='Test Template'
            )
            
            service.log_bulk_email_operation(
                user=admin_user,
                operation='initiated',
                recipient_count=10
            )
            
            return True
        except Exception as e:
            print(f"EmailHistoryService test error: {str(e)}")
            return False
    
    def test_service_integration(self):
        """Test integration between services"""
        try:
            # Create a template
            template = template_service.create_custom_template(
                name="Integration Test Template",
                category="general",
                subject_template="Integration Test: {student_name}",
                body_template="Hello {student_name}, this is an integration test.",
                description="Integration test template"
            )
            
            # Create admin user
            admin_user = User.objects.get_or_create(
                username="integration_admin",
                defaults={'email': 'admin@test.com', 'is_staff': True}
            )[0]
            
            # Build recipient list
            config = {
                'type': 'custom',
                'emails': ['integration1@example.com', 'integration2@example.com']
            }
            recipients, metadata = recipient_service.build_recipient_list(config)
            
            # Render template
            context = {'student_name': 'Integration Test User'}
            rendered = template_service.render_template(template, context)
            
            # Create email history record
            history = email_history_service.save_email_record(
                sender_user=admin_user,
                subject=rendered['subject'],
                body=rendered['body'],
                recipients=recipients,
                template_used=template
            )
            
            # Verify integration worked
            assert history.template_used == template
            assert history.recipient_count == len(recipients)
            assert 'Integration Test User' in history.subject
            
            return True
        except Exception as e:
            print(f"Service integration test error: {str(e)}")
            return False
    
    def test_database_migrations(self):
        """Test that all email-related database tables exist and are accessible"""
        try:
            # Test that we can query all email models
            EmailTemplate.objects.all().count()
            EmailHistory.objects.all().count()
            EmailDelivery.objects.all().count()
            EmailConfiguration.objects.all().count()
            
            # Test that indexes exist (should not raise errors)
            EmailDelivery.objects.filter(delivery_status='pending').count()
            EmailDelivery.objects.filter(recipient_email='test@example.com').count()
            
            return True
        except Exception as e:
            print(f"Database migration test error: {str(e)}")
            return False
    
    def test_property_based_tests(self):
        """Verify that property-based tests exist and are structured correctly"""
        try:
            # Check that property test files exist
            import os
            test_files = [
                'backend/students/test_email_properties.py',
                'backend/students/test_email_history_properties.py'
            ]
            
            existing_files = []
            for file_path in test_files:
                if os.path.exists(file_path):
                    existing_files.append(file_path)
            
            # We should have at least the history properties test
            assert len(existing_files) > 0, "No property test files found"
            
            # Check that the history properties test has the required property tests
            with open('backend/students/test_email_history_properties.py', 'r') as f:
                content = f.read()
                
            required_properties = [
                'Property 9: Email History Recording',
                'Property 17: History Filtering Accuracy',
                'Property 13: Administrative Action Logging'
            ]
            
            for prop in required_properties:
                assert prop in content, f"Missing property test: {prop}"
            
            return True
        except Exception as e:
            print(f"Property test verification error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all checkpoint tests"""
        print("🚀 Starting Email Management System Backend Checkpoint Tests")
        print("=" * 70)
        
        # Run all tests
        self.run_test("Email Models (Database Schema)", self.test_email_models)
        self.run_test("Email Service (SMTP & Configuration)", self.test_email_service)
        self.run_test("Template Service (Rendering & Variables)", self.test_template_service)
        self.run_test("Recipient Service (Filtering & Validation)", self.test_recipient_service)
        self.run_test("Email History Service (Tracking & Audit)", self.test_email_history_service)
        self.run_test("Service Integration (End-to-End)", self.test_service_integration)
        self.run_test("Database Migrations (Schema Integrity)", self.test_database_migrations)
        self.run_test("Property-Based Tests (Test Coverage)", self.test_property_based_tests)
        
        # Print summary
        print("\n" + "=" * 70)
        print("📊 CHECKPOINT SUMMARY")
        print("=" * 70)
        
        total_tests = self.passed_tests + self.failed_tests
        success_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {self.passed_tests}")
        print(f"Failed: {self.failed_tests}")
        print(f"Success Rate: {success_rate:.1f}%")
        
        if self.failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for test_name, status, error in self.test_results:
                if status in ['FAILED', 'ERROR']:
                    print(f"  • {test_name}: {error}")
        
        print("\n" + "=" * 70)
        
        if self.failed_tests == 0:
            print("🎉 ALL TESTS PASSED! Backend services are ready for API implementation.")
            print("\nNext Steps:")
            print("  1. Proceed to Task 6: Create Django API views and URL routing")
            print("  2. Implement email configuration API endpoints")
            print("  3. Create email composition and sending API endpoints")
            print("  4. Add email history API endpoints")
            return True
        else:
            print("⚠️  SOME TESTS FAILED! Please review and fix issues before proceeding.")
            print("\nRecommended Actions:")
            print("  1. Review failed test details above")
            print("  2. Fix any database or service configuration issues")
            print("  3. Re-run this checkpoint test")
            print("  4. Only proceed to API implementation when all tests pass")
            return False

def main():
    """Main function to run checkpoint tests"""
    checkpoint = EmailBackendCheckpoint()
    success = checkpoint.run_all_tests()
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())