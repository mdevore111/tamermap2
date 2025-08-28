#!/usr/bin/env python3
"""
Cleanup Unnecessary Database Indexes Script

This script removes unnecessary indexes that were created but aren't actually needed,
keeping only the essential ones for optimal performance.

ESSENTIAL INDEXES TO KEEP:
- idx_visitor_log_ip_timestamp (for IP summary queries)

INDEXES TO REMOVE (unnecessary/overkill):
- idx_visitor_log_timestamp (redundant with composite)
- idx_visitor_log_ip_location (overkill for current queries)
- idx_visitor_log_city (not needed for main functionality)
- idx_visitor_log_region (not needed for main functionality)
- idx_visitor_log_country (not needed for main functionality)
"""

import sqlite3
import os
from datetime import datetime

# Database configuration
DB_PATH = "instance/tamermap_data.db"
BACKUP_PATH = f"instance/tamermap_data_backup_index_cleanup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

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

def get_current_indexes(cursor):
    """Get all current indexes on visitor_log table"""
    print("🔍 Checking current indexes...")
    
    cursor.execute("""
        SELECT name, sql 
        FROM sqlite_master 
        WHERE type='index' AND tbl_name='visitor_log'
        ORDER BY name
    """)
    
    indexes = cursor.fetchall()
    
    if not indexes:
        print("   No indexes found on visitor_log table")
        return []
    
    print(f"   Found {len(indexes)} indexes:")
    for name, sql in indexes:
        print(f"     {name}: {sql}")
    
    return indexes

def identify_unnecessary_indexes(indexes):
    """Identify which indexes should be removed"""
    print("\n🎯 Analyzing index necessity...")
    
    # Essential indexes to keep
    essential_indexes = [
        'idx_visitor_log_ip_timestamp',  # Main composite index for IP summary
        'idx_visitor_log_session_id'     # Session tracking (if exists)
    ]
    
    # Indexes that are unnecessary/overkill
    unnecessary_indexes = [
        'idx_visitor_log_timestamp',     # Redundant with composite index
        'idx_visitor_log_ip_location',   # Overkill for current queries
        'idx_visitor_log_city',          # Not needed for main functionality
        'idx_visitor_log_region',        # Not needed for main functionality
        'idx_visitor_log_country',       # Not needed for main functionality
    ]
    
    to_remove = []
    to_keep = []
    
    for name, sql in indexes:
        if name in essential_indexes:
            to_keep.append((name, sql))
            print(f"   ✅ KEEP: {name} - Essential for performance")
        elif name in unnecessary_indexes:
            to_remove.append((name, sql))
            print(f"   🗑️  REMOVE: {name} - Unnecessary/overkill")
        else:
            # Unknown index - ask user
            to_keep.append((name, sql))
            print(f"   ❓ UNKNOWN: {name} - Keeping for safety")
    
    return to_remove, to_keep

def remove_unnecessary_indexes(cursor, indexes_to_remove):
    """Remove the unnecessary indexes"""
    if not indexes_to_remove:
        print("\n✅ No unnecessary indexes to remove")
        return 0
    
    print(f"\n🗑️  Removing {len(indexes_to_remove)} unnecessary indexes...")
    
    removed_count = 0
    for name, sql in indexes_to_remove:
        try:
            print(f"   🔨 Dropping {name}...")
            cursor.execute(f"DROP INDEX {name}")
            print(f"   ✅ Removed {name}")
            removed_count += 1
        except Exception as e:
            print(f"   ❌ Failed to remove {name}: {e}")
    
    return removed_count

def create_essential_indexes(cursor, indexes_to_keep):
    """Ensure essential indexes exist"""
    print("\n🔧 Ensuring essential indexes exist...")
    
    essential_indexes = {
        'idx_visitor_log_ip_timestamp': {
            'sql': 'CREATE INDEX idx_visitor_log_ip_timestamp ON visitor_log(ip_address, timestamp)',
            'description': 'Composite index for IP summary queries (timestamp filtering + IP grouping)'
        }
    }
    
    created_count = 0
    for name, sql in indexes_to_keep:
        if name in essential_indexes:
            print(f"   ✅ {name} already exists")
            continue
    
    # Check if we need to create the essential composite index
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_visitor_log_ip_timestamp'")
    if not cursor.fetchone():
        try:
            print(f"   🔨 Creating essential index idx_visitor_log_ip_timestamp...")
            cursor.execute(essential_indexes['idx_visitor_log_ip_timestamp']['sql'])
            print(f"   ✅ Created: {essential_indexes['idx_visitor_log_ip_timestamp']['description']}")
            created_count += 1
        except Exception as e:
            print(f"   ❌ Failed to create essential index: {e}")
    
    return created_count

def analyze_table(cursor):
    """Run ANALYZE to update table statistics"""
    print("\n📊 Analyzing table statistics...")
    try:
        cursor.execute("ANALYZE visitor_log")
        print("✅ Table analysis completed")
        return True
    except Exception as e:
        print(f"⚠️  Table analysis failed: {e}")
        return False

def show_final_indexes(cursor):
    """Show the final index configuration"""
    print("\n📋 Final Index Configuration:")
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
    if not indexes:
        print("   No indexes remaining on visitor_log table")
        return
    
    for name, sql in indexes:
        print(f"   {name}: {sql}")

def main():
    """Main index cleanup process"""
    print("🧹 Unnecessary Index Cleanup Script")
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
        # Step 1: Check current indexes
        current_indexes = get_current_indexes(cursor)
        
        # Step 2: Identify what to remove/keep
        to_remove, to_keep = identify_unnecessary_indexes(current_indexes)
        
        if not to_remove:
            print("\n✅ No unnecessary indexes found - nothing to clean up!")
            return
        
        # Step 3: Create backup
        if not backup_database():
            print("❌ Cannot proceed without backup")
            return
        
        # Step 4: Remove unnecessary indexes
        removed_count = remove_unnecessary_indexes(cursor, to_remove)
        
        # Step 5: Ensure essential indexes exist
        created_count = create_essential_indexes(cursor, to_keep)
        
        if removed_count > 0 or created_count > 0:
            # Step 6: Commit changes
            conn.commit()
            print(f"\n✅ Successfully cleaned up indexes!")
            print(f"   Removed: {removed_count} unnecessary indexes")
            print(f"   Created: {created_count} essential indexes")
            
            # Step 7: Analyze table
            analyze_table(cursor)
            
            # Step 8: Show final configuration
            show_final_indexes(cursor)
            
            print(f"\n🎉 Index cleanup completed successfully!")
            print(f"   Backup created: {BACKUP_PATH}")
        else:
            print("\n✅ No changes were needed")
        
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print("   Rolling back changes...")
        conn.rollback()
        print("   Please check the backup and restore if needed")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
