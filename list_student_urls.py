import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.urls import get_resolver

resolver = get_resolver()

print("=" * 60)
print("Checking Student Timetable Module URLs")
print("=" * 60)

# Get all URL patterns
def get_all_urls(urlpatterns, prefix=''):
    urls = []
    for pattern in urlpatterns:
        if hasattr(pattern, 'url_patterns'):
            # This is an include()
            new_prefix = prefix + str(pattern.pattern)
            urls.extend(get_all_urls(pattern.url_patterns, new_prefix))
        else:
            # This is a regular URL pattern
            url = prefix + str(pattern.pattern)
            urls.append(url)
    return urls

all_urls = get_all_urls(resolver.url_patterns)

# Filter for student timetable URLs
student_timetable_urls = [url for url in all_urls if 'students/level' in url or 'students/course-selection' in url]

print("\nStudent Timetable Module URLs:")
for url in sorted(student_timetable_urls):
    print(f"  {url}")

print("\nAll students/* URLs:")
students_urls = [url for url in all_urls if 'students/' in url]
for url in sorted(students_urls):
    print(f"  {url}")

print("\n" + "=" * 60)
