#!/usr/bin/env python
"""
List all Django URLs to verify the export endpoint exists
"""
import os
import sys
import django

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.urls import get_resolver
from django.conf import settings

def show_urls(urllist, depth=0):
    for entry in urllist:
        print("  " * depth, entry.pattern, entry.name)
        if hasattr(entry, 'url_patterns'):
            show_urls(entry.url_patterns, depth + 1)

if __name__ == '__main__':
    print("Django URLs:")
    resolver = get_resolver()
    show_urls(resolver.url_patterns)