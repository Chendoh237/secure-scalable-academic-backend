"""
System Monitoring and Alerting for Student Timetable Module

This module provides comprehensive monitoring, performance tracking, and alerting
capabilities for the Student Timetable Module to ensure system reliability and
performance.
"""

import logging
import time
import functools
from typing import Dict, Any, Optional, List, Callable
from django.utils import timezone
from django.core.cache import cache
from django.db import connection
from django.conf import settings
from django.core.mail import send_mail
from datetime import timedelta
import json
import threading
from collections import defaultdict, deque

from students.models import Student, StudentLevelSelection, StudentCourseSelection, CourseSelectionAuditLog
from courses.models import TimetableSlot, Level, Course
from institutions.models import Department

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    Performance monitoring for API endpoints and database operations
    """
    
    # Thread-safe storage for metrics
    _metrics = defaultdict(lambda: {
        'response_times': deque(maxlen=1000),  # Keep last 1000 measurements
        'error_count': 0,
        'success_count': 0,
        'total_requests': 0
    })
    _lock = threading.Lock()
    
    @classmethod
    def record_api_call(cls, endpoint: str, response_time: float, success: bool = True):
        """Record API call metrics"""
        with cls._lock:
            metrics = cls._metrics[endpoint]
            metrics['response_times'].append(response_time)
            metrics['total_requests'] += 1
            
            if success:
                metrics['success_count'] += 1
            else:
                metrics['error_count'] += 1
    
    @classmethod
    def get_endpoint_metrics(cls, endpoint: str) -> Dict[str, Any]:
        """Get metrics for a specific endpoint"""
        with cls._lock:
            metrics = cls._metrics[endpoint]
            response_times = list(metrics['response_times'])
            
            if not response_times:
                return {
                    'endpoint': endpoint,
                    'total_requests': 0,
                    'avg_response_time': 0,
                    'min_response_time': 0,
                    'max_response_time': 0,
                    'success_rate': 0,
                    'error_rate': 0
                }
            
            avg_time = sum(response_times) / len(response_times)
            min_time = min(response_times)
            max_time = max(response_times)
            total_requests = metrics['total_requests']
            success_rate = (metrics['success_count'] / total_requests * 100) if total_requests > 0 else 0
            error_rate = (metrics['error_count'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'endpoint': endpoint,
                'total_requests': total_requests,
                'avg_response_time': round(avg_time, 3),
                'min_response_time': round(min_time, 3),
                'max_response_time': round(max_time, 3),
                'success_rate': round(success_rate, 2),
                'error_rate': round(error_rate, 2),
                'recent_requests': len(response_times)
            }
    
    @classmethod
    def get_all_metrics(cls) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all monitored endpoints"""
        with cls._lock:
            return {endpoint: cls.get_endpoint_metrics(endpoint) for endpoint in cls._metrics.keys()}
    
    @classmethod
    def clear_metrics(cls):
        """Clear all metrics (for testing or maintenance)"""
        with cls._lock:
            cls._metrics.clear()


