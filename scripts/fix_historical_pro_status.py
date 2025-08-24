#!/usr/bin/env python3
"""
Fix Historical Pro User Status Script

This script fixes the is_pro field in existing legend_clicks and route_events records
by looking up the actual Pro status from the user table.

This is needed because the session-based Pro detection was broken, causing all
engagement tracking to be marked as non-Pro users.
"""

import sqlite3
import os
import shutil
from datetime import datetime

# Database configuration
DB_PATH = "instance/tamermap_data.db"
BACKUP_PATH = f"instance/tamermap_data_backup_pro_status_fix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def backup_database():
    """Create a backup before making changes"""
    print(f"🔒 Creating backup: {BACKUP_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"✅ Backup created successfully")
    return True

def get_current_stats():
    """Get current statistics about Pro vs non-Pro records"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Legend clicks stats
    cursor.execute("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN is_pro = 1 THEN 1 END) as pro_count,
               COUNT(CASE WHEN is_pro = 0 THEN 1 END) as non_pro_count
        FROM legend_clicks
    """)
    legend_stats = cursor.fetchone()
    
    # Route events stats
    cursor.execute("""
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN is_pro = 1 THEN 1 END) as pro_count,
               COUNT(CASE WHEN is_pro = 0 THEN 1 END) as non_pro_count
        FROM route_events
    """)
    route_stats = cursor.fetchone()
    
    # Users with Pro status
    cursor.execute("""
        SELECT COUNT(*) as total_pro_users
        FROM user 
        WHERE is_pro = 1
    """)
    pro_users = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'legend_clicks': {
            'total': legend_stats[0],
            'pro': legend_stats[1],
            'non_pro': legend_stats[2]
        },
        'route_events': {
            'total': route_stats[0],
            'pro': route_stats[1],
            'non_pro': route_stats[2]
        },
        'pro_users': pro_users
    }

def fix_legend_clicks_pro_status():
    """Fix Pro status in legend_clicks table"""
    print("🔧 Fixing Pro status in legend_clicks table...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all legend clicks with user_id
    cursor.execute("""
        SELECT lc.id, lc.user_id, lc.is_pro
        FROM legend_clicks lc
        WHERE lc.user_id IS NOT NULL
        ORDER BY lc.id
    """)
    records = cursor.fetchall()
    
    updated_count = 0
    for record_id, user_id, current_is_pro in records:
        # Get actual Pro status from user table
        cursor.execute("SELECT is_pro FROM user WHERE id = ?", (user_id,))
        user_result = cursor.fetchone()
        
        if user_result:
            actual_is_pro = user_result[0]
            
            # Update if different
            if current_is_pro != actual_is_pro:
                cursor.execute("""
                    UPDATE legend_clicks 
                    SET is_pro = ? 
                    WHERE id = ?
                """, (actual_is_pro, record_id))
                updated_count += 1
                
                if updated_count <= 10:  # Show first 10 updates
                    print(f"   Updated legend_click {record_id}: user {user_id} Pro status {current_is_pro} -> {actual_is_pro}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Updated {updated_count} legend_clicks records")
    return updated_count

def fix_route_events_pro_status():
    """Fix Pro status in route_events table"""
    print("🔧 Fixing Pro status in route_events table...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all route events with user_id
    cursor.execute("""
        SELECT re.id, re.user_id, re.is_pro
        FROM route_events re
        WHERE re.user_id IS NOT NULL
        ORDER BY re.id
    """)
    records = cursor.fetchall()
    
    updated_count = 0
    for record_id, user_id, current_is_pro in records:
        # Get actual Pro status from user table
        cursor.execute("SELECT is_pro FROM user WHERE id = ?", (user_id,))
        user_result = cursor.fetchone()
        
        if user_result:
            actual_is_pro = user_result[0]
            
            # Update if different
            if current_is_pro != actual_is_pro:
                cursor.execute("""
                    UPDATE route_events 
                    SET is_pro = ? 
                    WHERE id = ?
                """, (actual_is_pro, record_id))
                updated_count += 1
                
                if updated_count <= 10:  # Show first 10 updates
                    print(f"   Updated route_event {record_id}: user {user_id} Pro status {current_is_pro} -> {actual_is_pro}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Updated {updated_count} route_events records")
    return updated_count

def main():
    """Main fix process"""
    print("🔧 Historical Pro User Status Fix Script")
    print("=" * 60)
    
    # Step 1: Get current statistics
    print("\n📊 Current statistics:")
    stats = get_current_stats()
    
    print(f"   Pro users in system: {stats['pro_users']}")
    print(f"   Legend clicks: {stats['legend_clicks']['total']} total, {stats['legend_clicks']['pro']} Pro, {stats['legend_clicks']['non_pro']} non-Pro")
    print(f"   Route events: {stats['route_events']['total']} total, {stats['route_events']['pro']} Pro, {stats['route_events']['non_pro']} non-Pro")
    
    # Step 2: Create backup
    if not backup_database():
        print("❌ Backup failed - cannot proceed")
        return
    
    # Step 3: Fix legend clicks
    legend_updated = fix_legend_clicks_pro_status()
    
    # Step 4: Fix route events
    route_updated = fix_route_events_pro_status()
    
    # Step 5: Get new statistics
    print("\n📊 New statistics after fix:")
    new_stats = get_current_stats()
    
    print(f"   Legend clicks: {new_stats['legend_clicks']['total']} total, {new_stats['legend_clicks']['pro']} Pro, {new_stats['legend_clicks']['non_pro']} non-Pro")
    print(f"   Route events: {new_stats['route_events']['total']} total, {new_stats['route_events']['pro']} Pro, {new_stats['route_events']['non_pro']} non-Pro")
    
    # Step 6: Summary
    print("\n" + "=" * 60)
    print("📈 FIX SUMMARY")
    print("=" * 60)
    
    print(f"✅ Legend clicks updated: {legend_updated}")
    print(f"✅ Route events updated: {route_updated}")
    print(f"🔒 Backup created: {BACKUP_PATH}")
    
    if legend_updated > 0 or route_updated > 0:
        print(f"\n🎉 Pro user status has been fixed!")
        print(f"   Admin > Engagement should now show Pro vs non-Pro traffic correctly")
        print(f"   Historical data has been corrected")
    else:
        print(f"\n✅ No updates needed - Pro status was already correct")
    
    print(f"\n💡 To verify: Check Admin > Engagement page")
    print(f"   You should now see Pro user traffic in the charts and tables")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print("Please check the backup and restore if needed")
