"""
Management command for monitoring Student Timetable Module health and performance.

This command can be run periodically (e.g., via cron) to check system health,
collect metrics, and send alerts when necessary.
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
import json
import logging

from students.monitoring import (
    SystemHealthMonitor,
    PerformanceMonitor,
    AlertManager,
    MetricsCollector
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor Student Timetable Module health and performance'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--check-health',
            action='store_true',
            help='Perform system health check'
        )
        parser.add_argument(
            '--collect-metrics',
            action='store_true',
            help='Collect system metrics'
        )
        parser.add_argument(
            '--check-alerts',
            action='store_true',
            help='Check and send alerts'
        )
        parser.add_argument(
            '--performance-report',
            action='store_true',
            help='Generate performance report'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all monitoring tasks'
        )
        parser.add_argument(
            '--output-format',
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )
    
    def handle(self, *args, **options):
        """Handle the monitoring command"""
        try:
            if options['all']:
                self._run_all_checks(options)
            else:
                if options['check_health']:
                    self._check_health(options)
                
                if options['collect_metrics']:
                    self._collect_metrics(options)
                
                if options['check_alerts']:
                    self._check_alerts(options)
                
                if options['performance_report']:
                    self._performance_report(options)
                
                # If no specific option is provided, run health check by default
                if not any([
                    options['check_health'],
                    options['collect_metrics'],
                    options['check_alerts'],
                    options['performance_report']
                ]):
                    self._check_health(options)
        
        except Exception as e:
            logger.error(f"Error in monitoring command: {e}")
            raise CommandError(f"Monitoring failed: {e}")
    
    def _run_all_checks(self, options):
        """Run all monitoring checks"""
        self.stdout.write(
            self.style.SUCCESS("Running comprehensive Student Timetable Module monitoring...")
        )
        
        self._check_health(options)
        self._collect_metrics(options)
        self._check_alerts(options)
        self._performance_report(options)
        
        self.stdout.write(
            self.style.SUCCESS("All monitoring checks completed successfully")
        )
    
    def _check_health(self, options):
        """Perform system health check"""
        try:
            self.stdout.write("Checking system health...")
            
            health_check = SystemHealthMonitor.get_comprehensive_health_check()
            
            if options['output_format'] == 'json':
                self.stdout.write(json.dumps(health_check, indent=2))
            else:
                self._format_health_output(health_check, options['verbose'])
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            self.stdout.write(
                self.style.ERROR(f"Health check failed: {e}")
            )
    
    def _collect_metrics(self, options):
        """Collect system metrics"""
        try:
            self.stdout.write("Collecting system metrics...")
            
            metrics = MetricsCollector.collect_daily_metrics()
            
            if options['output_format'] == 'json':
                self.stdout.write(json.dumps(metrics, indent=2))
            else:
                self._format_metrics_output(metrics, options['verbose'])
            
        except Exception as e:
            logger.error(f"Metrics collection failed: {e}")
            self.stdout.write(
                self.style.ERROR(f"Metrics collection failed: {e}")
            )
    
    def _check_alerts(self, options):
        """Check and send alerts"""
        try:
            self.stdout.write("Checking for alerts...")
            
            alerts = AlertManager.check_and_send_alerts()
            
            if options['output_format'] == 'json':
                self.stdout.write(json.dumps(alerts, indent=2))
            else:
                if alerts:
                    self.stdout.write(
                        self.style.WARNING(f"Found {len(alerts)} alert(s):")
                    )
                    for alert in alerts:
                        level_style = self.style.ERROR if alert['level'] == 'CRITICAL' else self.style.WARNING
                        self.stdout.write(
                            level_style(f"[{alert['level']}] {alert['message']}")
                        )
                        if options['verbose']:
                            self.stdout.write(f"Details: {json.dumps(alert['details'], indent=2)}")
                else:
                    self.stdout.write(
                        self.style.SUCCESS("No alerts detected")
                    )
            
        except Exception as e:
            logger.error(f"Alert check failed: {e}")
            self.stdout.write(
                self.style.ERROR(f"Alert check failed: {e}")
            )
    
    def _performance_report(self, options):
        """Generate performance report"""
        try:
            self.stdout.write("Generating performance report...")
            
            performance_metrics = PerformanceMonitor.get_all_metrics()
            
            if options['output_format'] == 'json':
                self.stdout.write(json.dumps(performance_metrics, indent=2))
            else:
                self._format_performance_output(performance_metrics, options['verbose'])
            
        except Exception as e:
            logger.error(f"Performance report failed: {e}")
            self.stdout.write(
                self.style.ERROR(f"Performance report failed: {e}")
            )
    
    def _format_health_output(self, health_check, verbose=False):
        """Format health check output for text display"""
        overall_status = health_check['overall_status']
        
        # Overall status
        if overall_status == 'healthy':
            self.stdout.write(
                self.style.SUCCESS(f"Overall Status: {overall_status.upper()}")
            )
        elif overall_status == 'degraded':
            self.stdout.write(
                self.style.WARNING(f"Overall Status: {overall_status.upper()}")
            )
        else:
            self.stdout.write(
                self.style.ERROR(f"Overall Status: {overall_status.upper()}")
            )
        
        # Component status
        components = health_check['components']
        
        self.stdout.write("\nComponent Status:")
        for component_name, component_data in components.items():
            status = component_data['status']
            if status == 'healthy':
                status_style = self.style.SUCCESS
            elif status == 'degraded':
                status_style = self.style.WARNING
            else:
                status_style = self.style.ERROR
            
            self.stdout.write(f"  {component_name.title()}: {status_style(status.upper())}")
            
            if verbose:
                for key, value in component_data.items():
                    if key != 'status':
                        self.stdout.write(f"    {key}: {value}")
        
        self.stdout.write(f"\nTimestamp: {health_check['timestamp']}")
    
    def _format_metrics_output(self, metrics, verbose=False):
        """Format metrics output for text display"""
        if 'error' in metrics:
            self.stdout.write(
                self.style.ERROR(f"Metrics collection error: {metrics['error']}")
            )
            return
        
        self.stdout.write(f"Metrics for: {metrics['date']}")
        
        # Student metrics
        student_metrics = metrics['student_metrics']
        self.stdout.write(f"\nStudent Activity:")
        self.stdout.write(f"  New students today: {student_metrics['new_students_today']}")
        self.stdout.write(f"  Total students: {student_metrics['total_students']}")
        
        # Level selection metrics
        level_metrics = metrics['level_selection_metrics']
        self.stdout.write(f"\nLevel Selections:")
        self.stdout.write(f"  Selections today: {level_metrics['selections_today']}")
        self.stdout.write(f"  Total selections: {level_metrics['total_selections']}")
        
        # Course selection metrics
        course_metrics = metrics['course_selection_metrics']
        self.stdout.write(f"\nCourse Selections:")
        self.stdout.write(f"  New selections today: {course_metrics['new_selections_today']}")
        self.stdout.write(f"  Updates today: {course_metrics['updates_today']}")
        self.stdout.write(f"  Total selections: {course_metrics['total_selections']}")
        
        # Audit metrics
        audit_metrics = metrics['audit_metrics']
        self.stdout.write(f"\nAudit Trail:")
        self.stdout.write(f"  Logs today: {audit_metrics['logs_today']}")
        self.stdout.write(f"  Total logs: {audit_metrics['total_logs']}")
        
        # Performance metrics
        if verbose and metrics['performance_metrics']:
            self.stdout.write(f"\nAPI Performance:")
            for endpoint, perf_data in metrics['performance_metrics'].items():
                self.stdout.write(f"  {endpoint}:")
                self.stdout.write(f"    Requests: {perf_data['total_requests']}")
                self.stdout.write(f"    Avg Response: {perf_data['avg_response_time']}ms")
                self.stdout.write(f"    Success Rate: {perf_data['success_rate']}%")
        
        self.stdout.write(f"\nCollected at: {metrics['collected_at']}")
    
    def _format_performance_output(self, performance_metrics, verbose=False):
        """Format performance metrics output for text display"""
        if not performance_metrics:
            self.stdout.write("No performance metrics available")
            return
        
        self.stdout.write("API Performance Metrics:")
        
        for endpoint, metrics in performance_metrics.items():
            # Color code based on performance
            if metrics['error_rate'] > 10 or metrics['avg_response_time'] > 2000:
                endpoint_style = self.style.ERROR
            elif metrics['error_rate'] > 5 or metrics['avg_response_time'] > 1000:
                endpoint_style = self.style.WARNING
            else:
                endpoint_style = self.style.SUCCESS
            
            self.stdout.write(f"\n{endpoint_style(endpoint)}:")
            self.stdout.write(f"  Total Requests: {metrics['total_requests']}")
            self.stdout.write(f"  Average Response Time: {metrics['avg_response_time']}ms")
            self.stdout.write(f"  Success Rate: {metrics['success_rate']}%")
            self.stdout.write(f"  Error Rate: {metrics['error_rate']}%")
            
            if verbose:
                self.stdout.write(f"  Min Response Time: {metrics['min_response_time']}ms")
                self.stdout.write(f"  Max Response Time: {metrics['max_response_time']}ms")
                self.stdout.write(f"  Recent Requests: {metrics['recent_requests']}")