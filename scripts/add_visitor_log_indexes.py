#!/usr/bin/env python3
"""
Add performance indexes to visitor_log table for IP summary queries

This script adds indexes to optimize:
- IP address grouping and filtering
- Timestamp-based filtering
- Location-based searches
- Combined queries for the IP summary chart
"""

import sqlite3
import os
from datetime import datetime

# Database configuration
DB_PATH = "instance/tamermap_data.db"
BACKUP_PATH = f"instance/tamermap_data_backup_indexes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def backup_database():
    """Create a backup before making changes"""
    print(f"🔒 Creating backup: {BACKUP_PATH}")
    try:
        import shutil
        shutil.copy2(DB_PATH, BACKUP_PATH)
        print(f"✅ Backup created successfully")
        return True
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return False

def check_existing_indexes(cursor):
    """Check what indexes already exist"""
    print("🔍 Checking existing indexes...")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='visitor_log'")
    existing_indexes = [row[0] for row in cursor.fetchall()]
    
    print(f"   Existing indexes: {existing_indexes}")
    return existing_indexes

def create_indexes(cursor):
    """Create the necessary indexes"""
    print("🔧 Creating performance indexes...")
    
    # Indexes to create
    indexes_to_create = [
        {
            'name': 'idx_visitor_log_ip_timestamp',
            'sql': 'CREATE INDEX idx_visitor_log_ip_timestamp ON visitor_log(ip_address, timestamp)',
            'description': 'Composite index for IP address and timestamp (optimizes IP summary queries)'
        },
        {
            'name': 'idx_visitor_log_timestamp',
            'sql': 'CREATE INDEX idx_visitor_log_timestamp ON visitor_log(timestamp)',
            'description': 'Index on timestamp for date-based filtering'
        },
        {
            'name': 'idx_visitor_log_ip_location',
            'sql': 'CREATE INDEX idx_visitor_log_ip_location ON visitor_log(ip_address, city, region, country)',
            'description': 'Composite index for IP and location data'
        },
        {
            'name': 'idx_visitor_log_city',
            'sql': 'CREATE INDEX idx_visitor_log_city ON visitor_log(city)',
            'description': 'Index on city for location-based searches'
        },
        {
            'name': 'idx_visitor_log_region',
            'sql': 'CREATE INDEX idx_visitor_log_region ON visitor_log(region)',
            'description': 'Index on region for location-based searches'
        },
        {
            'name': 'idx_visitor_log_country',
            'sql': 'CREATE INDEX idx_visitor_log_country ON visitor_log(country)',
            'description': 'Index on country for location-based searches'
        }
    ]
    
    created_count = 0
    for index_info in indexes_to_create:
        index_name = index_info['name']
        
        # Check if index already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
        if cursor.fetchone():
            print(f"   ⏭️  Index {index_name} already exists, skipping...")
            continue
        
        try:
            print(f"   🔨 Creating {index_name}...")
            cursor.execute(index_info['sql'])
            print(f"   ✅ Created {index_name}: {index_info['description']}")
            created_count += 1
        except Exception as e:
            print(f"   ❌ Failed to create {index_name}: {e}")
    
    return created_count

def analyze_table(cursor):
    """Run ANALYZE to update table statistics"""
    print("📊 Analyzing table statistics...")
    try:
        cursor.execute("ANALYZE visitor_log")
        print("✅ Table analysis completed")
        return True
    except Exception as e:
        print(f"⚠️  Table analysis failed: {e}")
        return False

def show_index_info(cursor):
    """Show information about the created indexes"""
    print("\n📋 Index Information:")
    print("-" * 60)
    
    cursor.execute("""
        SELECT 
            name,
            sql
        FROM sqlite_master 
        WHERE type='index' AND tbl_name='visitor_log'
        ORDER BY name
    """)
    
    indexes = cursor.fetchall()
    for name, sql in indexes:
        print(f"   {name}: {sql}")

def main():
    """Main index creation process"""
    print("🔧 Visitor Log Performance Index Creation Script")
    print("=" * 60)
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        print("   Please run this script from the project root directory")
        return
    
    # Connect to database
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        print(f"✅ Connected to database: {DB_PATH}")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return
    
    try:
        # Step 1: Check existing indexes
        existing_indexes = check_existing_indexes(cursor)
        
        # Step 2: Create backup
        if not backup_database():
            print("❌ Cannot proceed without backup")
            return
        
        # Step 3: Create indexes
        created_count = create_indexes(cursor)
        
        if created_count > 0:
            # Step 4: Commit changes
            conn.commit()
            print(f"\n✅ Successfully created {created_count} new indexes")
            
            # Step 5: Analyze table
            analyze_table(cursor)
            
            # Step 6: Show index information
            show_index_info(cursor)
            
            print(f"\n🎉 Index creation completed successfully!")
            print(f"   Backup created: {BACKUP_PATH}")
            print(f"   New indexes created: {created_count}")
        else:
            print("\n✅ All necessary indexes already exist - no changes needed")
        
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print("   Rolling back changes...")
        conn.rollback()
        print("   Please check the backup and restore if needed")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
