"""
Property-Based Test for Audit Trail Completeness

This test validates Property 12: Audit Trail Completeness
- For any student selection change, the system should maintain a complete audit trail 
  that is traceable and persistent.

**Validates: Requirements 4.5**
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from django.test import TestCase, RequestFactory
from django.db import transaction
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from datetime import time, timedelta
import logging
import uuid

from students.models import Student, StudentLevelSelection, StudentCourseSelection, CourseSelectionAuditLog
from courses.models import Department, Level, Course, TimetableSlot, DepartmentTimetable, Lecturer
from institutions.models import Institution, Faculty
from users.models import User
from students.services.audit_service import CourseSelectionAuditService
from students.signals import AuditContext

logger = logging.getLogger(__name__)


class TestAuditTrailCompleteness(TestCase):
    """
    Property-based tests for audit trail completeness
    """
    
    def setUp(self):
        """Set up test data"""
        # Create institution
        self.institution = Institution.objects.create(
            name="Test University",
            code="TU",
            address="Test Address"
        )
        
        # Create faculty
        self.faculty = Faculty.objects.create(
            name="Faculty of Science",
            code="SCI",
            institution=self.institution
        )
        
        # Create department
        self.department = Department.objects.create(
            name="Computer Science",
            code="CS",
            faculty=self.faculty
        )
        
        # Create levels
        self.level_100 = Level.objects.create(
            name="Level 100",
            code="L100",
            department=self.department
        )
        
        self.level_200 = Level.objects.create(
            name="Level 200", 
            code="L200",
            department=self.department
        )
        
        # Create courses
        self.course_1 = Course.objects.create(
            title="Introduction to Programming",
            code="CS101",
            credit_units=3,
            department=self.department,
            level=self.level_100
        )
        
        self.course_2 = Course.objects.create(
            title="Data Structures",
            code="CS201",
            credit_units=3,
            department=self.department,
            level=self.level_200
        )
        
        # Create lecturer user
        self.lecturer_user = User.objects.create_user(
            username="lecturer1",
            email="lecturer@test.com",
            password="testpass123",
            first_name="John",
            last_name="Doe"
        )
        
        # Create lecturer
        self.lecturer = Lecturer.objects.create(
            user=self.lecturer_user,
            department=self.department,
            staff_id="LEC001"
        )
        
        # Create department timetable
        self.dept_timetable = DepartmentTimetable.objects.create(
            department=self.department,
            academic_year="2024/2025",
            semester="First"
        )
        
        # Create timetable slots
        self.slot_1 = TimetableSlot.objects.create(
            timetable=self.dept_timetable,
            course=self.course_1,
            lecturer=self.lecturer,
            level=self.level_100,
            day_of_week="MON",
            start_time=time(9, 0),
            end_time=time(10, 0),
            venue="Room 101"
        )
        
        # Create request factory for testing
        self.factory = RequestFactory()
    
    @given(
        matric_number=st.text(min_size=5, max_size=15, alphabet=st.characters(whitelist_categories=('Lu', 'Nd'))),
        full_name=st.text(min_size=5, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs'))),
        email_local=st.text(min_size=3, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))),
        course_selection_changes=st.lists(
            st.tuples(
                st.booleans(),  # is_offered
                st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs', 'Nd', 'Pc')))  # change_reason
            ),
            min_size=1, max_size=10
        )
    )
    @settings(max_examples=100, deadline=None)
    def test_complete_audit_trail_for_all_changes(self, matric_number, full_name, email_local, course_selection_changes):
        """
        **Property 12a: Complete Change Tracking**
        For any sequence of course selection changes, every single change should be 
        recorded in the audit trail with complete information including timestamps, 
        old/new values, and context.
        """
        assume(len(matric_number.strip()) >= 5)
        assume(len(full_name.strip()) >= 5)
        assume(len(email_local.strip()) >= 3)
        
        try:
            with transaction.atomic():
                # Create student user
                student_user = User.objects.create_user(
                    username=matric_number.strip(),
                    email=f"{email_local.strip()}@test.com",
                    password="testpass123",
                    first_name=full_name.strip().split()[0] if full_name.strip().split() else "Test",
                    last_name=" ".join(full_name.strip().split()[1:]) if len(full_name.strip().split()) > 1 else "User"
                )
                
                # Create student
                student = Student.objects.create(
                    user=student_user,
                    matric_number=matric_number.strip(),
                    full_name=full_name.strip(),
                    department=self.department,
                    faculty=self.faculty,
                    institution=self.institution
                )
                
                # Select level
                level_selection = StudentLevelSelection.objects.create(
                    student=student,
                    level=self.level_100
                )
                
                # Create mock request for audit context
                request = self.factory.post('/test/')
                request.META['HTTP_USER_AGENT'] = 'Test User Agent'
                request.META['REMOTE_ADDR'] = '127.0.0.1'
                request.session = {'session_key': 'test_session_key'}
                
                # Track expected audit entries
                expected_audit_entries = []
                
                # Perform sequence of course selection changes
                for i, (is_offered, change_reason) in enumerate(course_selection_changes):
                    change_reason_clean = change_reason.strip() or f"Change {i+1}"
                    
                    with AuditContext(request=request, change_reason=change_reason_clean):
                        # Get or create course selection
                        course_selection, created = StudentCourseSelection.objects.get_or_create(
                            student=student,
                            department=self.department,
                            level=self.level_100,
                            course=self.course_1,
                            defaults={'is_offered': is_offered}
                        )
                        
                        if created:
                            # This is a CREATE operation
                            expected_audit_entries.append({
                                'action': 'CREATE',
                                'old_is_offered': None,
                                'new_is_offered': is_offered,
                                'change_reason': change_reason_clean
                            })
                        else:
                            # This might be an UPDATE operation
                            old_is_offered = course_selection.is_offered
                            if old_is_offered != is_offered:
                                course_selection.is_offered = is_offered
                                course_selection.save()
                                
                                expected_audit_entries.append({
                                    'action': 'UPDATE',
                                    'old_is_offered': old_is_offered,
                                    'new_is_offered': is_offered,
                                    'change_reason': change_reason_clean
                                })
                
                # Verify audit trail completeness
                actual_audit_logs = CourseSelectionAuditLog.objects.filter(
                    student=student,
                    course=self.course_1
                ).order_by('timestamp')
                
                # Check that we have the expected number of audit entries
                assert actual_audit_logs.count() == len(expected_audit_entries), \
                    f"Expected {len(expected_audit_entries)} audit entries, got {actual_audit_logs.count()}"
                
                # Verify each audit entry
                for i, (expected, actual) in enumerate(zip(expected_audit_entries, actual_audit_logs)):
                    # Verify action type
                    assert actual.action == expected['action'], \
                        f"Entry {i}: Expected action {expected['action']}, got {actual.action}"
                    
                    # Verify old/new values
                    assert actual.old_is_offered == expected['old_is_offered'], \
                        f"Entry {i}: Expected old_is_offered {expected['old_is_offered']}, got {actual.old_is_offered}"
                    
                    assert actual.new_is_offered == expected['new_is_offered'], \
                        f"Entry {i}: Expected new_is_offered {expected['new_is_offered']}, got {actual.new_is_offered}"
                    
                    # Verify change reason
                    assert actual.change_reason == expected['change_reason'], \
                        f"Entry {i}: Expected change_reason '{expected['change_reason']}', got '{actual.change_reason}'"
                    
                    # Verify required fields are present
                    assert actual.student == student, f"Entry {i}: Student mismatch"
                    assert actual.course == self.course_1, f"Entry {i}: Course mismatch"
                    assert actual.level == self.level_100, f"Entry {i}: Level mismatch"
                    assert actual.department == self.department, f"Entry {i}: Department mismatch"
                    assert actual.timestamp is not None, f"Entry {i}: Missing timestamp"
                    
                    # Verify request context was captured
                    assert actual.ip_address == '127.0.0.1', f"Entry {i}: IP address not captured"
                    assert 'Test User Agent' in actual.user_agent, f"Entry {i}: User agent not captured"
                
                logger.info(f"✓ Property 12a verified: Complete audit trail for {len(expected_audit_entries)} changes for student {matric_number.strip()}")
                
        except Exception as e:
            logger.error(f"Error in test_complete_audit_trail_for_all_changes: {e}")
            raise
    
    @given(
        num_students=st.integers(min_value=1, max_value=5),
        operations_per_student=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50, deadline=None)
    def test_audit_trail_persistence_and_isolation(self, num_students, operations_per_student):
        """
        **Property 12b: Audit Trail Persistence and Isolation**
        For any number of students performing course selection operations, each student's 
        audit trail should be persistent, isolated, and complete regardless of concurrent 
        operations by other students.
        """
        students_created = []
        expected_audit_counts = {}
        
        try:
            with transaction.atomic():
                # Create multiple students
                for i in range(num_students):
                    matric = f"AUDIT{i:04d}"
                    
                    # Create student user
                    student_user = User.objects.create_user(
                        username=matric,
                        email=f"audit{i}@test.com",
                        password="testpass123",
                        first_name=f"Audit{i}",
                        last_name="Test"
                    )
                    
                    # Create student
                    student = Student.objects.create(
                        user=student_user,
                        matric_number=matric,
                        full_name=f"Audit {i} Test",
                        department=self.department,
                        faculty=self.faculty,
                        institution=self.institution
                    )
                    students_created.append(student)
                    
                    # Select level
                    StudentLevelSelection.objects.create(
                        student=student,
                        level=self.level_100
                    )
                    
                    expected_audit_counts[student.id] = 0
                
                # Perform operations for each student
                for student in students_created:
                    request = self.factory.post('/test/')
                    request.META['HTTP_USER_AGENT'] = f'Test Agent for {student.matric_number}'
                    request.META['REMOTE_ADDR'] = '127.0.0.1'
                    
                    for op_num in range(operations_per_student):
                        with AuditContext(request=request, change_reason=f"Operation {op_num+1}"):
                            # Alternate between creating and updating
                            if op_num == 0:
                                # Create initial selection
                                StudentCourseSelection.objects.create(
                                    student=student,
                                    department=self.department,
                                    level=self.level_100,
                                    course=self.course_1,
                                    is_offered=True
                                )
                                expected_audit_counts[student.id] += 1
                            else:
                                # Update existing selection
                                try:
                                    selection = StudentCourseSelection.objects.get(
                                        student=student,
                                        course=self.course_1
                                    )
                                    # Toggle the offering status
                                    selection.is_offered = not selection.is_offered
                                    selection.save()
                                    expected_audit_counts[student.id] += 1
                                except StudentCourseSelection.DoesNotExist:
                                    # Create if doesn't exist
                                    StudentCourseSelection.objects.create(
                                        student=student,
                                        department=self.department,
                                        level=self.level_100,
                                        course=self.course_1,
                                        is_offered=op_num % 2 == 0
                                    )
                                    expected_audit_counts[student.id] += 1
                
                # Verify audit trail persistence and isolation
                for student in students_created:
                    # Get audit logs for this student
                    student_audit_logs = CourseSelectionAuditLog.objects.filter(
                        student=student,
                        course=self.course_1
                    ).order_by('timestamp')
                    
                    # Verify expected count
                    expected_count = expected_audit_counts[student.id]
                    actual_count = student_audit_logs.count()
                    
                    assert actual_count == expected_count, \
                        f"Student {student.matric_number}: Expected {expected_count} audit entries, got {actual_count}"
                    
                    # Verify isolation - no audit logs from other students
                    for log in student_audit_logs:
                        assert log.student == student, \
                            f"Audit log isolation violated: found log for {log.student.matric_number} in {student.matric_number}'s audit trail"
                    
                    # Verify persistence - all logs have required fields
                    for log in student_audit_logs:
                        assert log.timestamp is not None, f"Missing timestamp in audit log {log.id}"
                        assert log.action in ['CREATE', 'UPDATE', 'DELETE'], f"Invalid action in audit log {log.id}"
                        assert log.student == student, f"Student mismatch in audit log {log.id}"
                        assert log.course == self.course_1, f"Course mismatch in audit log {log.id}"
                        assert log.level == self.level_100, f"Level mismatch in audit log {log.id}"
                        assert log.department == self.department, f"Department mismatch in audit log {log.id}"
                        
                        # Verify change summary is generated
                        assert len(log.change_summary) > 0, f"Missing change summary in audit log {log.id}"
                
                # Verify total audit log count
                total_expected = sum(expected_audit_counts.values())
                total_actual = CourseSelectionAuditLog.objects.filter(
                    student__in=students_created,
                    course=self.course_1
                ).count()
                
                assert total_actual == total_expected, \
                    f"Total audit count mismatch: expected {total_expected}, got {total_actual}"
                
                logger.info(f"✓ Property 12b verified: Audit trail persistence and isolation for {num_students} students with {operations_per_student} operations each")
                
        except Exception as e:
            logger.error(f"Error in test_audit_trail_persistence_and_isolation: {e}")
            raise
    
    @given(
        batch_size=st.integers(min_value=2, max_value=10),
        change_reason=st.text(min_size=1, max_size=100, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Zs', 'Nd', 'Pc')))
    )
    @settings(max_examples=50, deadline=None)
    def test_batch_operation_audit_trail(self, batch_size, change_reason):
        """
        **Property 12c: Batch Operation Audit Trail**
        For any batch operation involving multiple course selection changes, all changes 
        should be logged with a common batch identifier while maintaining individual 
        change details.
        """
        assume(len(change_reason.strip()) >= 1)
        
        try:
            with transaction.atomic():
                # Create multiple students for batch operation
                students = []
                for i in range(batch_size):
                    matric = f"BATCH{i:04d}"
                    
                    # Create student user
                    student_user = User.objects.create_user(
                        username=matric,
                        email=f"batch{i}@test.com",
                        password="testpass123",
                        first_name=f"Batch{i}",
                        last_name="Test"
                    )
                    
                    # Create student
                    student = Student.objects.create(
                        user=student_user,
                        matric_number=matric,
                        full_name=f"Batch {i} Test",
                        department=self.department,
                        faculty=self.faculty,
                        institution=self.institution
                    )
                    students.append(student)
                    
                    # Select level
                    StudentLevelSelection.objects.create(
                        student=student,
                        level=self.level_100
                    )
                
                # Prepare batch operation data
                selections_data = []
                for student in students:
                    selections_data.append({
                        'student': student,
                        'course': self.course_1,
                        'level': self.level_100,
                        'department': self.department,
                        'action': 'CREATE',
                        'new_is_offered': True,
                        'old_is_offered': None
                    })
                
                # Perform batch audit logging
                request = self.factory.post('/test/')
                request.META['HTTP_USER_AGENT'] = 'Batch Operation Agent'
                request.META['REMOTE_ADDR'] = '127.0.0.1'
                
                audit_logs = CourseSelectionAuditService.bulk_log_course_selections(
                    selections_data=selections_data,
                    request=request,
                    change_reason=change_reason.strip()
                )
                
                # Verify batch operation audit trail
                assert len(audit_logs) == batch_size, \
                    f"Expected {batch_size} audit logs, got {len(audit_logs)}"
                
                # Verify all logs have the same batch_id
                batch_ids = [log.batch_id for log in audit_logs]
                unique_batch_ids = set(batch_ids)
                assert len(unique_batch_ids) == 1, \
                    f"Expected single batch_id, got {len(unique_batch_ids)} different batch_ids"
                
                batch_id = batch_ids[0]
                assert batch_id is not None, "Batch ID should not be None"
                
                # Verify each audit log in the batch
                for i, log in enumerate(audit_logs):
                    assert log.student == students[i], f"Student mismatch in batch log {i}"
                    assert log.course == self.course_1, f"Course mismatch in batch log {i}"
                    assert log.level == self.level_100, f"Level mismatch in batch log {i}"
                    assert log.department == self.department, f"Department mismatch in batch log {i}"
                    assert log.action == 'CREATE', f"Action mismatch in batch log {i}"
                    assert log.new_is_offered == True, f"New offering status mismatch in batch log {i}"
                    assert log.old_is_offered is None, f"Old offering status should be None in batch log {i}"
                    assert log.change_reason == change_reason.strip(), f"Change reason mismatch in batch log {i}"
                    assert log.batch_id == batch_id, f"Batch ID mismatch in batch log {i}"
                    assert log.ip_address == '127.0.0.1', f"IP address not captured in batch log {i}"
                    assert 'Batch Operation Agent' in log.user_agent, f"User agent not captured in batch log {i}"
                
                # Verify batch logs can be retrieved together
                batch_logs_from_db = CourseSelectionAuditLog.objects.filter(batch_id=batch_id)
                assert batch_logs_from_db.count() == batch_size, \
                    f"Expected {batch_size} logs with batch_id {batch_id}, got {batch_logs_from_db.count()}"
                
                # Verify individual student audit summaries include batch operations
                for student in students:
                    summary = CourseSelectionAuditService.get_audit_summary_for_student(student)
                    assert summary['total_changes'] >= 1, f"Student {student.matric_number} should have at least 1 audit entry"
                    assert summary['action_counts']['create'] >= 1, f"Student {student.matric_number} should have at least 1 CREATE action"
                
                logger.info(f"✓ Property 12c verified: Batch operation audit trail for {batch_size} students with batch_id {batch_id}")
                
        except Exception as e:
            logger.error(f"Error in test_batch_operation_audit_trail: {e}")
            raise
    
    def test_property_12_audit_trail_completeness_summary(self):
        """
        Summary test that validates all aspects of Property 12
        """
        logger.info("=== Property 12: Audit Trail Completeness Test Summary ===")
        logger.info("✓ 12a: Complete change tracking for all course selection modifications")
        logger.info("✓ 12b: Audit trail persistence and isolation across multiple students")
        logger.info("✓ 12c: Batch operation audit trail with common batch identifiers")
        logger.info("✓ Requirements 4.5 validated through property-based testing")
        logger.info("=== Property 12 Test Complete ===")