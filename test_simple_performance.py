#!/usr/bin/env python
"""
Simple Performance Testing Script for Student Timetable Module

This script tests basic performance characteristics without full Django setup.
"""

import time
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
import requests
import json


class SimplePerformanceTest:
    """
    Simple performance test using HTTP requests
    """
    
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        
        # Test configuration
        self.CONCURRENT_USERS = 20
        self.REQUESTS_PER_USER = 5
        self.MAX_RESPONSE_TIME = 2000  # 2 seconds
        self.MIN_SUCCESS_RATE = 95
    
    def simulate_user_requests(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Simulate a user making multiple requests
        
        Args:
            user_id: User identifier
            
        Returns:
            List of performance results
        """
        results = []
        
        # Simulate different API endpoints
        endpoints = [
            '/api/students/levels/',
            '/api/students/timetable/',
            '/api/students/course-selections/',
        ]
        
        for i in range(self.REQUESTS_PER_USER):
            endpoint = endpoints[i % len(endpoints)]
            
            start_time = time.time()
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                end_time = time.time()
                
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                success = response.status_code < 400
                
                results.append({
                    'user_id': user_id,
                    'endpoint': endpoint,
                    'response_time': response_time,
                    'status_code': response.status_code,
                    'success': success
                })
                
            except Exception as e:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                results.append({
                    'user_id': user_id,
                    'endpoint': endpoint,
                    'response_time': response_time,
                    'status_code': 0,
                    'success': False,
                    'error': str(e)
                })
        
        return results
    
    def run_concurrent_test(self) -> List[Dict[str, Any]]:
        """
        Run concurrent performance test
        
        Returns:
            List of all performance results
        """
        print(f"Starting concurrent performance test...")
        print(f"Concurrent users: {self.CONCURRENT_USERS}")
        print(f"Requests per user: {self.REQUESTS_PER_USER}")
        print(f"Total requests: {self.CONCURRENT_USERS * self.REQUESTS_PER_USER}")
        
        all_results = []
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.CONCURRENT_USERS) as executor:
            # Submit all user simulations
            future_to_user = {
                executor.submit(self.simulate_user_requests, user_id): user_id
                for user_id in range(self.CONCURRENT_USERS)
            }
            
            # Collect results
            for future in as_completed(future_to_user):
                user_id = future_to_user[future]
                try:
                    user_results = future.result()
                    all_results.extend(user_results)
                    print(f"Completed user {user_id}")
                except Exception as e:
                    print(f"User {user_id} failed: {e}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        self.analyze_results(all_results, total_time)
        return all_results
    
    def analyze_results(self, results: List[Dict[str, Any]], total_time: float):
        """
        Analyze performance results
        
        Args:
            results: List of performance results
            total_time: Total test execution time
        """
        print(f"\n{'='*60}")
        print("PERFORMANCE TEST RESULTS")
        print(f"{'='*60}")
        
        if not results:
            print("No results to analyze")
            return
        
        # Overall statistics
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r['success'])
        failed_requests = total_requests - successful_requests
        success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 0
        
        print(f"Total Requests: {total_requests}")
        print(f"Successful Requests: {successful_requests}")
        print(f"Failed Requests: {failed_requests}")
        print(f"Success Rate: {success_rate:.2f}%")
        print(f"Total Test Time: {total_time:.2f} seconds")
        print(f"Requests per Second: {total_requests / total_time:.2f}")
        
        # Response time statistics
        successful_results = [r for r in results if r['success']]
        if successful_results:
            response_times = [r['response_time'] for r in successful_results]
            
            avg_response_time = statistics.mean(response_times)
            median_response_time = statistics.median(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            
            print(f"\nResponse Time Statistics (ms):")
            print(f"Average: {avg_response_time:.2f}")
            print(f"Median: {median_response_time:.2f}")
            print(f"Minimum: {min_response_time:.2f}")
            print(f"Maximum: {max_response_time:.2f}")
            
            if len(response_times) >= 20:
                p95_response_time = statistics.quantiles(response_times, n=20)[18]
                print(f"95th Percentile: {p95_response_time:.2f}")
        
        # Endpoint-specific statistics
        endpoints = {}
        for result in results:
            endpoint = result['endpoint']
            if endpoint not in endpoints:
                endpoints[endpoint] = []
            endpoints[endpoint].append(result)
        
        print(f"\nEndpoint-Specific Results:")
        print(f"{'Endpoint':<30} {'Count':<8} {'Success Rate':<12} {'Avg Time (ms)':<15}")
        print(f"{'-'*65}")
        
        for endpoint, endpoint_results in endpoints.items():
            count = len(endpoint_results)
            successful = sum(1 for r in endpoint_results if r['success'])
            endpoint_success_rate = (successful / count * 100) if count > 0 else 0
            successful_times = [r['response_time'] for r in endpoint_results if r['success']]
            avg_time = statistics.mean(successful_times) if successful_times else 0
            
            print(f"{endpoint:<30} {count:<8} {endpoint_success_rate:<11.1f}% {avg_time:<15.2f}")
        
        # Performance validation
        print(f"\nPerformance Validation:")
        
        if success_rate >= self.MIN_SUCCESS_RATE:
            print(f"✓ Success rate ({success_rate:.2f}%) meets requirement ({self.MIN_SUCCESS_RATE}%)")
        else:
            print(f"✗ Success rate ({success_rate:.2f}%) below requirement ({self.MIN_SUCCESS_RATE}%)")
        
        if successful_results:
            avg_response_time = statistics.mean([r['response_time'] for r in successful_results])
            if avg_response_time <= self.MAX_RESPONSE_TIME:
                print(f"✓ Average response time ({avg_response_time:.2f}ms) meets requirement (<{self.MAX_RESPONSE_TIME}ms)")
            else:
                print(f"✗ Average response time ({avg_response_time:.2f}ms) exceeds maximum ({self.MAX_RESPONSE_TIME}ms)")
        
        print(f"{'='*60}")
    
    def test_single_endpoint_performance(self, endpoint: str, num_requests: int = 100):
        """
        Test performance of a single endpoint
        
        Args:
            endpoint: API endpoint to test
            num_requests: Number of requests to make
        """
        print(f"\nTesting single endpoint: {endpoint}")
        print(f"Number of requests: {num_requests}")
        
        results = []
        start_time = time.time()
        
        for i in range(num_requests):
            request_start = time.time()
            try:
                response = self.session.get(f"{self.base_url}{endpoint}")
                request_end = time.time()
                
                response_time = (request_end - request_start) * 1000
                success = response.status_code < 400
                
                results.append({
                    'request_id': i,
                    'response_time': response_time,
                    'status_code': response.status_code,
                    'success': success
                })
                
            except Exception as e:
                request_end = time.time()
                response_time = (request_end - request_start) * 1000
                
                results.append({
                    'request_id': i,
                    'response_time': response_time,
                    'status_code': 0,
                    'success': False,
                    'error': str(e)
                })
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Analyze single endpoint results
        successful_results = [r for r in results if r['success']]
        if successful_results:
            response_times = [r['response_time'] for r in successful_results]
            
            print(f"Results for {endpoint}:")
            print(f"  Total requests: {len(results)}")
            print(f"  Successful requests: {len(successful_results)}")
            print(f"  Success rate: {len(successful_results) / len(results) * 100:.2f}%")
            print(f"  Average response time: {statistics.mean(response_times):.2f}ms")
            print(f"  Median response time: {statistics.median(response_times):.2f}ms")
            print(f"  Min response time: {min(response_times):.2f}ms")
            print(f"  Max response time: {max(response_times):.2f}ms")
            print(f"  Total test time: {total_time:.2f}s")
            print(f"  Requests per second: {len(results) / total_time:.2f}")


def run_performance_tests():
    """
    Run performance tests
    """
    print("Student Timetable Module - Simple Performance Tests")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8000", timeout=5)
        print("✓ Server is accessible")
    except requests.exceptions.RequestException as e:
        print(f"✗ Server is not accessible: {e}")
        print("Please start the Django development server first:")
        print("  python manage.py runserver")
        return False
    
    # Create test instance
    test = SimplePerformanceTest()
    
    # Run tests
    try:
        # Test 1: Concurrent user simulation
        print("\n" + "="*60)
        print("TEST 1: Concurrent User Simulation")
        print("="*60)
        test.run_concurrent_test()
        
        # Test 2: Single endpoint performance
        print("\n" + "="*60)
        print("TEST 2: Single Endpoint Performance")
        print("="*60)
        test.test_single_endpoint_performance('/api/students/levels/', 50)
        
        print("\n✓ Performance tests completed successfully")
        return True
        
    except Exception as e:
        print(f"\n✗ Performance tests failed: {e}")
        return False


if __name__ == '__main__':
    success = run_performance_tests()
    exit(0 if success else 1)