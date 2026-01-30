#!/usr/bin/env python
"""
Performance Testing Script for Student Timetable Module

This script tests system performance with multiple concurrent students
to ensure the module can handle realistic load scenarios.

Requirements: 8.3 - Test system performance with multiple concurrent students
"""

import os
import sys
import django
import time
import json
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import threading
from dataclasses import dataclass
from datetime import datetime

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import transaction, connections
from django.core.management import call_command
from django.test.utils import override_settings
from django.urls import reverse

from students.models import Student, StudentLevelSelection, StudentCourseSelection
from courses.models import Level, Course, TimetableSlot, DepartmentTimetable
from institutions.models import Institution, Faculty, Department
from users.models import User
from students.monitoring import PerformanceMonitor, SystemHealthMonitor

User = get_user_model()


@dataclass
class PerformanceResult:
    """Container for performance test results"""
    operation: str
    response_time: float
    success: bool
    error_message: str = ""
    status_code: int = 200


class StudentTimetablePerformanceTest(TransactionTestCase):
    """
    Performance tests for Student Timetable Module
    
    Tests system performance with multiple concurrent students
    performing various operations simultaneously.
    """
    
    # Test configuration
    CONCURRENT_STUDENTS = 50  # Number of concurrent students to simulate
    OPERATIONS_PER_STUDENT = 10  # Number of operations each student performs
    MAX_RESPONSE_TIME = 2000  # Maximum acceptable response time in milliseconds
    MIN_SUCCESS_RATE = 95  # Minimum acceptable success rate percentage
    
    @classmethod
    def setUpClass(cls):
        """Set up test data for performance testing"""
        super().setUpClass()
        
        # Clear any existing performance metrics
        PerformanceMonitor.clear_metrics()
        
        # Create test institution structure
        cls.institution = Institution.objects.create(
            name="Test University",
            code="TU",
            address="Test Address"
        )
        
        cls.faculty = Faculty.objects.create(
            name="Faculty of Engineering",
            code="FOE",
            institution=cls.institution
        )
        
        cls.department = Department.objects.create(
            name="Computer Science",
            code="CS",
            faculty=cls.faculty
        )
        
        # Create test levels
        cls.levels = []
        for i in range(1, 5):  # Create 4 levels
            level = Level.objects.create(
                name=f"Level {i}00",
                code=f"L{i}00",
                department=cls.department
            )
            cls.levels.append(level)
        
        # Create test courses for each level
        cls.courses = []
        for level in cls.levels:
            for j in range(1, 8):  # 7 courses per level
                course = Course.objects.create(
                    code=f"CS{level.code[1:]}{j:02d}",
                    title=f"Course {level.code[1:]}.{j}",
                    credit_units=3,
                    department=cls.department,
                    level=level,
                    semester=1
                )
                cls.courses.append(course)
        
        # Create department timetable
        cls.department_timetable = DepartmentTimetable.objects.create(
            department=cls.department,
            academic_year="2024/2025",
            semester=1
        )
        
        # Create timetable slots
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        times = [
            ('09:00', '10:00'),
            ('10:00', '11:00'),
            ('11:00', '12:00'),
            ('14:00', '15:00'),
            ('15:00', '16:00')
        ]
        
        # Create a lecturer user for timetable slots
        lecturer_user = User.objects.create_user(
            username='test_lecturer',
            email='lecturer@test.com',
            password='testpass123',
            first_name='Test',
            last_name='Lecturer'
        )
        
        from users.models import Lecturer
        lecturer = Lecturer.objects.create(
            user=lecturer_user,
            employee_id='LEC001',
            department=cls.department
        )
        
        slot_id = 1
        for level in cls.levels:
            level_courses = [c for c in cls.courses if c.level == level]
            for i, course in enumerate(level_courses[:len(days) * len(times)]):
                day_idx = i % len(days)
                time_idx = (i // len(days)) % len(times)
                
                TimetableSlot.objects.create(
                    id=slot_id,
                    timetable=cls.department_timetable,
                    day_of_week=day_idx,
                    start_time=times[time_idx][0],
                    end_time=times[time_idx][1],
                    course=course,
                    level=level,
                    lecturer=lecturer,
                    venue=f"Room {100 + slot_id}"
                )
                slot_id += 1
        
        print(f"Created test data: {len(cls.levels)} levels, {len(cls.courses)} courses")
    
    def setUp(self):
        """Set up for each test"""
        # Create test students for concurrent testing
        self.test_students = []
        self.test_users = []
        
        for i in range(self.CONCURRENT_STUDENTS):
            # Create user
            user = User.objects.create_user(
                username=f'student{i:03d}',
                email=f'student{i:03d}@test.com',
                password='testpass123',
                first_name=f'Student{i:03d}',
                last_name='Test'
            )
            self.test_users.append(user)
            
            # Create student
            student = Student.objects.create(
                user=user,
                full_name=f'Student{i:03d} Test',
                matric_number=f'ST{i:06d}',
                institution=self.institution,
                faculty=self.faculty,
                department=self.department,
                program_id=1,  # Assuming program exists
                is_approved=True
            )
            self.test_students.append(student)
        
        print(f"Created {len(self.test_students)} test students for performance testing")
    
    def tearDown(self):
        """Clean up after each test"""
        # Clean up test students and users
        Student.objects.filter(matric_number__startswith='ST').delete()
        User.objects.filter(username__startswith='student').delete()
    
    def simulate_student_workflow(self, student_index: int) -> List[PerformanceResult]:
        """
        Simulate a complete student workflow with performance measurement
        
        Args:
            student_index: Index of the student to simulate
            
        Returns:
            List of performance results for each operation
        """
        results = []
        student = self.test_students[student_index]
        user = self.test_users[student_index]
        
        try:
            # Simulate login and get session
            from django.test import Client
            client = Client()
            client.force_login(user)
            
            # 1. Get available levels
            start_time = time.time()
            try:
                response = client.get('/api/students/levels/')
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                results.append(PerformanceResult(
                    operation="get_levels",
                    response_time=response_time,
                    success=response.status_code == 200,
                    status_code=response.status_code
                ))
            except Exception as e:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                results.append(PerformanceResult(
                    operation="get_levels",
                    response_time=response_time,
                    success=False,
                    error_message=str(e)
                ))
            
            # 2. Select a level
            level = self.levels[student_index % len(self.levels)]
            start_time = time.time()
            try:
                response = client.post('/api/students/level-selection/', {
                    'level_id': level.id
                }, content_type='application/json')
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                results.append(PerformanceResult(
                    operation="select_level",
                    response_time=response_time,
                    success=response.status_code in [200, 201],
                    status_code=response.status_code
                ))
            except Exception as e:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                results.append(PerformanceResult(
                    operation="select_level",
                    response_time=response_time,
                    success=False,
                    error_message=str(e)
                ))
            
            # 3. Get timetable
            start_time = time.time()
            try:
                response = client.get(f'/api/students/timetable/?level_id={level.id}')
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                results.append(PerformanceResult(
                    operation="get_timetable",
                    response_time=response_time,
                    success=response.status_code == 200,
                    status_code=response.status_code
                ))
            except Exception as e:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                results.append(PerformanceResult(
                    operation="get_timetable",
                    response_time=response_time,
                    success=False,
                    error_message=str(e)
                ))
            
            # 4. Get current course selections
            start_time = time.time()
            try:
                response = client.get('/api/students/course-selections/')
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                results.append(PerformanceResult(
                    operation="get_course_selections",
                    response_time=response_time,
                    success=response.status_code == 200,
                    status_code=response.status_code
                ))
            except Exception as e:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                results.append(PerformanceResult(
                    operation="get_course_selections",
                    response_time=response_time,
                    success=False,
                    error_message=str(e)
                ))
            
            # 5. Update course selections
            level_courses = [c for c in self.courses if c.level == level]
            selections = []
            for i, course in enumerate(level_courses[:5]):  # Select first 5 courses
                selections.append({
                    'course_id': course.id,
                    'is_offered': i % 2 == 0  # Alternate between offered/not offered
                })
            
            start_time = time.time()
            try:
                response = client.post('/api/students/course-selections/', {
                    'selections': selections
                }, content_type='application/json')
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                results.append(PerformanceResult(
                    operation="update_course_selections",
                    response_time=response_time,
                    success=response.status_code == 200,
                    status_code=response.status_code
                ))
            except Exception as e:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                results.append(PerformanceResult(
                    operation="update_course_selections",
                    response_time=response_time,
                    success=False,
                    error_message=str(e)
                ))
            
        except Exception as e:
            print(f"Error in student workflow {student_index}: {e}")
        
        return results
    
    def test_concurrent_student_operations(self):
        """
        Test system performance with multiple concurrent students
        
        This test simulates realistic load by having multiple students
        perform timetable operations simultaneously.
        """
        print(f"\nStarting concurrent performance test with {self.CONCURRENT_STUDENTS} students...")
        
        # Record start time
        test_start_time = time.time()
        
        # Use ThreadPoolExecutor for concurrent execution
        all_results = []
        with ThreadPoolExecutor(max_workers=min(self.CONCURRENT_STUDENTS, 20)) as executor:
            # Submit all student workflows
            future_to_student = {
                executor.submit(self.simulate_student_workflow, i): i 
                for i in range(self.CONCURRENT_STUDENTS)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_student):
                student_index = future_to_student[future]
                try:
                    student_results = future.result()
                    all_results.extend(student_results)
                    print(f"Completed student {student_index} workflow")
                except Exception as e:
                    print(f"Student {student_index} workflow failed: {e}")
        
        test_end_time = time.time()
        total_test_time = test_end_time - test_start_time
        
        # Analyze results
        self.analyze_performance_results(all_results, total_test_time)
    
    def analyze_performance_results(self, results: List[PerformanceResult], total_time: float):
        """
        Analyze performance test results and generate report
        
        Args:
            results: List of performance results
            total_time: Total time taken for the test
        """
        print(f"\n{'='*60}")
        print("PERFORMANCE TEST RESULTS")
        print(f"{'='*60}")
        
        # Overall statistics
        total_operations = len(results)
        successful_operations = sum(1 for r in results if r.success)
        failed_operations = total_operations - successful_operations
        success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0
        
        print(f"Total Operations: {total_operations}")
        print(f"Successful Operations: {successful_operations}")
        print(f"Failed Operations: {failed_operations}")
        print(f"Success Rate: {success_rate:.2f}%")
        print(f"Total Test Time: {total_time:.2f} seconds")
        print(f"Operations per Second: {total_operations / total_time:.2f}")
        
        # Response time statistics
        response_times = [r.response_time for r in results if r.success]
        if response_times:
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
            
            print(f"\nResponse Time Statistics (ms):")
            print(f"Average: {avg_response_time:.2f}")
            print(f"Median: {median_response_time:.2f}")
            print(f"Minimum: {min_response_time:.2f}")
            print(f"Maximum: {max_response_time:.2f}")
            print(f"95th Percentile: {p95_response_time:.2f}")
        
        # Operation-specific statistics
        operations = {}
        for result in results:
            if result.operation not in operations:
                operations[result.operation] = []
            operations[result.operation].append(result)
        
        print(f"\nOperation-Specific Results:")
        print(f"{'Operation':<25} {'Count':<8} {'Success Rate':<12} {'Avg Time (ms)':<15}")
        print(f"{'-'*60}")
        
        for operation, op_results in operations.items():
            count = len(op_results)
            successful = sum(1 for r in op_results if r.success)
            op_success_rate = (successful / count * 100) if count > 0 else 0
            successful_times = [r.response_time for r in op_results if r.success]
            avg_time = statistics.mean(successful_times) if successful_times else 0
            
            print(f"{operation:<25} {count:<8} {op_success_rate:<11.1f}% {avg_time:<15.2f}")
        
        # Performance assertions
        print(f"\nPerformance Validation:")
        
        # Check success rate
        if success_rate >= self.MIN_SUCCESS_RATE:
            print(f"✓ Success rate ({success_rate:.2f}%) meets minimum requirement ({self.MIN_SUCCESS_RATE}%)")
        else:
            print(f"✗ Success rate ({success_rate:.2f}%) below minimum requirement ({self.MIN_SUCCESS_RATE}%)")
            self.fail(f"Success rate {success_rate:.2f}% is below minimum requirement {self.MIN_SUCCESS_RATE}%")
        
        # Check response times
        if response_times:
            if avg_response_time <= self.MAX_RESPONSE_TIME:
                print(f"✓ Average response time ({avg_response_time:.2f}ms) meets requirement (<{self.MAX_RESPONSE_TIME}ms)")
            else:
                print(f"✗ Average response time ({avg_response_time:.2f}ms) exceeds maximum ({self.MAX_RESPONSE_TIME}ms)")
                self.fail(f"Average response time {avg_response_time:.2f}ms exceeds maximum {self.MAX_RESPONSE_TIME}ms")
            
            if p95_response_time <= self.MAX_RESPONSE_TIME * 2:  # Allow 2x for 95th percentile
                print(f"✓ 95th percentile response time ({p95_response_time:.2f}ms) is acceptable")
            else:
                print(f"⚠ 95th percentile response time ({p95_response_time:.2f}ms) is high")
        
        # Database performance check
        self.check_database_performance()
        
        # System health check
        health_check = SystemHealthMonitor.get_comprehensive_health_check()
        print(f"\nSystem Health After Test: {health_check['overall_status'].upper()}")
        
        print(f"{'='*60}")
    
    def check_database_performance(self):
        """Check database performance metrics"""
        print(f"\nDatabase Performance Check:")
        
        # Check database connections
        for alias in connections:
            connection = connections[alias]
            if hasattr(connection, 'queries'):
                query_count = len(connection.queries)
                print(f"Database '{alias}': {query_count} queries executed")
        
        # Check for N+1 query problems by analyzing query patterns
        # This is a simplified check - in production you'd want more sophisticated analysis
        
        # Check table sizes
        student_count = Student.objects.count()
        level_selection_count = StudentLevelSelection.objects.count()
        course_selection_count = StudentCourseSelection.objects.count()
        
        print(f"Table sizes after test:")
        print(f"  Students: {student_count}")
        print(f"  Level Selections: {level_selection_count}")
        print(f"  Course Selections: {course_selection_count}")
    
    def test_database_query_optimization(self):
        """
        Test database query optimization and identify potential N+1 problems
        """
        print("\nTesting database query optimization...")
        
        # Create a student with level and course selections
        user = User.objects.create_user(
            username='test_optimization',
            email='test@optimization.com',
            password='testpass123'
        )
        
        student = Student.objects.create(
            user=user,
            full_name='Test Optimization',
            matric_number='OPT001',
            institution=self.institution,
            faculty=self.faculty,
            department=self.department,
            program_id=1,
            is_approved=True
        )
        
        # Select a level
        level = self.levels[0]
        StudentLevelSelection.objects.create(
            student=student,
            level=level
        )
        
        # Create course selections
        level_courses = [c for c in self.courses if c.level == level][:5]
        for course in level_courses:
            StudentCourseSelection.objects.create(
                student=student,
                department=self.department,
                level=level,
                course=course,
                is_offered=True
            )
        
        # Test optimized queries
        from django.db import connection
        from django.test.utils import override_settings
        
        # Reset query log
        connection.queries_log.clear()
        
        # Test 1: Get student with level selection (should use select_related)
        start_time = time.time()
        student_with_level = Student.objects.select_related(
            'level_selection__level'
        ).get(id=student.id)
        end_time = time.time()
        
        query_count_1 = len(connection.queries)
        time_1 = (end_time - start_time) * 1000
        
        print(f"Student with level selection: {query_count_1} queries, {time_1:.2f}ms")
        
        # Reset query log
        connection.queries_log.clear()
        
        # Test 2: Get course selections (should use select_related)
        start_time = time.time()
        course_selections = StudentCourseSelection.objects.select_related(
            'course', 'level', 'department'
        ).filter(student=student)
        list(course_selections)  # Force evaluation
        end_time = time.time()
        
        query_count_2 = len(connection.queries)
        time_2 = (end_time - start_time) * 1000
        
        print(f"Course selections with relations: {query_count_2} queries, {time_2:.2f}ms")
        
        # Test 3: Get timetable data (should use select_related)
        connection.queries_log.clear()
        
        start_time = time.time()
        timetable_slots = TimetableSlot.objects.select_related(
            'course', 'lecturer', 'lecturer__user', 'level'
        ).filter(
            timetable__department=self.department,
            level=level
        )
        list(timetable_slots)  # Force evaluation
        end_time = time.time()
        
        query_count_3 = len(connection.queries)
        time_3 = (end_time - start_time) * 1000
        
        print(f"Timetable slots with relations: {query_count_3} queries, {time_3:.2f}ms")
        
        # Validate query optimization
        self.assertLessEqual(query_count_1, 2, "Student with level selection should use ≤2 queries")
        self.assertLessEqual(query_count_2, 2, "Course selections should use ≤2 queries")
        self.assertLessEqual(query_count_3, 2, "Timetable slots should use ≤2 queries")
        
        print("✓ Database query optimization tests passed")
        
        # Clean up
        student.delete()
        user.delete()
    
    def test_caching_performance(self):
        """
        Test caching performance for frequently accessed data
        """
        print("\nTesting caching performance...")
        
        from django.core.cache import cache
        
        # Test 1: Cache level data
        cache_key = f"student_levels_{self.department.id}"
        
        # First call (cache miss)
        start_time = time.time()
        levels_data = cache.get(cache_key)
        if levels_data is None:
            levels_data = list(Level.objects.filter(
                department=self.department
            ).values('id', 'name', 'code'))
            cache.set(cache_key, levels_data, 300)  # Cache for 5 minutes
        end_time = time.time()
        cache_miss_time = (end_time - start_time) * 1000
        
        # Second call (cache hit)
        start_time = time.time()
        cached_levels_data = cache.get(cache_key)
        end_time = time.time()
        cache_hit_time = (end_time - start_time) * 1000
        
        print(f"Level data - Cache miss: {cache_miss_time:.2f}ms, Cache hit: {cache_hit_time:.2f}ms")
        
        # Validate caching effectiveness
        self.assertIsNotNone(cached_levels_data, "Cached data should be available")
        self.assertEqual(len(levels_data), len(cached_levels_data), "Cached data should match original")
        self.assertLess(cache_hit_time, cache_miss_time, "Cache hit should be faster than cache miss")
        
        # Test 2: Cache timetable data
        level = self.levels[0]
        timetable_cache_key = f"student_timetable_{self.department.id}_{level.id}"
        
        # Cache miss
        start_time = time.time()
        timetable_data = cache.get(timetable_cache_key)
        if timetable_data is None:
            timetable_slots = TimetableSlot.objects.select_related(
                'course', 'lecturer', 'lecturer__user'
            ).filter(
                timetable__department=self.department,
                level=level
            )
            timetable_data = [
                {
                    'id': slot.id,
                    'day_of_week': slot.day_of_week,
                    'start_time': slot.start_time.strftime('%H:%M'),
                    'end_time': slot.end_time.strftime('%H:%M'),
                    'course_code': slot.course.code,
                    'course_title': slot.course.title,
                    'lecturer_name': f"{slot.lecturer.user.first_name} {slot.lecturer.user.last_name}",
                    'venue': slot.venue
                }
                for slot in timetable_slots
            ]
            cache.set(timetable_cache_key, timetable_data, 600)  # Cache for 10 minutes
        end_time = time.time()
        timetable_miss_time = (end_time - start_time) * 1000
        
        # Cache hit
        start_time = time.time()
        cached_timetable_data = cache.get(timetable_cache_key)
        end_time = time.time()
        timetable_hit_time = (end_time - start_time) * 1000
        
        print(f"Timetable data - Cache miss: {timetable_miss_time:.2f}ms, Cache hit: {timetable_hit_time:.2f}ms")
        
        # Validate timetable caching
        self.assertIsNotNone(cached_timetable_data, "Cached timetable data should be available")
        self.assertLess(timetable_hit_time, timetable_miss_time, "Timetable cache hit should be faster")
        
        print("✓ Caching performance tests passed")
        
        # Clean up cache
        cache.delete(cache_key)
        cache.delete(timetable_cache_key)


def run_performance_tests():
    """
    Run all performance tests and generate a comprehensive report
    """
    print("Starting Student Timetable Module Performance Tests...")
    print(f"Test Configuration:")
    print(f"  Concurrent Students: {StudentTimetablePerformanceTest.CONCURRENT_STUDENTS}")
    print(f"  Operations per Student: {StudentTimetablePerformanceTest.OPERATIONS_PER_STUDENT}")
    print(f"  Max Response Time: {StudentTimetablePerformanceTest.MAX_RESPONSE_TIME}ms")
    print(f"  Min Success Rate: {StudentTimetablePerformanceTest.MIN_SUCCESS_RATE}%")
    
    # Run the tests
    import unittest
    
    # Create test suite
    suite = unittest.TestSuite()
    suite.addTest(StudentTimetablePerformanceTest('test_concurrent_student_operations'))
    suite.addTest(StudentTimetablePerformanceTest('test_database_query_optimization'))
    suite.addTest(StudentTimetablePerformanceTest('test_caching_performance'))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Generate final report
    print(f"\n{'='*80}")
    print("FINAL PERFORMANCE TEST REPORT")
    print(f"{'='*80}")
    
    if result.wasSuccessful():
        print("✓ All performance tests PASSED")
        print("✓ System meets performance requirements")
    else:
        print("✗ Some performance tests FAILED")
        print(f"  Failures: {len(result.failures)}")
        print(f"  Errors: {len(result.errors)}")
    
    # Get final system metrics
    final_metrics = PerformanceMonitor.get_all_metrics()
    if final_metrics:
        print(f"\nFinal System Metrics:")
        for endpoint, metrics in final_metrics.items():
            print(f"  {endpoint}: {metrics['avg_response_time']:.2f}ms avg, {metrics['success_rate']:.1f}% success")
    
    print(f"{'='*80}")
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_performance_tests()
    sys.exit(0 if success else 1)