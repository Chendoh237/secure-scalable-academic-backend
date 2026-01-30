from django.urls import path
from . import views

urlpatterns = [
    # Audit log endpoints
    path('logs/', views.get_audit_logs, name='audit_logs'),
    path('logs/summary/', views.get_audit_summary, name='audit_summary'),
    path('logs/export/', views.export_audit_logs, name='export_audit_logs'),
    
    # Email log endpoints
    path('emails/', views.get_email_logs, name='email_logs'),
    path('emails/test/', views.send_test_email, name='send_test_email'),
    path('emails/resend/', views.resend_email, name='resend_email'),
    
    # Email configuration
    path('config/', views.email_configuration, name='email_config'),
    path('config/test/', views.test_email_configuration, name='test_email_config'),
    
    # Email templates
    path('templates/', views.email_templates, name='email_templates'),
    path('templates/<int:template_id>/', views.email_template_detail, name='email_template_detail'),
    
    # Email rules
    path('rules/', views.email_rules, name='email_rules'),
    path('rules/<int:rule_id>/', views.email_rule_detail, name='email_rule_detail'),
]
