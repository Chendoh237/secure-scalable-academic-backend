"""
Property-Based Tests for Email System Security and Encryption

This module contains property-based tests that validate the security and encryption
properties of the email management system, ensuring that sensitive credentials
are properly encrypted, transmitted securely, and masked in user interfaces.

**Property 20: Security and Encryption**
For any sensitive credential (SMTP passwords), the system should encrypt the data 
for storage and transmit it only over secure connections, while masking it in user interfaces.
**Validates: Requirements 9.1, 9.2, 9.3**
"""

import unittest
from hypothesis import given, strategies as st, settings, assume
from django.test import TestCase
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock
import ssl
import base64
import json

from students.email_models import (
    EmailConfiguration, 
    EmailSecurityManager, 
    EmailTemplate, 
    EmailHistory, 
    EmailDelivery
)
from students.email_service import EmailService


class SecurityEncryptionPropertiesTest(TestCase):
    """
    Property-based tests for security and encryption functionality.
    
    **Feature: email-management-system, Property 20: Security and Encryption**
    **Validates: Requirements 9.1, 9.2, 9.3**
    """
    
    def setUp(self):
        """Set up test environment"""
        self.email_service = EmailService()
        self.security_manager = EmailSecurityManager()
    
    @given(
        password=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        smtp_host=st.text(min_size=5, max_size=50).filter(lambda x: '.' in x and x.strip()),
        smtp_port=st.integers(min_value=1, max_value=65535),
        username=st.emails()
    )
    @settings(max_examples=50, deadline=5000)
    def test_password_encryption_storage_property(self, password, smtp_host, smtp_port, username):
        """
        **Property 20a: Password Encryption Storage**
        For any SMTP password, storing it should encrypt the password and 
        retrieving it should return the original password unchanged.
        **Validates: Requirements 9.1**
        """
        # Create email configuration with password
        config = EmailConfiguration(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=username,
            from_email=username,
            use_tls=True,
            use_ssl=False,
            from_name="Test System"
        )
        
        # Set the password (should be encrypted)
        config.set_password(password)
        
        # Verify password is encrypted in storage
        stored_password = config.smtp_password
        self.assertNotEqual(stored_password, password, 
                          f"Password should be encrypted in storage, but got plain text: {password}")
        
        # Verify we can retrieve the original password
        retrieved_password = config.get_password()
        self.assertEqual(retrieved_password, password,
                        f"Retrieved password should match original. Expected: {password}, Got: {retrieved_password}")
        
        # Verify encrypted password is different from original
        if password:  # Only check if password is not empty
            self.assertNotEqual(stored_password, password,
                              "Stored password should be encrypted, not plain text")
    
    @given(
        config_data=st.fixed_dictionaries({
            'smtp_host': st.text(min_size=5, max_size=50).filter(lambda x: '.' in x),
            'smtp_port': st.integers(min_value=1, max_value=65535),
            'smtp_username': st.emails(),
            'smtp_password': st.text(min_size=1, max_size=50),
            'use_tls': st.booleans(),
            'use_ssl': st.booleans(),
            'from_email': st.emails(),
            'from_name': st.text(min_size=1, max_size=100)
        })
    )
    @settings(max_examples=30, deadline=5000)
    def test_sensitive_data_masking_property(self, config_data):
        """
        **Property 20b: Sensitive Data Masking**
        For any configuration containing sensitive data, the masked version
        should hide passwords while preserving other configuration data.
        **Validates: Requirements 9.3**
        """
        # Assume valid TLS/SSL combination
        assume(not (config_data['use_tls'] and config_data['use_ssl']))
        
        # Create configuration
        config = EmailConfiguration(
            smtp_host=config_data['smtp_host'],
            smtp_port=config_data['smtp_port'],
            smtp_username=config_data['smtp_username'],
            from_email=config_data['from_email'],
            use_tls=config_data['use_tls'],
            use_ssl=config_data['use_ssl'],
            from_name=config_data['from_name']
        )
        config.set_password(config_data['smtp_password'])
        
        # Get masked configuration
        masked_config = config.get_masked_config()
        
        # Verify password is masked
        self.assertIn('***masked***', masked_config['smtp_password'],
                     "Password should be masked in configuration display")
        
        # Verify other fields are not masked
        self.assertEqual(masked_config['smtp_host'], config_data['smtp_host'])
        self.assertEqual(masked_config['smtp_port'], config_data['smtp_port'])
        self.assertEqual(masked_config['smtp_username'], config_data['smtp_username'])
        self.assertEqual(masked_config['from_email'], config_data['from_email'])
        
        # Verify original password is not exposed
        self.assertNotEqual(masked_config['smtp_password'], config_data['smtp_password'],
                          "Original password should not appear in masked configuration")
    
    @given(
        use_tls=st.booleans(),
        use_ssl=st.booleans(),
        port=st.integers(min_value=1, max_value=65535)
    )
    @settings(max_examples=50, deadline=3000)
    def test_ssl_tls_validation_property(self, use_tls, use_ssl, port):
        """
        **Property 20c: SSL/TLS Validation**
        For any SSL/TLS configuration, the system should validate that
        encryption settings are secure and properly configured.
        **Validates: Requirements 9.4**
        """
        # Test the validation logic
        if use_tls and use_ssl:
            # Should raise validation error for conflicting settings
            with self.assertRaises(ValidationError):
                EmailSecurityManager.validate_ssl_tls_settings(use_tls, use_ssl, port)
        else:
            # Should not raise error for valid combinations
            try:
                EmailSecurityManager.validate_ssl_tls_settings(use_tls, use_ssl, port)
                # If no exception, validation passed
                validation_passed = True
            except ValidationError:
                # Some combinations may still be invalid (e.g., no encryption on port 25)
                validation_passed = False
            
            # Verify that at least secure configurations pass validation
            if (use_tls and port == 587) or (use_ssl and port == 465):
                self.assertTrue(validation_passed, 
                              f"Secure configuration should pass validation: TLS={use_tls}, SSL={use_ssl}, port={port}")
    
    @given(
        config_data=st.fixed_dictionaries({
            'smtpServer': st.text(min_size=5, max_size=50).filter(lambda x: '.' in x),
            'smtpPort': st.integers(min_value=1, max_value=65535),
            'emailUser': st.emails(),
            'emailPassword': st.text(min_size=1, max_size=50),
            'useTLS': st.booleans(),
            'useSSL': st.booleans(),
            'fromName': st.text(min_size=1, max_size=100)
        })
    )
    @settings(max_examples=30, deadline=5000)
    def test_security_validation_property(self, config_data):
        """
        **Property 20d: Security Validation**
        For any SMTP configuration, security validation should identify
        insecure configurations and provide appropriate warnings.
        **Validates: Requirements 9.2, 9.4**
        """
        # Assume valid TLS/SSL combination
        assume(not (config_data['useTLS'] and config_data['useSSL']))
        
        # Test security validation
        result = self.email_service.validate_smtp_security(config_data)
        
        # Should always return a result
        self.assertIsInstance(result, dict)
        self.assertIn('success', result)
        
        if result['success']:
            security_validation = result['security_validation']
            
            # Should have security level assessment
            self.assertIn('security_level', security_validation)
            self.assertIn(security_validation['security_level'], ['low', 'medium', 'high', 'unknown'])
            
            # Should have security status
            self.assertIn('is_secure', security_validation)
            self.assertIsInstance(security_validation['is_secure'], bool)
            
            # Should provide warnings for insecure configurations
            if not config_data['useTLS'] and not config_data['useSSL']:
                self.assertFalse(security_validation['is_secure'],
                               "Configuration without encryption should be marked as insecure")
                self.assertTrue(len(security_validation.get('warnings', [])) > 0,
                              "Insecure configuration should have warnings")
            
            # Should mark encrypted configurations as more secure
            if config_data['useTLS'] or config_data['useSSL']:
                self.assertIn(security_validation['security_level'], ['medium', 'high'],
                            "Encrypted configuration should have medium or high security level")
    
    @patch('students.email_service.smtplib.SMTP')
    @patch('students.email_service.smtplib.SMTP_SSL')
    @given(
        use_ssl=st.booleans(),
        verify_certificates=st.booleans()
    )
    @settings(max_examples=20, deadline=3000)
    def test_secure_ssl_context_property(self, mock_smtp_ssl, mock_smtp, use_ssl, verify_certificates):
        """
        **Property 20e: Secure SSL Context**
        For any SSL context creation, the system should create contexts with
        secure settings and proper certificate verification.
        **Validates: Requirements 9.2**
        """
        # Create secure SSL context
        context = self.email_service._create_secure_ssl_context(verify_mode=verify_certificates)
        
        # Verify it's an SSL context
        self.assertIsInstance(context, ssl.SSLContext)
        
        # Verify security settings
        if verify_certificates:
            self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(context.check_hostname)
        else:
            self.assertEqual(context.verify_mode, ssl.CERT_NONE)
            self.assertFalse(context.check_hostname)
        
        # Verify minimum TLS version is secure
        self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2,
                              "Minimum TLS version should be 1.2 or higher for security")
        
        # Verify weak protocols are disabled
        self.assertTrue(context.options & ssl.OP_NO_SSLv2)
        self.assertTrue(context.options & ssl.OP_NO_SSLv3)
        self.assertTrue(context.options & ssl.OP_NO_TLSv1)
        self.assertTrue(context.options & ssl.OP_NO_TLSv1_1)
    
    @given(
        event_type=st.text(min_size=1, max_size=50),
        details=st.fixed_dictionaries({
            'host': st.text(min_size=1, max_size=50),
            'port': st.integers(min_value=1, max_value=65535),
            'password': st.text(min_size=1, max_size=50),
            'username': st.emails(),
            'other_data': st.text(min_size=1, max_size=100)
        })
    )
    @settings(max_examples=30, deadline=3000)
    def test_security_logging_property(self, event_type, details):
        """
        **Property 20f: Security Logging**
        For any security event logging, sensitive data should be masked
        while preserving important security information.
        **Validates: Requirements 9.5**
        """
        # Test security event logging (we'll capture the log call)
        with patch('students.email_service.logger.info') as mock_logger:
            self.email_service._log_security_event(event_type, details)
            
            # Verify logger was called
            mock_logger.assert_called_once()
            
            # Get the logged message
            logged_args = mock_logger.call_args[0]
            logged_message = logged_args[0] if logged_args else ""
            
            # Verify sensitive data is not in the log
            self.assertNotIn(details['password'], logged_message,
                           "Password should not appear in security logs")
            
            # Verify event type is logged
            self.assertIn(event_type, logged_message,
                        "Event type should be included in security log")
            
            # Verify non-sensitive data can be logged
            self.assertIn(str(details['port']), logged_message,
                        "Non-sensitive data like port should be in security log")
    
    @given(
        passwords=st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10)
    )
    @settings(max_examples=20, deadline=5000)
    def test_encryption_consistency_property(self, passwords):
        """
        **Property 20g: Encryption Consistency**
        For any set of passwords, each should encrypt to a different value,
        but decrypt back to the original consistently.
        **Validates: Requirements 9.1**
        """
        encrypted_passwords = []
        
        for password in passwords:
            # Encrypt password
            encrypted = EmailSecurityManager.encrypt_password(password)
            encrypted_passwords.append(encrypted)
            
            # Verify it decrypts back to original
            decrypted = EmailSecurityManager.decrypt_password(encrypted)
            self.assertEqual(decrypted, password,
                           f"Password should decrypt to original value. Expected: {password}, Got: {decrypted}")
        
        # Verify different passwords encrypt to different values
        unique_passwords = list(set(passwords))
        if len(unique_passwords) > 1:
            unique_encrypted = []
            for password in unique_passwords:
                encrypted = EmailSecurityManager.encrypt_password(password)
                unique_encrypted.append(encrypted)
            
            # All encrypted values should be different
            self.assertEqual(len(unique_encrypted), len(set(unique_encrypted)),
                           "Different passwords should encrypt to different values")
    
    def test_empty_password_handling(self):
        """
        Test that empty passwords are handled securely.
        **Validates: Requirements 9.1**
        """
        # Test empty string
        encrypted_empty = EmailSecurityManager.encrypt_password("")
        decrypted_empty = EmailSecurityManager.decrypt_password(encrypted_empty)
        self.assertEqual(decrypted_empty, "")
        
        # Test None (should be handled gracefully)
        encrypted_none = EmailSecurityManager.encrypt_password(None)
        self.assertEqual(encrypted_none, "")
    
    def test_security_manager_error_handling(self):
        """
        Test that security manager handles errors gracefully.
        **Validates: Requirements 9.1, 9.2**
        """
        # Test with invalid encrypted data
        invalid_encrypted = "invalid_base64_data"
        decrypted = EmailSecurityManager.decrypt_password(invalid_encrypted)
        
        # Should handle gracefully (return empty string or original)
        self.assertIsInstance(decrypted, str)
        
        # Test masking with various data types
        test_data = {
            'password': 'secret123',
            'smtp_password': 'another_secret',
            'email_password': 'email_secret',
            'normal_field': 'normal_value'
        }
        
        masked = EmailSecurityManager.mask_sensitive_data(test_data)
        
        # Verify sensitive fields are masked
        self.assertEqual(masked['password'], '***masked***')
        self.assertEqual(masked['smtp_password'], '***masked***')
        self.assertEqual(masked['email_password'], '***masked***')
        
        # Verify normal fields are not masked
        self.assertEqual(masked['normal_field'], 'normal_value')


if __name__ == '__main__':
    unittest.main()