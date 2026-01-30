"""
API views for Student Timetable Module monitoring and alerting.

This module provides REST API endpoints for administrators to:
1. Check system health status
2. View performance metrics
3. Get alerts and notifications
4. Monitor system resources
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import json

from students.monitoring import (
    SystemHealthMonitor,
    PerformanceMonitor,
    AlertManager,
    MetricsCollector,
    monitor_performance
)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
@monitor_performance('system_health_check')
def system_health_check(request):
    """
    Get comprehensive system health status.
    
    Returns:
        JSON response with system health information
    """
    try:
        health_check = SystemHealthMonitor.get_comprehensive_health_check()
        return Response(health_check)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get system health: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
@monitor_performance('performance_metrics')
def get_performance_metrics(request):
    """
    Get API performance metrics.
    
    Query Parameters:
        endpoint (str): Filter by specific endpoint
        reset (bool): Reset metrics after retrieval
    """
    try:
        endpoint_filter = request.GET.get('endpoint')
        reset_metrics = request.GET.get('reset', 'false').lower() == 'true'
        
        if endpoint_filter:
            metrics = {
                endpoint_filter: PerformanceMonitor.get_endpoint_metrics(endpoint_filter)
            }
        else:
            metrics = PerformanceMonitor.get_all_metrics()
        
        # Reset metrics if requested
        if reset_metrics:
            PerformanceMonitor.clear_metrics()
        
        return Response({
            'metrics': metrics,
            'timestamp': timezone.now().isoformat(),
            'reset_after_retrieval': reset_metrics
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get performance metrics: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
@monitor_performance('alert_management')
def manage_alerts(request):
    """
    Manage system alerts.
    
    GET: Get recent alerts
    POST: Trigger alert check
    """
    try:
        if request.method == 'GET':
            hours = int(request.GET.get('hours', 24))
            alerts = AlertManager.get_recent_alerts(hours)
            
            return Response({
                'alerts': alerts,
                'hours_range': hours,
                'timestamp': timezone.now().isoformat()
            })
        
        elif request.method == 'POST':
            # Trigger alert check
            alerts = AlertManager.check_and_send_alerts()
            
            return Response({
                'message': 'Alert check completed',
                'alerts_found': len(alerts),
                'alerts': alerts,
                'timestamp': timezone.now().isoformat()
            })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to manage alerts: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
@monitor_performance('system_metrics')
def get_system_metrics(request):
    """
    Get comprehensive system metrics.
    
    Query Parameters:
        days (int): Number of days to include in metrics (default: 1)
    """
    try:
        days = int(request.GET.get('days', 1))
        
        if days == 1:
            # Get daily metrics
            metrics = MetricsCollector.collect_daily_metrics()
        else:
            # For multi-day metrics, we'd need to implement historical data collection
            # For now, return current day metrics with a note
            metrics = MetricsCollector.collect_daily_metrics()
            metrics['note'] = f'Multi-day metrics not yet implemented. Showing current day only.'
        
        return Response(metrics)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get system metrics: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
@monitor_performance('monitoring_dashboard')
def monitoring_dashboard(request):
    """
    Get comprehensive monitoring dashboard data.
    
    Returns all monitoring information in a single response for dashboard display.
    """
    try:
        # Get all monitoring data
        health_check = SystemHealthMonitor.get_comprehensive_health_check()
        performance_metrics = PerformanceMonitor.get_all_metrics()
        system_metrics = MetricsCollector.collect_daily_metrics()
        recent_alerts = AlertManager.get_recent_alerts(24)
        
        # Calculate summary statistics
        total_requests = sum(
            metrics['total_requests'] 
            for metrics in performance_metrics.values()
        )
        
        avg_response_time = (
            sum(
                metrics['avg_response_time'] * metrics['total_requests']
                for metrics in performance_metrics.values()
            ) / total_requests
        ) if total_requests > 0 else 0
        
        overall_error_rate = (
            sum(
                metrics['error_rate'] * metrics['total_requests']
                for metrics in performance_metrics.values()
            ) / total_requests
        ) if total_requests > 0 else 0
        
        dashboard_data = {
            'overview': {
                'system_status': health_check['overall_status'],
                'total_api_requests': total_requests,
                'avg_response_time': round(avg_response_time, 2),
                'overall_error_rate': round(overall_error_rate, 2),
                'active_alerts': len([a for a in recent_alerts if a.get('level') == 'CRITICAL']),
                'timestamp': timezone.now().isoformat()
            },
            'health': health_check,
            'performance': performance_metrics,
            'metrics': system_metrics,
            'alerts': recent_alerts
        }
        
        return Response(dashboard_data)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get dashboard data: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminUser])
def reset_monitoring_data(request):
    """
    Reset monitoring data (admin only).
    
    POST data:
        reset_performance (bool): Reset performance metrics
        reset_alerts (bool): Reset alert history
    """
    try:
        reset_performance = request.data.get('reset_performance', False)
        reset_alerts = request.data.get('reset_alerts', False)
        
        reset_actions = []
        
        if reset_performance:
            PerformanceMonitor.clear_metrics()
            reset_actions.append('performance_metrics')
        
        if reset_alerts:
            # Clear alert cache (simplified implementation)
            # In production, you'd want a more sophisticated alert storage system
            cache.delete_pattern('alert_*')
            reset_actions.append('alert_history')
        
        return Response({
            'message': 'Monitoring data reset completed',
            'reset_actions': reset_actions,
            'timestamp': timezone.now().isoformat()
        })
        
    except Exception as e:
        return Response(
            {'error': f'Failed to reset monitoring data: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminUser])
def monitoring_config(request):
    """
    Get monitoring configuration and thresholds.
    """
    try:
        config = {
            'alert_thresholds': {
                'critical_error_rate': AlertManager.CRITICAL_ERROR_RATE_THRESHOLD,
                'warning_error_rate': AlertManager.WARNING_ERROR_RATE_THRESHOLD,
                'critical_response_time': AlertManager.CRITICAL_RESPONSE_TIME_THRESHOLD,
                'warning_response_time': AlertManager.WARNING_RESPONSE_TIME_THRESHOLD
            },
            'monitoring_settings': {
                'max_stored_response_times': 1000,
                'cache_timeout_seconds': 3600,
                'health_check_components': ['database', 'cache', 'api']
            },
            'endpoints_monitored': [
                'GET_student_levels',
                'GET_level_selection',
                'POST_level_selection',
                'GET_student_timetable',
                'GET_course_selections',
                'POST_course_selections',
                'GET_audit_trail'
            ],
            'timestamp': timezone.now().isoformat()
        }
        
        return Response(config)
        
    except Exception as e:
        return Response(
            {'error': f'Failed to get monitoring config: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )