#!/usr/bin/env python
"""
Simple test script for email history service functionality
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
from students.email_models import EmailHistory, EmailDelivery, EmailTemplate
from students.email_history_service import EmailHistoryService
from students.models import Student
from institutions.models import Institution, Faculty, Department

User = get_user_model()

def test_email_history_service():
    """Test basic email history service functionality"""
    print("Testing Email History Service...")
    
    try:
        # Create admin user
        print("Creating test user...")
        admin_user = User.objects.get_or_create(
            username="test_admin",
            defaults={
                'email': 'admin@test.com',
                'is_staff': True
            }
        )[0]
        
        # Create email template
        template = EmailTemplate.objects.get_or_create(
            name="Test Template",
            defaults={
                'category': 'general',
                'subject_template': 'Test Subject: {student_name}',
                'body_template': 'Hello {student_name}, this is a test email.',
                'variables': ['student_name'],
                'is_active': True
            }
        )[0]
        
        # Initialize service
        service = EmailHistoryService()
        
        # Test 1: Save email record
        print("Test 1: Saving email record...")
        recipients = ['test1@example.com', 'test2@example.com', 'test3@example.com']
        
        history = service.save_email_record(
            sender_user=admin_user,
            subject="Test Email Subject",
            body="Test email body content",
            recipients=recipients,
            template_used=template
        )
        
        assert history is not None, "Email history record should be created"
        assert history.sender == admin_user, "Sender should match"
        assert history.subject == "Test Email Subject", "Subject should match"
        assert history.recipient_count == 3, "Recipient count should be 3"
        assert history.status == 'sending', "Initial status should be 'sending'"
        
        # Verify delivery records were created
        delivery_records = EmailDelivery.objects.filter(email_history=history)
        assert delivery_records.count() == 3, "Should have 3 delivery records"
        
        print("✓ Email record saved successfully")
        
        # Test 2: Update delivery status
        print("Test 2: Updating delivery status...")
        
        success = service.update_delivery_status(
            record_id=history.id,
            recipient_email='test1@example.com',
            status='sent'
        )
        
        assert success, "Delivery status update should succeed"
        
        # Refresh history record
        history.refresh_from_db()
        assert history.success_count == 1, "Success count should be 1"
        assert history.failure_count == 0, "Failure count should be 0"
        
        print("✓ Delivery status updated successfully")
        
        # Test 3: Get email history
        print("Test 3: Retrieving email history...")
        
        result = service.get_email_history(page_size=10)
        
        assert 'results' in result, "Result should contain 'results'"
        assert 'pagination' in result, "Result should contain 'pagination'"
        assert len(result['results']) > 0, "Should have at least one result"
        
        # Find our test email
        test_email = None
        for item in result['results']:
            if item['id'] == history.id:
                test_email = item
                break
        
        assert test_email is not None, "Should find our test email in results"
        assert test_email['subject'] == "Test Email Subject", "Subject should match"
        assert test_email['recipient_count'] == 3, "Recipient count should match"
        
        print("✓ Email history retrieved successfully")
        
        # Test 4: Get delivery details
        print("Test 4: Getting delivery details...")
        
        delivery_details = service.get_delivery_details(history.id)
        
        assert len(delivery_details) == 3, "Should have 3 delivery details"
        
        # Check that one delivery is marked as sent
        sent_deliveries = [d for d in delivery_details if d['delivery_status'] == 'sent']
        assert len(sent_deliveries) == 1, "Should have 1 sent delivery"
        
        print("✓ Delivery details retrieved successfully")
        
        # Test 5: Search functionality
        print("Test 5: Testing search functionality...")
        
        search_results = service.search_email_history("Test Email")
        
        assert len(search_results) > 0, "Should find results for 'Test Email'"
        
        # Find our test email in search results
        found = False
        for item in search_results:
            if item['id'] == history.id:
                found = True
                break
        
        assert found, "Should find our test email in search results"
        
        print("✓ Search functionality working")
        
        # Test 6: Administrative action logging
        print("Test 6: Testing administrative action logging...")
        
        # This test just verifies the methods don't crash
        service.log_smtp_configuration_change(
            user=admin_user,
            old_config={'smtp_host': 'old.example.com'},
            new_config={'smtp_host': 'new.example.com'}
        )
        
        service.log_template_action(
            action='created',
            user=admin_user,
            template_id=template.id,
            template_name=template.name
        )
        
        service.log_bulk_email_operation(
            user=admin_user,
            operation='initiated',
            recipient_count=3,
            template_used=template.name
        )
        
        print("✓ Administrative action logging working")
        
        print("\n🎉 All tests passed! Email History Service is working correctly.")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_email_history_service()
    sys.exit(0 if success else 1)