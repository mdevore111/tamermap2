#!/usr/bin/env python3
"""
Database Performance Optimization Script

This script adds missing indexes to improve query performance based on
analysis of the most frequently used queries in the application.
"""

import sqlite3
import os
from datetime import datetime

# Database configuration
DB_PATH = "instance/tamermap_data.db"
BACKUP_PATH = f"instance/tamermap_data_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def create_backup():
    """Create a backup of the database before making changes"""
    import shutil
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"✅ Database backup created: {BACKUP_PATH}")

def add_indexes():
    """Add performance-critical indexes"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get current indexes
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")
    existing_indexes = {row[0] for row in cursor.fetchall()}
    
    # Define indexes to add based on query analysis
    indexes_to_add = [
        # Retailer table indexes (most frequently queried)
        {
            'name': 'idx_retailers_enabled',
            'table': 'retailers',
            'columns': 'enabled',
            'description': 'Filter by enabled status (used in all retailer queries)'
        },
        {
            'name': 'idx_retailers_retailer_type',
            'table': 'retailers', 
            'columns': 'retailer_type',
            'description': 'Filter by retailer type (kiosk, store, etc.)'
        },
        {
            'name': 'idx_retailers_lat_lng',
            'table': 'retailers',
            'columns': 'latitude, longitude',
            'description': 'Geographic queries and bounding box filters'
        },
        {
            'name': 'idx_retailers_place_id',
            'table': 'retailers',
            'columns': 'place_id',
            'description': 'Lookups by Google Place ID'
        },
        {
            'name': 'idx_retailers_enabled_type',
            'table': 'retailers',
            'columns': 'enabled, retailer_type',
            'description': 'Composite index for common filter combinations'
        },
        
        # PinInteraction table indexes
        {
            'name': 'idx_pin_interaction_timestamp',
            'table': 'pin_interaction',
            'columns': 'timestamp',
            'description': 'Time-based queries for heatmap data'
        },
        {
            'name': 'idx_pin_interaction_marker_id',
            'table': 'pin_interaction',
            'columns': 'marker_id',
            'description': 'Lookups by marker/place_id'
        },
        {
            'name': 'idx_pin_interaction_session_id',
            'table': 'pin_interaction',
            'columns': 'session_id',
            'description': 'User session tracking'
        },
        
        # PinPopularity table indexes
        {
            'name': 'idx_pin_popularity_place_id',
            'table': 'pin_popularity',
            'columns': 'place_id',
            'description': 'Lookups by place_id for popularity data'
        },
        {
            'name': 'idx_pin_popularity_count',
            'table': 'pin_popularity',
            'columns': 'interaction_count',
            'description': 'Sorting by popularity'
        },
        
        # UserNote table indexes
        {
            'name': 'idx_user_notes_user_id',
            'table': 'user_notes',
            'columns': 'user_id',
            'description': 'User-specific note lookups'
        },
        {
            'name': 'idx_user_notes_retailer_id',
            'table': 'user_notes',
            'columns': 'retailer_id',
            'description': 'Retailer-specific note lookups'
        },
        {
            'name': 'idx_user_notes_user_retailer',
            'table': 'user_notes',
            'columns': 'user_id, retailer_id',
            'description': 'Composite index for user-retailer note lookups'
        },
        
        # MapUsage table indexes
        {
            'name': 'idx_map_usage_session_id',
            'table': 'map_usage',
            'columns': 'session_id',
            'description': 'Session-based usage tracking'
        },
        {
            'name': 'idx_map_usage_timestamp',
            'table': 'map_usage',
            'columns': 'timestamp',
            'description': 'Time-based usage analysis'
        },
        
        # VisitorLog table indexes
        {
            'name': 'idx_visitor_log_timestamp',
            'table': 'visitor_log',
            'columns': 'timestamp',
            'description': 'Time-based visitor analysis'
        },
        {
            'name': 'idx_visitor_log_path',
            'table': 'visitor_log',
            'columns': 'path',
            'description': 'Page view analysis'
        },
        {
            'name': 'idx_visitor_log_ip',
            'table': 'visitor_log',
            'columns': 'ip_address',
            'description': 'IP-based analysis'
        }
    ]
    
    added_count = 0
    skipped_count = 0
    
    for index_def in indexes_to_add:
        index_name = index_def['name']
        
        if index_name in existing_indexes:
            print(f"⏭️  Skipping {index_name} (already exists)")
            skipped_count += 1
            continue
            
        try:
            sql = f"CREATE INDEX {index_name} ON {index_def['table']} ({index_def['columns']})"
            cursor.execute(sql)
            print(f"✅ Added {index_name}: {index_def['description']}")
            added_count += 1
        except sqlite3.Error as e:
            print(f"❌ Failed to create {index_name}: {e}")
    
    conn.commit()
    conn.close()
    
    return added_count, skipped_count

def analyze_query_performance():
    """Analyze current query performance"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n📊 QUERY PERFORMANCE ANALYSIS")
    print("=" * 50)
    
    # Enable query plan analysis
    cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM retailers WHERE enabled = 1 AND retailer_type LIKE '%kiosk%'")
    plan = cursor.fetchall()
    print("Sample query plan for retailer filtering:")
    for row in plan:
        print(f"  {row}")
    
    # Get table statistics
    tables = ['retailers', 'pin_interaction', 'pin_popularity', 'user_notes', 'map_usage', 'visitor_log']
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count:,} rows")
        except sqlite3.Error:
            print(f"  {table}: Table not found")
    
    conn.close()

def main():
    """Main optimization function"""
    print("🗄️ Starting database performance optimization...")
    
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        return False
    
    # Create backup
    create_backup()
    
    # Add indexes
    print("\n📈 Adding performance indexes...")
    added, skipped = add_indexes()
    
    # Analyze performance
    analyze_query_performance()
    
    # Summary
    print(f"\n📊 OPTIMIZATION SUMMARY")
    print("=" * 50)
    print(f"✅ Indexes added: {added}")
    print(f"⏭️  Indexes skipped: {skipped}")
    print(f"🔒 Backup created: {BACKUP_PATH}")
    print(f"💡 To rollback: copy backup over current database")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        if success:
            print("\n🎉 Database optimization completed successfully!")
        else:
            print("\n❌ Database optimization failed!")
    except Exception as e:
        print(f"\n❌ Error during optimization: {e}")
