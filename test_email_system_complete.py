#!/usr/bin/env python
"""
Complete Email Management System Test Suite

This script runs all tests for the email management system to ensure
everything is working properly before final deployment.

Usage:
    python test_email_system_complete.py

This will run:
1. All property-based tests
2. Integration tests
3. Unit tests
4. System verification checks
"""

import os
import sys
import subprocess
import django
from django.conf import settings
from django.test.utils import get_runner
from django.core.management import execute_from_command_line

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

def run_test_suite(test_module, description):
    """Run a specific test suite and return results"""
    print(f"\n{'='*60}")
    print(f"Running {description}")
    print(f"{'='*60}")
    
    try:
        # Use Django's test runner
        result = subprocess.run([
            sys.executable, 'manage.py', 'test', test_module, '-v', '2'
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print(f"✅ {description} - PASSED")
            return True
        else:
            print(f"❌ {description} - FAILED")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
    
    except subprocess.TimeoutExpired:
        print(f"⏰ {description} - TIMEOUT (5 minutes)")
        return False
    except Exception as e:
        print(f"💥 {description} - ERROR: {str(e)}")
        return False

def verify_system_components():
    """Verify that all system components are properly set up"""
    print(f"\n{'='*60}")
    print("Verifying System Components")
    print(f"{'='*60}")
    
    checks = []
    
    # Check if all required models exist
    try:
        from students.email_models import EmailConfiguration, EmailTemplate, EmailHistory, EmailDelivery
        print("✅ Email models imported successfully")
        checks.append(True)
    except ImportError as e:
        print(f"❌ Email models import failed: {e}")
        checks.append(False)
    
    # Check if all services exist
    try:
        from students.email_service import EmailService
        from students.template_service import TemplateService
        from students.recipient_service import RecipientService
        from students.email_history_service import EmailHistoryService
        print("✅ Email services imported successfully")
        checks.append(True)
    except ImportError as e:
        print(f"❌ Email services import failed: {e}")
        checks.append(False)
    
    # Check if all views exist
    try:
        from students.email_views import (
            get_smtp_configuration, save_smtp_configuration, test_smtp_connection,
            send_bulk_email, get_email_history, get_email_statistics
        )
        print("✅ Email views imported successfully")
        checks.append(True)
    except ImportError as e:
        print(f"❌ Email views import failed: {e}")
        checks.append(False)
    
    # Check if frontend components exist
    frontend_components = [
        'src/components/admin/EmailManagement.tsx',
        'src/components/admin/email/SMTPConfigurationPanel.tsx',
        'src/components/admin/email/EmailCompositionForm.tsx',
        'src/components/admin/email/RecipientSelector.tsx',
        'src/components/admin/email/EmailHistoryViewer.tsx'
    ]
    
    all_frontend_exist = True
    for component in frontend_components:
        if os.path.exists(component):
            print(f"✅ {component} exists")
        else:
            print(f"❌ {component} missing")
            all_frontend_exist = False
    
    checks.append(all_frontend_exist)
    
    # Check if API endpoints are configured
    try:
        from django.urls import reverse
        email_urls = [
            'admin_get_smtp_config',
            'admin_save_smtp_config',
            'admin_test_smtp_connection',
            'admin_send_bulk_email',
            'admin_get_email_history',
            'admin_get_email_statistics'
        ]
        
        for url_name in email_urls:
            try:
                reverse(url_name)
                print(f"✅ URL {url_name} configured")
            except:
                print(f"❌ URL {url_name} not found")
                all_frontend_exist = False
        
        checks.append(all_frontend_exist)
    except Exception as e:
        print(f"❌ URL configuration check failed: {e}")
        checks.append(False)
    
    return all(checks)

def main():
    """Main test execution function"""
    print("🚀 Starting Complete Email Management System Test Suite")
    print(f"Django version: {django.get_version()}")
    print(f"Python version: {sys.version}")
    
    # Verify system components first
    if not verify_system_components():
        print("\n❌ System component verification failed!")
        print("Please ensure all components are properly installed.")
        return False
    
    # Define test suites to run
    test_suites = [
        # Core functionality tests
        ('students.email_models', 'Email Models Tests'),
        ('students.email_service', 'Email Service Tests'),
        ('students.template_service', 'Template Service Tests'),
        ('students.recipient_service', 'Recipient Service Tests'),
        ('students.email_history_service', 'Email History Service Tests'),
        
        # Property-based tests
        ('students.test_email_properties', 'Core Email Properties'),
        ('students.test_security_encryption_properties', 'Security & Encryption Properties'),
        ('students.test_batch_processing_efficiency_properties', 'Batch Processing Properties'),
        ('students.test_rate_limiting_compliance_properties', 'Rate Limiting Properties'),
        ('students.test_student_data_integration_properties', 'Student Data Integration Properties'),
        ('students.test_missing_data_handling_properties', 'Missing Data Handling Properties'),
        ('students.test_session_management_properties', 'Session Management Properties'),
        ('students.test_concurrency_safety_properties', 'Concurrency Safety Properties'),
        
        # Integration tests
        ('students.test_integration_e2e', 'End-to-End Integration Tests'),
        
        # Error handling tests
        ('students.test_comprehensive_error_handling_properties', 'Error Handling Properties'),
        ('students.test_bulk_error_resilience_properties', 'Bulk Error Resilience Properties'),
    ]
    
    # Run all test suites
    results = []
    for test_module, description in test_suites:
        result = run_test_suite(test_module, description)
        results.append((description, result))
    
    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUITE SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for description, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status:<12} {description}")
    
    print(f"\nOverall Results: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Email Management System is ready for deployment.")
        return True
    else:
        print(f"\n⚠️  {total - passed} test suite(s) failed. Please review and fix issues.")
        return False

def run_quick_verification():
    """Run a quick verification of core functionality"""
    print("\n🔍 Running Quick Verification Tests")
    
    try:
        # Test database connectivity
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        print("✅ Database connection working")
        
        # Test model creation
        from students.email_models import EmailConfiguration
        config = EmailConfiguration(
            smtp_host='test.smtp.com',
            smtp_port=587,
            smtp_username='test@test.com',
            from_email='test@test.com',
            use_tls=True
        )
        config.set_password('test_password')
        print("✅ Email model creation working")
        
        # Test service instantiation
        from students.email_service import EmailService
        service = EmailService()
        print("✅ Email service instantiation working")
        
        # Test template service
        from students.template_service import TemplateService
        template_service = TemplateService()
        print("✅ Template service instantiation working")
        
        # Test recipient service
        from students.recipient_service import RecipientService
        recipient_service = RecipientService()
        print("✅ Recipient service instantiation working")
        
        print("✅ Quick verification completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Quick verification failed: {e}")
        return False

if __name__ == '__main__':
    # Change to the directory containing manage.py
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # Run quick verification first
    if not run_quick_verification():
        print("Quick verification failed. Skipping full test suite.")
        sys.exit(1)
    
    # Run full test suite
    success = main()
    
    if success:
        print("\n📋 DEPLOYMENT CHECKLIST:")
        print("✅ All tests passing")
        print("✅ Email models configured")
        print("✅ Email services implemented")
        print("✅ API endpoints configured")
        print("✅ Frontend components created")
        print("✅ Property-based tests validated")
        print("✅ Integration tests verified")
        print("✅ Error handling tested")
        print("✅ Security measures implemented")
        print("✅ Performance optimizations applied")
        print("✅ Concurrency safety verified")
        print("\n🚀 Email Management System is READY FOR PRODUCTION!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please review and fix issues before deployment.")
        sys.exit(1)