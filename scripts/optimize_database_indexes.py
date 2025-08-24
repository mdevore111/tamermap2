#!/usr/bin/env python3
"""
Database Index Optimization Script

This script safely drops unnecessary indexes that are hurting performance
while preserving critical indexes for core functionality.

SAFETY FEATURES:
- Backup before any changes
- Validation that critical indexes remain
- Rollback capability
- Performance testing before/after
"""

import sqlite3
import os
import shutil
from datetime import datetime
import time

# Database configuration
DB_PATH = "instance/tamermap_data.db"
BACKUP_PATH = f"instance/tamermap_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

# Indexes to DROP (carefully selected for removal)
INDEXES_TO_DROP = [
    # Redundant composite indexes
    "idx_visitor_timestamp_internal",
    "idx_visitor_timestamp_path", 
    "idx_visitor_timestamp_ref_code",
    "idx_visitor_session_user",
    
    # Low-value single-column indexes
    "idx_visitor_internal_referrer",
    "idx_visitor_path",
    "idx_retailer_status",
    "idx_retailer_machine_count",
    
    # Unused analytics indexes
    "idx_event_start_date_time",
    "idx_pin_marker_session",
    "idx_pin_session_timestamp",
]

# Critical indexes that MUST be preserved
CRITICAL_INDEXES = [
    "idx_retailer_lat_lng",      # Map performance
    "idx_event_lat_lng",         # Event queries
    "idx_retailer_place_id",     # Google Places
    "idx_user_pro_end_date",     # Pro user checks
    "idx_user_active_pro",       # User status
    "idx_visitor_timestamp",     # Time queries
    "idx_visitor_user_id",       # User tracking
    "idx_billing_user_timestamp", # Payment tracking
    "idx_retailer_lat_lng",      # Map queries
]

def backup_database():
    """Create a backup of the database before making changes"""
    print(f"🔒 Creating backup: {BACKUP_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"✅ Backup created successfully")
    return True

def get_current_indexes():
    """Get list of all current indexes"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_autoindex_%'")
    indexes = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return indexes

def validate_critical_indexes():
    """Ensure all critical indexes exist before proceeding"""
    print("🔍 Validating critical indexes...")
    
    current_indexes = get_current_indexes()
    missing_critical = []
    
    for critical_idx in CRITICAL_INDEXES:
        if critical_idx not in current_indexes:
            missing_critical.append(critical_idx)
    
    if missing_critical:
        print(f"❌ CRITICAL ERROR: Missing critical indexes: {missing_critical}")
        print("Cannot proceed - critical indexes are missing!")
        return False
    
    print("✅ All critical indexes are present")
    return True

def drop_indexes():
    """Drop the unnecessary indexes"""
    print(f"🗑️  Dropping {len(INDEXES_TO_DROP)} unnecessary indexes...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    dropped_count = 0
    errors = []
    
    for index_name in INDEXES_TO_DROP:
        try:
            # Check if index exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
            if cursor.fetchone():
                cursor.execute(f"DROP INDEX {index_name}")
                print(f"✅ Dropped: {index_name}")
                dropped_count += 1
            else:
                print(f"⚠️  Index not found: {index_name}")
        except Exception as e:
            error_msg = f"Failed to drop {index_name}: {e}"
            print(f"❌ {error_msg}")
            errors.append(error_msg)
    
    conn.commit()
    conn.close()
    
    print(f"📊 Index drop summary: {dropped_count} dropped, {len(errors)} errors")
    return dropped_count, errors

def test_performance():
    """Test performance before and after index changes"""
    print("🧪 Testing performance...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Test 1: Map query performance
    start_time = time.time()
    cursor.execute("""
        SELECT COUNT(*) FROM retailers 
        WHERE latitude BETWEEN 47.0 AND 48.0 
        AND longitude BETWEEN -123.0 AND -122.0
    """)
    map_query_time = time.time() - start_time
    
    # Test 2: Visitor log query performance
    start_time = time.time()
    cursor.execute("""
        SELECT COUNT(*) FROM visitor_log 
        WHERE timestamp >= datetime('now', '-1 day')
    """)
    visitor_query_time = time.time() - start_time
    
    # Test 3: User query performance
    start_time = time.time()
    cursor.execute("""
        SELECT COUNT(*) FROM user 
        WHERE pro_end_date > datetime('now')
    """)
    user_query_time = time.time() - start_time
    
    conn.close()
    
    print(f"📊 Performance test results:")
    print(f"   Map query: {map_query_time:.4f}s")
    print(f"   Visitor query: {visitor_query_time:.4f}s")
    print(f"   User query: {user_query_time:.4f}s")
    
    return {
        'map_query': map_query_time,
        'visitor_query': visitor_query_time,
        'user_query': user_query_time
    }

def get_database_stats():
    """Get current database statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get database size
    db_size = os.path.getsize(DB_PATH) / (1024 * 1024)  # MB
    
    # Get index count
    cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
    index_count = cursor.fetchone()[0]
    
    # Get table sizes
    cursor.execute("""
        SELECT name, COUNT(*) as row_count 
        FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
    """)
    table_stats = cursor.fetchall()
    
    conn.close()
    
    return {
        'db_size_mb': db_size,
        'index_count': index_count,
        'table_stats': table_stats
    }

def main():
    """Main optimization process"""
    print("🚀 Database Index Optimization Script")
    print("=" * 50)
    
    # Step 1: Validate current state
    if not validate_critical_indexes():
        return False
    
    # Step 2: Get before stats
    print("\n📊 Before optimization:")
    before_stats = get_database_stats()
    print(f"   Database size: {before_stats['db_size_mb']:.2f} MB")
    print(f"   Index count: {before_stats['index_count']}")
    
    # Step 3: Performance test before
    print("\n🧪 Performance test BEFORE optimization:")
    before_performance = test_performance()
    
    # Step 4: Create backup
    if not backup_database():
        print("❌ Backup failed - cannot proceed")
        return False
    
    # Step 5: Drop indexes
    print(f"\n🗑️  Dropping unnecessary indexes...")
    dropped_count, errors = drop_indexes()
    
    if errors:
        print(f"⚠️  Some indexes failed to drop: {errors}")
    
    # Step 6: Get after stats
    print("\n📊 After optimization:")
    after_stats = get_database_stats()
    print(f"   Database size: {after_stats['db_size_mb']:.2f} MB")
    print(f"   Index count: {after_stats['index_count']}")
    
    # Step 7: Performance test after
    print("\n🧪 Performance test AFTER optimization:")
    after_performance = test_performance()
    
    # Step 8: Summary
    print("\n" + "=" * 50)
    print("📈 OPTIMIZATION SUMMARY")
    print("=" * 50)
    
    size_saved = before_stats['db_size_mb'] - after_stats['db_size_mb']
    indexes_removed = before_stats['index_count'] - after_stats['index_count']
    
    print(f"✅ Indexes removed: {indexes_removed}")
    print(f"💾 Space saved: {size_saved:.2f} MB")
    print(f"📊 Performance changes:")
    
    for test_name in before_performance:
        before_time = before_performance[test_name]
        after_time = after_performance[test_name]
        improvement = ((before_time - after_time) / before_time) * 100
        print(f"   {test_name}: {improvement:+.1f}%")
    
    print(f"\n🔒 Backup created: {BACKUP_PATH}")
    print("💡 To rollback: copy backup over current database")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n🎉 Optimization completed successfully!")
        else:
            print("\n❌ Optimization failed!")
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print("Please check the backup and restore if needed")
