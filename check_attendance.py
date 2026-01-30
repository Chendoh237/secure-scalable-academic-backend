#!/usr/bin/env python
"""
Simple script to check attendance data in the system
Run this from the Django project root: python check_attendance.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from students.models import Student
from attendance.models import Attendance, CourseRegistration
from courses.models import Course

def main():
    print("=== ATTENDANCE DATA CHECK ===")
    
    # Check students
    students = Student.objects.filter(is_approved=True)
    print(f"Approved students: {students.count()}")
    
    # Check courses
    courses = Course.objects.all()
    print(f"Total courses: {courses.count()}")
    
    # Check course registrations
    registrations = CourseRegistration.objects.all()
    print(f"Course registrations: {registrations.count()}")
    
    # Check attendance records
    attendance_records = Attendance.objects.all()
    print(f"Attendance records: {attendance_records.count()}")
    
    if attendance_records.exists():
        print("\n=== SAMPLE ATTENDANCE RECORDS ===")
        for record in attendance_records[:5]:
            course_name = record.course_registration.course.code if record.course_registration and record.course_registration.course else "N/A"
            print(f"Student: {record.student.full_name} | Course: {course_name} | Date: {record.date} | Status: {record.status}")
    
    # Check for specific student
    if students.exists():
        student = students.first()
        student_attendance = Attendance.objects.filter(student=student)
        print(f"\n=== ATTENDANCE FOR {student.full_name} ===")
        print(f"Total records: {student_attendance.count()}")
        
        if student_attendance.exists():
            present = student_attendance.filter(status='present').count()
            late = student_attendance.filter(status='late').count()
            absent = student_attendance.filter(status='absent').count()
            total = student_attendance.count()
            
            print(f"Present: {present}")
            print(f"Late: {late}")
            print(f"Absent: {absent}")
            print(f"Attendance %: {((present + late) / total * 100):.1f}%" if total > 0 else "0%")

if __name__ == "__main__":
    main()