def monitor_performance(endpoint_name: str):
    """
    Decorator to monitor API endpoint performance
    
    Usage:
    @monitor_performance('student_course_selections')
    def my_api_view(request):
        # API logic here
        pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                
                # Check if result indicates an error (for DRF responses)
                if hasattr(result, 'status_code') and result.status_code >= 400:
                    success = False
                
                return result
            except Exception as e:
                success = False
                logger.error(f"Error in {endpoint_name}: {e}")
                raise
            finally:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                PerformanceMonitor.record_api_call(endpoint_name, response_time, success)
                
                # Log slow requests
                if response_time > 1000:  # Log requests slower than 1 second
                    logger.warning(f"Slow request detected: {endpoint_name} took {response_time:.2f}ms")
        
        return wrapper
    return decorator


class SystemHealthMonitor:
    """
    System health monitoring for the Student Timetable Module
    """
    
    @staticmethod
    def check_database_health() -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            
            # Test basic connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            # Test student timetable specific tables
            student_count = Student.objects.count()
            level_selection_count = StudentLevelSelection.objects.count()
            course_selection_count = StudentCourseSelection.objects.count()
            audit_log_count = CourseSelectionAuditLog.objects.count()
            
            end_time = time.time()
            query_time = (end_time - start_time) * 1000
            
            return {
                'status': 'healthy',
                'query_time_ms': round(query_time, 2),
                'student_count': student_count,
                'level_selection_count': level_selection_count,
                'course_selection_count': course_selection_count,
                'audit_log_count': audit_log_count,
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    @staticmethod
    def check_cache_health() -> Dict[str, Any]:
        """Check cache connectivity and performance"""
        try:
            start_time = time.time()
            
            # Test cache operations
            test_key = 'health_check_test'
            test_value = f'test_value_{int(time.time())}'
            
            cache.set(test_key, test_value, 10)
            retrieved_value = cache.get(test_key)
            cache.delete(test_key)
            
            end_time = time.time()
            cache_time = (end_time - start_time) * 1000
            
            if retrieved_value == test_value:
                return {
                    'status': 'healthy',
                    'cache_time_ms': round(cache_time, 2),
                    'timestamp': timezone.now().isoformat()
                }
            else:
                return {
                    'status': 'degraded',
                    'error': 'Cache value mismatch',
                    'timestamp': timezone.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    @staticmethod
    def check_api_health() -> Dict[str, Any]:
        """Check API endpoint health based on recent performance"""
        try:
            all_metrics = PerformanceMonitor.get_all_metrics()
            
            if not all_metrics:
                return {
                    'status': 'unknown',
                    'message': 'No API metrics available',
                    'timestamp': timezone.now().isoformat()
                }
            
            # Analyze metrics for health indicators
            unhealthy_endpoints = []
            degraded_endpoints = []
            
            for endpoint, metrics in all_metrics.items():
                # Check error rate
                if metrics['error_rate'] > 10:  # More than 10% errors
                    unhealthy_endpoints.append(f"{endpoint} (error rate: {metrics['error_rate']}%)")
                elif metrics['error_rate'] > 5:  # More than 5% errors
                    degraded_endpoints.append(f"{endpoint} (error rate: {metrics['error_rate']}%)")
                
                # Check response time
                if metrics['avg_response_time'] > 2000:  # Slower than 2 seconds
                    unhealthy_endpoints.append(f"{endpoint} (avg response: {metrics['avg_response_time']}ms)")
                elif metrics['avg_response_time'] > 1000:  # Slower than 1 second
                    degraded_endpoints.append(f"{endpoint} (avg response: {metrics['avg_response_time']}ms)")
            
            if unhealthy_endpoints:
                status = 'unhealthy'
            elif degraded_endpoints:
                status = 'degraded'
            else:
                status = 'healthy'
            
            return {
                'status': status,
                'total_endpoints': len(all_metrics),
                'unhealthy_endpoints': unhealthy_endpoints,
                'degraded_endpoints': degraded_endpoints,
                'timestamp': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }
    
    @staticmethod
    def get_comprehensive_health_check() -> Dict[str, Any]:
        """Get comprehensive system health check"""
        database_health = SystemHealthMonitor.check_database_health()
        cache_health = SystemHealthMonitor.check_cache_health()
        api_health = SystemHealthMonitor.check_api_health()
        
        # Determine overall status
        statuses = [database_health['status'], cache_health['status'], api_health['status']]
        
        if 'unhealthy' in statuses:
            overall_status = 'unhealthy'
        elif 'degraded' in statuses:
            overall_status = 'degraded'
        elif 'unknown' in statuses:
            overall_status = 'unknown'
        else:
            overall_status = 'healthy'
        
        return {
            'overall_status': overall_status,
            'components': {
                'database': database_health,
                'cache': cache_health,
                'api': api_health
            },
            'timestamp': timezone.now().isoformat()
        }


class AlertManager:
    """
    Alert management for critical system failures and performance issues
    """
    
    # Alert thresholds
    CRITICAL_ERROR_RATE_THRESHOLD = 20  # 20% error rate
    WARNING_ERROR_RATE_THRESHOLD = 10   # 10% error rate
    CRITICAL_RESPONSE_TIME_THRESHOLD = 5000  # 5 seconds
    WARNING_RESPONSE_TIME_THRESHOLD = 2000   # 2 seconds
    
    @staticmethod
    def check_and_send_alerts():
        """Check system health and send alerts if necessary"""
        try:
            health_check = SystemHealthMonitor.get_comprehensive_health_check()
            alerts = []
            
            # Check overall system health
            if health_check['overall_status'] == 'unhealthy':
                alerts.append({
                    'level': 'CRITICAL',
                    'message': 'Student Timetable Module system is unhealthy',
                    'details': health_check
                })
            elif health_check['overall_status'] == 'degraded':
                alerts.append({
                    'level': 'WARNING',
                    'message': 'Student Timetable Module system performance is degraded',
                    'details': health_check
                })
            
            # Check specific components
            components = health_check['components']
            
            # Database alerts
            if components['database']['status'] == 'unhealthy':
                alerts.append({
                    'level': 'CRITICAL',
                    'message': 'Database connectivity issues detected',
                    'details': components['database']
                })
            
            # Cache alerts
            if components['cache']['status'] == 'unhealthy':
                alerts.append({
                    'level': 'WARNING',
                    'message': 'Cache system issues detected',
                    'details': components['cache']
                })
            
            # API performance alerts
            api_metrics = PerformanceMonitor.get_all_metrics()
            for endpoint, metrics in api_metrics.items():
                if metrics['error_rate'] >= AlertManager.CRITICAL_ERROR_RATE_THRESHOLD:
                    alerts.append({
                        'level': 'CRITICAL',
                        'message': f'High error rate detected for {endpoint}',
                        'details': metrics
                    })
                elif metrics['error_rate'] >= AlertManager.WARNING_ERROR_RATE_THRESHOLD:
                    alerts.append({
                        'level': 'WARNING',
                        'message': f'Elevated error rate detected for {endpoint}',
                        'details': metrics
                    })
                
                if metrics['avg_response_time'] >= AlertManager.CRITICAL_RESPONSE_TIME_THRESHOLD:
                    alerts.append({
                        'level': 'CRITICAL',
                        'message': f'Very slow response times detected for {endpoint}',
                        'details': metrics
                    })
                elif metrics['avg_response_time'] >= AlertManager.WARNING_RESPONSE_TIME_THRESHOLD:
                    alerts.append({
                        'level': 'WARNING',
                        'message': f'Slow response times detected for {endpoint}',
                        'details': metrics
                    })
            
            # Send alerts
            for alert in alerts:
                AlertManager._send_alert(alert)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking and sending alerts: {e}")
            return []
    
    @staticmethod
    def _send_alert(alert: Dict[str, Any]):
        """Send an alert notification"""
        try:
            # Log the alert
            log_level = logging.CRITICAL if alert['level'] == 'CRITICAL' else logging.WARNING
            logger.log(log_level, f"ALERT [{alert['level']}]: {alert['message']}")
            
            # Store alert in cache for dashboard display
            cache_key = f"alert_{int(time.time())}"
            cache.set(cache_key, alert, 3600)  # Store for 1 hour
            
            # Send email alert if configured
            if hasattr(settings, 'ALERT_EMAIL_RECIPIENTS') and settings.ALERT_EMAIL_RECIPIENTS:
                try:
                    subject = f"[{alert['level']}] Student Timetable Module Alert"
                    message = f"""
