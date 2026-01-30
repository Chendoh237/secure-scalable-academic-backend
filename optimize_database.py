#!/usr/bin/env python
"""
Database Optimization Script for Student Timetable Module

This script optimizes database performance by:
1. Adding strategic indexes
2. Analyzing query patterns
3. Providing optimization recommendations
"""

import os
import sys
import django
from django.db import connection, transaction
from django.core.management import call_command
import time

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    django.setup()
except Exception as e:
    print(f"Django setup failed: {e}")
    print("This script should be run from the backend directory")
    sys.exit(1)

from students.models import Student, StudentLevelSelection, StudentCourseSelection, CourseSelectionAuditLog
from courses.models import Level, Course, TimetableSlot, DepartmentTimetable
from institutions.models import Department


class DatabaseOptimizer:
    """
    Database optimization utilities for Student Timetable Module
    """
    
    def __init__(self):
        self.cursor = connection.cursor()
    
    def analyze_table_sizes(self):
        """Analyze table sizes and record counts"""
        print("Analyzing table sizes...")
        print("=" * 50)
        
        tables = [
            ('students_student', Student),
            ('students_studentlevelselection', StudentLevelSelection),
            ('students_studentcourseselection', StudentCourseSelection),
            ('students_courseselectionauditlog', CourseSelectionAuditLog),
            ('courses_level', Level),
            ('courses_course', Course),
            ('courses_timetableslot', TimetableSlot),
            ('courses_departmenttimetable', DepartmentTimetable),
            ('institutions_department', Department),
        ]
        
        for table_name, model_class in tables:
            try:
                count = model_class.objects.count()
                print(f"{table_name:<35} {count:>10} records")
            except Exception as e:
                print(f"{table_name:<35} {'ERROR':>10} - {e}")
        
        print("=" * 50)
    
    def analyze_query_performance(self):
        """Analyze common query performance"""
        print("\nAnalyzing query performance...")
        print("=" * 50)
        
        # Test common queries and measure performance
        queries = [
            {
                'name': 'Get student with department',
                'query': lambda: list(Student.objects.select_related('department').all()[:10])
            },
            {
                'name': 'Get levels for department',
                'query': lambda: list(Level.objects.filter(department_id=1).order_by('code'))
            },
            {
                'name': 'Get timetable slots with relations',
                'query': lambda: list(TimetableSlot.objects.select_related(
                    'course', 'lecturer', 'lecturer__user', 'level'
                ).filter(level_id=1)[:10])
            },
            {
                'name': 'Get course selections for student',
                'query': lambda: list(StudentCourseSelection.objects.select_related(
                    'course'
                ).filter(student_id=1))
            },
            {
                'name': 'Get student level selection',
                'query': lambda: list(StudentLevelSelection.objects.select_related(
                    'level'
                ).filter(student_id=1))
            }
        ]
        
        for query_info in queries:
            try:
                # Clear query log
                connection.queries_log.clear()
                
                # Execute query and measure time
                start_time = time.time()
                result = query_info['query']()
                end_time = time.time()
                
                query_time = (end_time - start_time) * 1000  # Convert to milliseconds
                query_count = len(connection.queries)
                
                print(f"{query_info['name']:<35} {query_time:>8.2f}ms {query_count:>3} queries")
                
            except Exception as e:
                print(f"{query_info['name']:<35} {'ERROR':>8} - {e}")
        
        print("=" * 50)
    
    def check_existing_indexes(self):
        """Check existing database indexes"""
        print("\nChecking existing indexes...")
        print("=" * 50)
        
        # Get index information (SQLite specific)
        try:
            # List all indexes
            self.cursor.execute("""
                SELECT name, tbl_name, sql 
                FROM sqlite_master 
                WHERE type = 'index' 
                AND name NOT LIKE 'sqlite_%'
                ORDER BY tbl_name, name
            """)
            
            indexes = self.cursor.fetchall()
            
            current_table = None
            for index_name, table_name, sql in indexes:
                if table_name != current_table:
                    if current_table is not None:
                        print()
                    print(f"Table: {table_name}")
                    current_table = table_name
                
                print(f"  {index_name}")
                if sql:
                    # Extract column info from CREATE INDEX statement
                    if 'ON' in sql and '(' in sql:
                        columns_part = sql.split('(')[1].split(')')[0]
                        print(f"    Columns: {columns_part}")
            
        except Exception as e:
            print(f"Error checking indexes: {e}")
        
        print("=" * 50)
    
    def suggest_optimizations(self):
        """Suggest database optimizations"""
        print("\nOptimization Suggestions:")
        print("=" * 50)
        
        suggestions = [
            {
                'category': 'Indexes',
                'items': [
                    'Consider composite index on (student_id, level_id) for StudentCourseSelection',
                    'Consider index on (department_id, level_id) for TimetableSlot',
                    'Consider index on (student_id, timestamp) for CourseSelectionAuditLog',
                    'Consider index on (is_offered) for StudentCourseSelection for attendance queries'
                ]
            },
            {
                'category': 'Query Optimization',
                'items': [
                    'Use select_related() for foreign key relationships',
                    'Use prefetch_related() for reverse foreign key relationships',
                    'Consider database-level caching for frequently accessed data',
                    'Use bulk operations for multiple record updates'
                ]
            },
            {
                'category': 'Data Management',
                'items': [
                    'Archive old audit log entries periodically',
                    'Consider partitioning large tables by academic year',
                    'Implement soft deletes instead of hard deletes where appropriate',
                    'Use database constraints to maintain data integrity'
                ]
            }
        ]
        
        for suggestion in suggestions:
            print(f"\n{suggestion['category']}:")
            for item in suggestion['items']:
                print(f"  • {item}")
        
        print("=" * 50)
    
    def create_performance_indexes(self):
        """Create additional indexes for better performance"""
        print("\nCreating performance indexes...")
        print("=" * 50)
        
        # Define additional indexes that might help performance
        indexes = [
            {
                'name': 'idx_student_course_selection_lookup',
                'table': 'students_studentcourseselection',
                'columns': ['student_id', 'level_id', 'is_offered'],
                'description': 'Optimize course selection lookups'
            },
            {
                'name': 'idx_timetable_slot_lookup',
                'table': 'courses_timetableslot',
                'columns': ['timetable_id', 'level_id', 'day_of_week'],
                'description': 'Optimize timetable queries'
            },
            {
                'name': 'idx_audit_log_student_time',
                'table': 'students_courseselectionauditlog',
                'columns': ['student_id', 'timestamp'],
                'description': 'Optimize audit log queries'
            }
        ]
        
        for index in indexes:
            try:
                # Check if index already exists
                self.cursor.execute(f"""
                    SELECT name FROM sqlite_master 
                    WHERE type='index' AND name='{index['name']}'
                """)
                
                if self.cursor.fetchone():
                    print(f"  Index {index['name']} already exists")
                    continue
                
                # Create the index
                columns_str = ', '.join(index['columns'])
                sql = f"""
                    CREATE INDEX {index['name']} 
                    ON {index['table']} ({columns_str})
                """
                
                start_time = time.time()
                self.cursor.execute(sql)
                end_time = time.time()
                
                creation_time = (end_time - start_time) * 1000
                print(f"  ✓ Created {index['name']} ({creation_time:.2f}ms)")
                print(f"    {index['description']}")
                
            except Exception as e:
                print(f"  ✗ Failed to create {index['name']}: {e}")
        
        print("=" * 50)
    
    def vacuum_database(self):
        """Vacuum the database to reclaim space and optimize"""
        print("\nVacuuming database...")
        print("=" * 50)
        
        try:
            start_time = time.time()
            self.cursor.execute("VACUUM")
            end_time = time.time()
            
            vacuum_time = (end_time - start_time) * 1000
            print(f"✓ Database vacuumed successfully ({vacuum_time:.2f}ms)")
            
        except Exception as e:
            print(f"✗ Database vacuum failed: {e}")
        
        print("=" * 50)
    
    def analyze_database_stats(self):
        """Analyze database statistics"""
        print("\nDatabase Statistics:")
        print("=" * 50)
        
        try:
            # Get database file size
            db_path = connection.settings_dict['NAME']
            if os.path.exists(db_path):
                db_size = os.path.getsize(db_path)
                print(f"Database file size: {db_size / (1024*1024):.2f} MB")
            
            # Get page count and page size
            self.cursor.execute("PRAGMA page_count")
            page_count = self.cursor.fetchone()[0]
            
            self.cursor.execute("PRAGMA page_size")
            page_size = self.cursor.fetchone()[0]
            
            print(f"Page count: {page_count:,}")
            print(f"Page size: {page_size:,} bytes")
            print(f"Total pages size: {(page_count * page_size) / (1024*1024):.2f} MB")
            
            # Get cache size
            self.cursor.execute("PRAGMA cache_size")
            cache_size = self.cursor.fetchone()[0]
            print(f"Cache size: {cache_size:,} pages")
            
        except Exception as e:
            print(f"Error getting database stats: {e}")
        
        print("=" * 50)
    
    def run_full_optimization(self):
        """Run complete database optimization"""
        print("Student Timetable Module - Database Optimization")
        print("=" * 60)
        
        # Step 1: Analyze current state
        self.analyze_table_sizes()
        self.analyze_database_stats()
        self.check_existing_indexes()
        
        # Step 2: Performance analysis
        self.analyze_query_performance()
        
        # Step 3: Create optimizations
        self.create_performance_indexes()
        
        # Step 4: Vacuum database
        self.vacuum_database()
        
        # Step 5: Provide suggestions
        self.suggest_optimizations()
        
        print("\n" + "=" * 60)
        print("Database optimization completed!")
        print("=" * 60)


def main():
    """Main function"""
    try:
        optimizer = DatabaseOptimizer()
        optimizer.run_full_optimization()
        return True
    except Exception as e:
        print(f"Optimization failed: {e}")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)