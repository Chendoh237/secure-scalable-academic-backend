#!/usr/bin/env python
"""Script to check Django URL patterns"""
import os
import sys
import django
from django.conf import settings
from django.urls import get_resolver

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
    django.setup()
    
    resolver = get_resolver()
    
    def list_urls(url_patterns, prefix=''):
        for pattern in url_patterns:
            if hasattr(pattern, 'url_patterns'):
                # This is an include() pattern
                new_prefix = prefix + str(pattern.pattern)
                list_urls(pattern.url_patterns, new_prefix)
            else:
                # This is a regular pattern
                full_pattern = prefix + str(pattern.pattern)
                print(f"{full_pattern} -> {pattern.callback}")
    
    print("URL Patterns:")
    list_urls(resolver.url_patterns)