Alert Level: {alert['level']}
Message: {alert['message']}
Timestamp: {timezone.now().isoformat()}

Details:
{json.dumps(alert['details'], indent=2)}
                    """
                    
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=settings.ALERT_EMAIL_RECIPIENTS,
                        fail_silently=True
                    )
                except Exception as e:
                    logger.error(f"Failed to send email alert: {e}")
            
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
    
    @staticmethod
    def get_recent_alerts(hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent alerts from cache"""
        try:
            alerts = []
            # This is a simplified implementation
            # In production, you'd want to use a proper alert storage system
            
            # For now, we'll return a placeholder
            return alerts
        except Exception as e:
            logger.error(f"Error getting recent alerts: {e}")
            return []


class MetricsCollector:
    """
    Collect and aggregate system metrics for reporting and analysis
    """
    
    @staticmethod
    def collect_daily_metrics() -> Dict[str, Any]:
        """Collect daily metrics for the Student Timetable Module"""
        try:
            today = timezone.now().date()
            yesterday = today - timedelta(days=1)
            
            # Student activity metrics
            new_students_today = Student.objects.filter(created_at__date=today).count()
            total_students = Student.objects.count()
            
            # Level selection metrics
            level_selections_today = StudentLevelSelection.objects.filter(
                selected_at__date=today
            ).count()
            total_level_selections = StudentLevelSelection.objects.count()
            
            # Course selection metrics
            course_selections_today = StudentCourseSelection.objects.filter(
                created_at__date=today
            ).count()
            course_updates_today = StudentCourseSelection.objects.filter(
                updated_at__date=today,
                created_at__date__lt=today
            ).count()
            total_course_selections = StudentCourseSelection.objects.count()
            
            # Audit log metrics
            audit_logs_today = CourseSelectionAuditLog.objects.filter(
                timestamp__date=today
            ).count()
            total_audit_logs = CourseSelectionAuditLog.objects.count()
            
            # Performance metrics
            api_metrics = PerformanceMonitor.get_all_metrics()
            
            return {
                'date': today.isoformat(),
                'student_metrics': {
                    'new_students_today': new_students_today,
                    'total_students': total_students
                },
                'level_selection_metrics': {
                    'selections_today': level_selections_today,
                    'total_selections': total_level_selections
                },
                'course_selection_metrics': {
                    'new_selections_today': course_selections_today,
                    'updates_today': course_updates_today,
                    'total_selections': total_course_selections
                },
                'audit_metrics': {
                    'logs_today': audit_logs_today,
                    'total_logs': total_audit_logs
                },
                'performance_metrics': api_metrics,
                'collected_at': timezone.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error collecting daily metrics: {e}")
            return {
                'error': str(e),
                'collected_at': timezone.now().isoformat()
            }


# Convenience functions for easy integration
def get_system_health():
    """Get current system health status"""
    return SystemHealthMonitor.get_comprehensive_health_check()


def get_performance_metrics():
    """Get current performance metrics"""
    return PerformanceMonitor.get_all_metrics()


def check_alerts():
    """Check and send alerts if necessary"""
    return AlertManager.check_and_send_alerts()


def collect_metrics():
    """Collect current system metrics"""
    return MetricsCollector.collect_daily_metrics()


# Middleware for automatic performance monitoring
class StudentTimetableMonitoringMiddleware:
    """
    Middleware to automatically monitor Student Timetable Module API endpoints
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check if this is a student timetable API request
        if self._is_student_timetable_request(request):
            start_time = time.time()
            
            try:
                response = self.get_response(request)
                success = response.status_code < 400
            except Exception as e:
                response = None
                success = False
                logger.error(f"Error in student timetable request: {e}")
                raise
            finally:
                end_time = time.time()
                response_time = (end_time - start_time) * 1000
                
                endpoint_name = self._get_endpoint_name(request)
                PerformanceMonitor.record_api_call(endpoint_name, response_time, success)
            
            return response
        else:
            return self.get_response(request)
    
    def _is_student_timetable_request(self, request):
        """Check if request is for student timetable endpoints"""
        path = request.path
        return (
            '/students/levels/' in path or
            '/students/level-selection/' in path or
            '/students/timetable/' in path or
            '/students/course-selections/' in path or
            '/admin/audit/' in path
        )
    
    def _get_endpoint_name(self, request):
        """Get endpoint name for monitoring"""
        path = request.path
        method = request.method
        
        if '/students/levels/' in path:
            return f"{method}_student_levels"
        elif '/students/level-selection/' in path:
            return f"{method}_level_selection"
        elif '/students/timetable/' in path:
            return f"{method}_student_timetable"
        elif '/students/course-selections/' in path:
            return f"{method}_course_selections"
        elif '/admin/audit/' in path:
            return f"{method}_audit_trail"
        else:
            return f"{method}_unknown_endpoint"