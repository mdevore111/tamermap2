#!/usr/bin/env python3
"""
Add is_pro field to visitor_log table

This script adds the is_pro field to the visitor_log table to track
whether visitors are Pro users or not. This will fix the Admin > Visit Trends
showing only non-Pro visits.
"""

import sqlite3
import os
import shutil
from datetime import datetime

# Database configuration
DB_PATH = "instance/tamermap_data.db"
BACKUP_PATH = f"instance/tamermap_data_backup_add_is_pro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"

def backup_database():
    """Create a backup before making changes"""
    print(f"🔒 Creating backup: {BACKUP_PATH}")
    shutil.copy2(DB_PATH, BACKUP_PATH)
    print(f"✅ Backup created successfully")
    return True

def add_is_pro_column():
    """Add is_pro column to visitor_log table"""
    print("🔧 Adding is_pro column to visitor_log table...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(visitor_log)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_pro' in columns:
            print("✅ is_pro column already exists")
            return 0
        
        # Add the column
        cursor.execute("ALTER TABLE visitor_log ADD COLUMN is_pro BOOLEAN DEFAULT FALSE")
        
        # Update existing records with user_id to have correct is_pro status
        cursor.execute("""
            UPDATE visitor_log 
            SET is_pro = (
                SELECT u.is_pro 
                FROM user u 
                WHERE u.id = visitor_log.user_id
            )
            WHERE user_id IS NOT NULL
        """)
        
        updated_count = cursor.rowcount
        print(f"✅ Updated {updated_count} existing visitor_log records with Pro status")
        
        conn.commit()
        return updated_count
        
    except Exception as e:
        print(f"❌ Error adding is_pro column: {e}")
        conn.rollback()
        return -1
    finally:
        conn.close()

def verify_changes():
    """Verify the changes were applied correctly"""
    print("🔍 Verifying changes...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(visitor_log)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_pro' in columns:
            print("✅ is_pro column successfully added")
            
            # Check some sample data
            cursor.execute("""
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN is_pro = 1 THEN 1 END) as pro_count,
                       COUNT(CASE WHEN is_pro = 0 THEN 1 END) as non_pro_count
                FROM visitor_log
                WHERE user_id IS NOT NULL
            """)
            stats = cursor.fetchone()
            
            print(f"   Total visitor_log records with user_id: {stats[0]}")
            print(f"   Pro users: {stats[1]}")
            print(f"   Non-Pro users: {stats[2]}")
            
            return True
        else:
            print("❌ is_pro column not found")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying changes: {e}")
        return False
    finally:
        conn.close()

def main():
    """Main migration process"""
    print("🔧 Add is_pro field to visitor_log table")
    print("=" * 60)
    
    # Step 1: Create backup
    if not backup_database():
        print("❌ Backup failed - cannot proceed")
        return
    
    # Step 2: Add is_pro column
    updated_count = add_is_pro_column()
    
    if updated_count >= 0:
        # Step 3: Verify changes
        if verify_changes():
            print("\n" + "=" * 60)
            print("📈 MIGRATION SUMMARY")
            print("=" * 60)
            print(f"✅ is_pro column added to visitor_log table")
            print(f"✅ {updated_count} existing records updated with Pro status")
            print(f"🔒 Backup created: {BACKUP_PATH}")
            print(f"\n💡 Admin > Visit Trends should now show Pro vs non-Pro visits correctly")
        else:
            print("❌ Verification failed - check the backup and restore if needed")
    else:
        print("❌ Migration failed - check the backup and restore if needed")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        print("Please check the backup and restore if needed")
