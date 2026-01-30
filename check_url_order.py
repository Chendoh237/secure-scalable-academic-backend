import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver

def print_url_patterns(urlpatterns, prefix='', depth=0):
    """Recursively print URL patterns with their order"""
    for i, pattern in enumerate(urlpatterns):
        indent = "  " * depth
        pattern_str = str(pattern.pattern)
        
        if isinstance(pattern, URLResolver):
            # This is an include()
            print(f"{indent}[{i}] INCLUDE: {prefix}{pattern_str}")
            print_url_patterns(pattern.url_patterns, prefix + pattern_str, depth + 1)
        elif isinstance(pattern, URLPattern):
            # This is a regular URL pattern
            full_url = prefix + pattern_str
            view_name = getattr(pattern.callback, '__name__', str(pattern.callback))
            print(f"{indent}[{i}] {full_url} -> {view_name}")

print("=" * 80)
print("URL PATTERNS IN ORDER (showing potential conflicts)")
print("=" * 80)

resolver = get_resolver()
print_url_patterns(resolver.url_patterns)

print("\n" + "=" * 80)
print("Checking for patterns that might catch /api/students/levels/")
print("=" * 80)

# Test URL resolution
from django.urls import resolve
from django.urls.exceptions import Resolver404

test_urls = [
    '/api/students/levels/',
    '/api/students/level-selection/',
    '/api/students/timetable/',
    '/api/students/course-selections/',
]

for url in test_urls:
    try:
        match = resolve(url)
        print(f"\n[OK] {url}")
        print(f"  View: {match.func.__name__}")
        print(f"  URL name: {match.url_name}")
    except Resolver404 as e:
        print(f"\n[FAIL] {url}")
        print(f"  ERROR: {e}")
