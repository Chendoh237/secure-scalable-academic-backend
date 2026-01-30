"""
Property-Based Tests for Concurrency Safety

This module contains property-based tests that validate the concurrency safety
properties of the email management system, ensuring that concurrent operations
maintain data consistency and system integrity.

**Property 27: Concurrency Safety**
For any concurrent operations on the email system, data consistency and system
integrity should be maintained without race conditions or data corruption.
**Validates: Requirements 10.5**
"""

import unittest
import threading
import time
import queue
from hypothesis import given, strategies as st, settings, assume
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import transaction, connection
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json
import random

from students.email_models import EmailConfiguration, EmailTemplate, EmailHistory, EmailDelivery
from students.email_service import EmailService
from students.template_service import TemplateService
from students.recipient_service import RecipientService
from students.email_history_service import EmailHistoryService
from students.models import Student
from institutions.models import Institution, Faculty, Department
from institutions.program_models import AcademicProgram

User = get_user_model()


class ConcurrencySafetyPropertiesTest(TransactionTestCase):
    """
    Property-based tests for concurrency safety in the email management system.
    
    **Feature: email-management-system, Property 27: Concurrency Safety**
    **Validates: Requirements 10.5**
    """
    
    def setUp(self):
        """Set up test environment"""
        # Create admin user
        self.admin_user = User.objects.create_user(
            username='concurrency_admin',
            email='admin@concurrent.test',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )
        
        # Create institution structure
        self.institution = Institution.objects.create(
            name="Concurrent Test University",
            code="CTU",
            address="456 Concurrent St"
        )
        
        self.faculty = Faculty.objects.create(
            name="Concurrent Faculty",
            institution=self.institution
        )
        
        self.department = Department.objects.create(
            name="Concurrent Department",
            faculty=self.faculty
        )
        
        self.program = AcademicProgram.objects.create(
            name="Concurrent Program",
            code="CP",
            department=self.department
        )
        
        # Create test students
        self.students = []
        for i in range(10):
            student = Student.objects.create(
                student_id=f"CONC{i:03d}",
                first_name=f"Concurrent{i}",
                last_name="Student",
                email=f"concurrent{i}@test.edu",
                department=self.department,
                level="Level 1",
                is_approved=True
            )
            self.students.append(student)
    
    @given(
        concurrent_operations=st.lists(
            st.sampled_from(['smtp_config', 'email_send', 'history_query', 'template_render']),
            min_size=2, max_size=8
        ),
        operation_delays=st.lists(
            st.floats(min_value=0.0, max_value=0.5),  # Small delays to create race conditions
            min_size=2, max_size=8
        )
    )
    @settings(max_examples=10, deadline=15000)
    def test_concurrent_operations_data_consistency_property(self, concurrent_operations, operation_delays):
        """
        **Property 27a: Concurrent Operations Data Consistency**
        For any set of concurrent operations, the system should maintain data
        consistency without corruption or race conditions.
        **Validates: Requirements 10.5**
        """
        # Ensure we have matching lengths
        min_length = min(len(concurrent_operations), len(operation_delays))
        concurrent_operations = concurrent_operations[:min_length]
        operation_delays = operation_delays[:min_length]
        
        # Skip if too few operations
        assume(len(concurrent_operations) >= 2)
        
        results = queue.Queue()
        errors = queue.Queue()
        
        def perform_smtp_config(delay, thread_id):
            """Perform SMTP configuration operation"""
            try:
                time.sleep(delay)
                
                config_data = {
                    'smtp_host': f'smtp.thread{thread_id}.com',
                    'smtp_port': 587,
                    'smtp_username': f'thread{thread_id}@test.com',
                    'smtp_password': f'password{thread_id}',
                    'from_email': f'thread{thread_id}@test.com',
                    'use_tls': True,
                    'use_ssl': False
                }
                
                # Simulate database transaction
                with transaction.atomic():
                    # Deactivate existing configurations
                    EmailConfiguration.objects.filter(is_active=True).update(is_active=False)
                    
                    # Create new configuration
                    config = EmailConfiguration.objects.create(
                        smtp_host=config_data['smtp_host'],
                        smtp_port=config_data['smtp_port'],
                        smtp_username=config_data['smtp_username'],
                        from_email=config_data['from_email'],
                        use_tls=config_data['use_tls'],
                        use_ssl=config_data['use_ssl'],
                        is_active=True
                    )
                    config.set_password(config_data['smtp_password'])
                    config.save()
                
                results.put({
                    'operation': 'smtp_config',
                    'thread_id': thread_id,
                    'success': True,
                    'config_id': config.id
                })
                
            except Exception as e:
                errors.put({
                    'operation': 'smtp_config',
                    'thread_id': thread_id,
                    'error': str(e)
                })
        
        def perform_email_send(delay, thread_id):
            """Perform email sending operation"""
            try:
                time.sleep(delay)
                
                # Ensure we have an active SMTP configuration
                config = EmailConfiguration.objects.filter(is_active=True).first()
                if not config:
                    # Create a default configuration for this test
                    config = EmailConfiguration.objects.create(
                        smtp_host='smtp.default.com',
                        smtp_port=587,
                        smtp_username='default@test.com',
                        from_email='default@test.com',
                        use_tls=True,
                        is_active=True
                    )
                    config.set_password('default_password')
                    config.save()
                
                # Create email history record
                with transaction.atomic():
                    history = EmailHistory.objects.create(
                        sender=self.admin_user,
                        subject=f'Concurrent Email from Thread {thread_id}',
                        message=f'This is a test email from thread {thread_id}',
                        recipient_count=len(self.students),
                        successful_sends=len(self.students),
                        failed_sends=0,
                        status='completed'
                    )
                    
                    # Create delivery records
                    for student in self.students:
                        EmailDelivery.objects.create(
                            email_history=history,
                            recipient_email=student.email,
                            recipient_name=f"{student.first_name} {student.last_name}",
                            status='delivered',
                            delivered_at=timezone.now()
                        )
                
                results.put({
                    'operation': 'email_send',
                    'thread_id': thread_id,
                    'success': True,
                    'history_id': history.id
                })
                
            except Exception as e:
                errors.put({
                    'operation': 'email_send',
                    'thread_id': thread_id,
                    'error': str(e)
                })
        
        def perform_history_query(delay, thread_id):
            """Perform email history query operation"""
            try:
                time.sleep(delay)
                
                # Query email history
                with transaction.atomic():
                    histories = EmailHistory.objects.select_related('sender').all()
                    history_count = histories.count()
                    
                    # Perform some aggregation operations
                    total_recipients = sum(h.recipient_count for h in histories)
                    total_successful = sum(h.successful_sends for h in histories)
                    
                results.put({
                    'operation': 'history_query',
                    'thread_id': thread_id,
                    'success': True,
                    'history_count': history_count,
                    'total_recipients': total_recipients,
                    'total_successful': total_successful
                })
                
            except Exception as e:
                errors.put({
                    'operation': 'history_query',
                    'thread_id': thread_id,
                    'error': str(e)
                })
        
        def perform_template_render(delay, thread_id):
            """Perform template rendering operation"""
            try:
                time.sleep(delay)
                
                # Create or get a template
                template_name = f'concurrent_template_{thread_id}'
                template_content = f'Hello {{{{ student_name }}}}, this is from thread {thread_id}'
                
                with transaction.atomic():
                    template, created = EmailTemplate.objects.get_or_create(
                        name=template_name,
                        defaults={
                            'subject': f'Template from Thread {thread_id}',
                            'content': template_content,
                            'category': 'test'
                        }
                    )
                    
                    # Render template with context
                    template_service = TemplateService()
                    context = {'student_name': f'TestStudent{thread_id}'}
                    rendered = template_service.render_template(template.id, context)
                
                results.put({
                    'operation': 'template_render',
                    'thread_id': thread_id,
                    'success': True,
                    'template_id': template.id,
                    'rendered_length': len(rendered['content'])
                })
                
            except Exception as e:
                errors.put({
                    'operation': 'template_render',
                    'thread_id': thread_id,
                    'error': str(e)
                })
        
        # Map operations to functions
        operation_functions = {
            'smtp_config': perform_smtp_config,
            'email_send': perform_email_send,
            'history_query': perform_history_query,
            'template_render': perform_template_render
        }
        
        # Start concurrent threads
        threads = []
        for i, (operation, delay) in enumerate(zip(concurrent_operations, operation_delays)):
            if operation in operation_functions:
                thread = threading.Thread(
                    target=operation_functions[operation],
                    args=(delay, i)
                )
                threads.append(thread)
                thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=10)  # 10 second timeout per thread
        
        # Collect results
        operation_results = []
        while not results.empty():
            operation_results.append(results.get())
        
        operation_errors = []
        while not errors.empty():
            operation_errors.append(errors.get())
        
        # Verify data consistency
        if operation_errors:
            # Some errors are acceptable in concurrent scenarios, but not data corruption
            for error in operation_errors:
                # Database integrity errors are not acceptable
                self.assertNotIn('integrity', error['error'].lower(),
                               f"Database integrity error in {error['operation']}: {error['error']}")
                self.assertNotIn('corruption', error['error'].lower(),
                               f"Data corruption error in {error['operation']}: {error['error']}")
        
        # Verify that at least some operations succeeded
        successful_operations = [r for r in operation_results if r['success']]
        self.assertTrue(len(successful_operations) > 0,
                       "At least some concurrent operations should succeed")
        
        # Verify database consistency
        # Only one SMTP configuration should be active
        active_configs = EmailConfiguration.objects.filter(is_active=True)
        self.assertLessEqual(active_configs.count(), 1,
                           "Only one SMTP configuration should be active")
        
        # All email histories should have consistent data
        histories = EmailHistory.objects.all()
        for history in histories:
            # Recipient count should match delivery records
            delivery_count = EmailDelivery.objects.filter(email_history=history).count()
            self.assertEqual(history.recipient_count, delivery_count,
                           f"History {history.id} recipient count mismatch")
            
            # Successful sends should not exceed recipient count
            self.assertLessEqual(history.successful_sends, history.recipient_count,
                               f"History {history.id} successful sends exceed recipient count")
    
    @given(
        smtp_configs=st.lists(
            st.tuples(
                st.text(min_size=5, max_size=20),  # smtp_host
                st.integers(min_value=25, max_value=587),  # smtp_port
                st.text(min_size=5, max_size=30),  # username
                st.booleans()  # use_tls
            ),
            min_size=2, max_size=5
        )
    )
    @settings(max_examples=8, deadline=12000)
    def test_concurrent_smtp_configuration_property(self, smtp_configs):
        """
        **Property 27b: Concurrent SMTP Configuration**
        For any concurrent SMTP configuration updates, only one configuration
        should remain active and data should be consistent.
        **Validates: Requirements 10.5**
        """
        results = queue.Queue()
        errors = queue.Queue()
        
        def configure_smtp(config_data, thread_id):
            """Configure SMTP in a thread"""
            try:
                host, port, username, use_tls = config_data
                
                # Add some randomness to create race conditions
                time.sleep(random.uniform(0.01, 0.1))
                
                with transaction.atomic():
                    # Deactivate existing configurations
                    EmailConfiguration.objects.filter(is_active=True).update(is_active=False)
                    
                    # Create new configuration
                    config = EmailConfiguration.objects.create(
                        smtp_host=f"{host}.thread{thread_id}.com",
                        smtp_port=port,
                        smtp_username=f"{username}@thread{thread_id}.com",
                        from_email=f"{username}@thread{thread_id}.com",
                        use_tls=use_tls,
                        use_ssl=False,
                        is_active=True
                    )
                    config.set_password(f'password{thread_id}')
                    config.save()
                
                results.put({
                    'thread_id': thread_id,
                    'config_id': config.id,
                    'success': True
                })
                
            except Exception as e:
                errors.put({
                    'thread_id': thread_id,
                    'error': str(e)
                })
        
        # Start concurrent configuration threads
        threads = []
        for i, config_data in enumerate(smtp_configs):
            thread = threading.Thread(target=configure_smtp, args=(config_data, i))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)
        
        # Collect results
        thread_results = []
        while not results.empty():
            thread_results.append(results.get())
        
        thread_errors = []
        while not errors.empty():
            thread_errors.append(errors.get())
        
        # Verify consistency: only one active configuration should exist
        active_configs = EmailConfiguration.objects.filter(is_active=True)
        self.assertLessEqual(active_configs.count(), 1,
                           "Only one SMTP configuration should be active after concurrent updates")
        
        # At least one configuration should have succeeded
        self.assertTrue(len(thread_results) > 0 or len(thread_errors) < len(smtp_configs),
                       "At least one SMTP configuration should succeed")
        
        # No data corruption errors should occur
        for error in thread_errors:
            self.assertNotIn('integrity', error['error'].lower(),
                           f"Database integrity error: {error['error']}")
    
    @given(
        email_batches=st.lists(
            st.tuples(
                st.text(min_size=5, max_size=50),  # subject
                st.text(min_size=10, max_size=100),  # message
                st.integers(min_value=1, max_value=5)  # recipient_count
            ),
            min_size=2, max_size=6
        )
    )
    @settings(max_examples=8, deadline=15000)
    def test_concurrent_email_sending_property(self, email_batches):
        """
        **Property 27c: Concurrent Email Sending**
        For any concurrent email sending operations, all email history records
        should be created correctly without data loss or corruption.
        **Validates: Requirements 10.5**
        """
        # Set up SMTP configuration
        config = EmailConfiguration.objects.create(
            smtp_host='smtp.concurrent.test',
            smtp_port=587,
            smtp_username='concurrent@test.com',
            from_email='concurrent@test.com',
            use_tls=True,
            is_active=True
        )
        config.set_password('test_password')
        config.save()
        
        results = queue.Queue()
        errors = queue.Queue()
        
        def send_email_batch(email_data, thread_id):
            """Send email batch in a thread"""
            try:
                subject, message, recipient_count = email_data
                
                # Add some randomness to create race conditions
                time.sleep(random.uniform(0.01, 0.2))
                
                with transaction.atomic():
                    # Create email history
                    history = EmailHistory.objects.create(
                        sender=self.admin_user,
                        subject=f"{subject} (Thread {thread_id})",
                        message=f"{message} (From thread {thread_id})",
                        recipient_count=recipient_count,
                        successful_sends=recipient_count,
                        failed_sends=0,
                        status='completed'
                    )
                    
                    # Create delivery records
                    for i in range(recipient_count):
                        student = self.students[i % len(self.students)]
                        EmailDelivery.objects.create(
                            email_history=history,
                            recipient_email=student.email,
                            recipient_name=f"{student.first_name} {student.last_name}",
                            status='delivered',
                            delivered_at=timezone.now()
                        )
                
                results.put({
                    'thread_id': thread_id,
                    'history_id': history.id,
                    'recipient_count': recipient_count,
                    'success': True
                })
                
            except Exception as e:
                errors.put({
                    'thread_id': thread_id,
                    'error': str(e),
                    'email_data': email_data
                })
        
        # Start concurrent email sending threads
        threads = []
        for i, email_data in enumerate(email_batches):
            thread = threading.Thread(target=send_email_batch, args=(email_data, i))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=8)
        
        # Collect results
        send_results = []
        while not results.empty():
            send_results.append(results.get())
        
        send_errors = []
        while not errors.empty():
            send_errors.append(errors.get())
        
        # Verify data consistency
        # All successful email histories should have correct delivery records
        for result in send_results:
            history = EmailHistory.objects.get(id=result['history_id'])
            delivery_count = EmailDelivery.objects.filter(email_history=history).count()
            
            self.assertEqual(history.recipient_count, delivery_count,
                           f"History {history.id} has mismatched delivery count")
            self.assertEqual(history.recipient_count, result['recipient_count'],
                           f"History {history.id} recipient count mismatch")
            self.assertEqual(history.successful_sends, delivery_count,
                           f"History {history.id} successful sends mismatch")
        
        # No data corruption should occur
        for error in send_errors:
            self.assertNotIn('integrity', error['error'].lower(),
                           f"Database integrity error: {error['error']}")
            self.assertNotIn('foreign key', error['error'].lower(),
                           f"Foreign key constraint error: {error['error']}")
        
        # At least some emails should be sent successfully
        self.assertTrue(len(send_results) > 0,
                       "At least some concurrent email sends should succeed")
    
    @given(
        query_operations=st.lists(
            st.sampled_from(['count_histories', 'sum_recipients', 'filter_by_status', 'aggregate_stats']),
            min_size=3, max_size=8
        )
    )
    @settings(max_examples=6, deadline=10000)
    def test_concurrent_database_queries_property(self, query_operations):
        """
        **Property 27d: Concurrent Database Queries**
        For any concurrent database query operations, results should be
        consistent and no deadlocks should occur.
        **Validates: Requirements 10.5**
        """
        # Create test data
        for i in range(10):
            history = EmailHistory.objects.create(
                sender=self.admin_user,
                subject=f'Test Email {i}',
                message=f'Test message {i}',
                recipient_count=random.randint(1, 5),
                successful_sends=random.randint(1, 5),
                failed_sends=random.randint(0, 2),
                status=random.choice(['completed', 'partial_failure', 'failed'])
            )
        
        results = queue.Queue()
        errors = queue.Queue()
        
        def perform_query(operation, thread_id):
            """Perform database query in a thread"""
            try:
                time.sleep(random.uniform(0.01, 0.1))
                
                if operation == 'count_histories':
                    count = EmailHistory.objects.count()
                    result = {'operation': operation, 'count': count}
                
                elif operation == 'sum_recipients':
                    from django.db.models import Sum
                    total = EmailHistory.objects.aggregate(
                        total=Sum('recipient_count')
                    )['total'] or 0
                    result = {'operation': operation, 'total_recipients': total}
                
                elif operation == 'filter_by_status':
                    completed_count = EmailHistory.objects.filter(status='completed').count()
                    result = {'operation': operation, 'completed_count': completed_count}
                
                elif operation == 'aggregate_stats':
                    from django.db.models import Sum, Avg, Count
                    stats = EmailHistory.objects.aggregate(
                        total_emails=Count('id'),
                        avg_recipients=Avg('recipient_count'),
                        total_successful=Sum('successful_sends')
                    )
                    result = {'operation': operation, 'stats': stats}
                
                results.put({
                    'thread_id': thread_id,
                    'success': True,
                    'result': result
                })
                
            except Exception as e:
                errors.put({
                    'thread_id': thread_id,
                    'operation': operation,
                    'error': str(e)
                })
        
        # Start concurrent query threads
        threads = []
        for i, operation in enumerate(query_operations):
            thread = threading.Thread(target=perform_query, args=(operation, i))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=5)
        
        # Collect results
        query_results = []
        while not results.empty():
            query_results.append(results.get())
        
        query_errors = []
        while not errors.empty():
            query_errors.append(errors.get())
        
        # Verify no deadlocks occurred
        for error in query_errors:
            self.assertNotIn('deadlock', error['error'].lower(),
                           f"Deadlock detected in {error['operation']}: {error['error']}")
            self.assertNotIn('timeout', error['error'].lower(),
                           f"Query timeout in {error['operation']}: {error['error']}")
        
        # Verify query consistency
        # All count operations should return the same value (since we're not modifying data)
        count_results = [r['result']['count'] for r in query_results 
                        if r['result']['operation'] == 'count_histories']
        if len(count_results) > 1:
            self.assertTrue(all(c == count_results[0] for c in count_results),
                           "Concurrent count queries should return consistent results")
        
        # At least most queries should succeed
        success_rate = len(query_results) / len(query_operations)
        self.assertGreater(success_rate, 0.5,
                          "At least 50% of concurrent queries should succeed")
    
    @given(
        mixed_operations=st.lists(
            st.tuples(
                st.sampled_from(['create', 'read', 'update', 'delete']),
                st.integers(min_value=1, max_value=100)  # operation_id
            ),
            min_size=4, max_size=10
        )
    )
    @settings(max_examples=5, deadline=12000)
    def test_concurrent_crud_operations_property(self, mixed_operations):
        """
        **Property 27e: Concurrent CRUD Operations**
        For any mix of concurrent create, read, update, delete operations,
        data integrity should be maintained.
        **Validates: Requirements 10.5**
        """
        results = queue.Queue()
        errors = queue.Queue()
        
        def perform_crud_operation(operation_data, thread_id):
            """Perform CRUD operation in a thread"""
            try:
                operation, operation_id = operation_data
                time.sleep(random.uniform(0.01, 0.1))
                
                if operation == 'create':
                    with transaction.atomic():
                        template = EmailTemplate.objects.create(
                            name=f'CRUD Template {operation_id}',
                            subject=f'CRUD Subject {operation_id}',
                            content=f'CRUD Content {operation_id}',
                            category='crud_test'
                        )
                    result = {'operation': 'create', 'template_id': template.id}
                
                elif operation == 'read':
                    templates = EmailTemplate.objects.filter(category='crud_test')
                    result = {'operation': 'read', 'template_count': templates.count()}
                
                elif operation == 'update':
                    with transaction.atomic():
                        templates = EmailTemplate.objects.filter(category='crud_test')
                        if templates.exists():
                            template = templates.first()
                            template.subject = f'Updated Subject {operation_id}'
                            template.save()
                            result = {'operation': 'update', 'template_id': template.id}
                        else:
                            result = {'operation': 'update', 'template_id': None}
                
                elif operation == 'delete':
                    with transaction.atomic():
                        templates = EmailTemplate.objects.filter(category='crud_test')
                        if templates.exists():
                            template = templates.first()
                            template_id = template.id
                            template.delete()
                            result = {'operation': 'delete', 'deleted_id': template_id}
                        else:
                            result = {'operation': 'delete', 'deleted_id': None}
                
                results.put({
                    'thread_id': thread_id,
                    'success': True,
                    'result': result
                })
                
            except Exception as e:
                errors.put({
                    'thread_id': thread_id,
                    'operation': operation_data[0],
                    'error': str(e)
                })
        
        # Start concurrent CRUD threads
        threads = []
        for i, operation_data in enumerate(mixed_operations):
            thread = threading.Thread(target=perform_crud_operation, args=(operation_data, i))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join(timeout=6)
        
        # Collect results
        crud_results = []
        while not results.empty():
            crud_results.append(results.get())
        
        crud_errors = []
        while not errors.empty():
            crud_errors.append(errors.get())
        
        # Verify data integrity
        for error in crud_errors:
            # Some errors are acceptable (e.g., trying to update non-existent records)
            # But integrity violations are not
            self.assertNotIn('integrity', error['error'].lower(),
                           f"Data integrity error in {error['operation']}: {error['error']}")
            self.assertNotIn('constraint', error['error'].lower(),
                           f"Constraint violation in {error['operation']}: {error['error']}")
        
        # Verify that database is in a consistent state
        remaining_templates = EmailTemplate.objects.filter(category='crud_test')
        
        # All remaining templates should have valid data
        for template in remaining_templates:
            self.assertIsNotNone(template.name)
            self.assertIsNotNone(template.subject)
            self.assertIsNotNone(template.content)
            self.assertEqual(template.category, 'crud_test')
        
        # At least some operations should have succeeded
        self.assertTrue(len(crud_results) > 0,
                       "At least some concurrent CRUD operations should succeed")
    
    def test_transaction_isolation_levels(self):
        """
        Test that transaction isolation levels prevent data corruption.
        **Validates: Requirements 10.5**
        """
        # Create initial SMTP configuration
        initial_config = EmailConfiguration.objects.create(
            smtp_host='initial.smtp.com',
            smtp_port=587,
            smtp_username='initial@test.com',
            from_email='initial@test.com',
            use_tls=True,
            is_active=True
        )
        initial_config.set_password('initial_password')
        initial_config.save()
        
        results = []
        
        def concurrent_config_update(thread_id):
            """Update SMTP configuration concurrently"""
            try:
                with transaction.atomic():
                    # Read current active config
                    current_config = EmailConfiguration.objects.filter(is_active=True).first()
                    
                    if current_config:
                        # Deactivate current
                        current_config.is_active = False
                        current_config.save()
                    
                    # Create new config
                    new_config = EmailConfiguration.objects.create(
                        smtp_host=f'thread{thread_id}.smtp.com',
                        smtp_port=587,
                        smtp_username=f'thread{thread_id}@test.com',
                        from_email=f'thread{thread_id}@test.com',
                        use_tls=True,
                        is_active=True
                    )
                    new_config.set_password(f'password{thread_id}')
                    new_config.save()
                    
                    results.append({
                        'thread_id': thread_id,
                        'config_id': new_config.id,
                        'success': True
                    })
            
            except Exception as e:
                results.append({
                    'thread_id': thread_id,
                    'error': str(e),
                    'success': False
                })
        
        # Start multiple concurrent transactions
        threads = []
        for i in range(3):
            thread = threading.Thread(target=concurrent_config_update, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Verify only one active configuration exists
        active_configs = EmailConfiguration.objects.filter(is_active=True)
        self.assertEqual(active_configs.count(), 1,
                        "Only one SMTP configuration should be active after concurrent updates")
        
        # At least one transaction should have succeeded
        successful_results = [r for r in results if r['success']]
        self.assertTrue(len(successful_results) >= 1,
                       "At least one concurrent transaction should succeed")


if __name__ == '__main__':
    unittest.main()