#!/usr/bin/env python3
"""
Database migration script to add session_id column to visitor_log table.
This script can be run safely multiple times and will handle existing data.
"""

import sys
import os
import sqlite3
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    return any(col[1] == column_name for col in columns)

def add_session_id_column():
    """Add session_id column to visitor_log table if it doesn't exist."""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'tamermap_data.db')
    
    if not os.path.exists(db_path):
        print(f"Database file not found: {db_path}")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if session_id column already exists
        if check_column_exists(cursor, 'visitor_log', 'session_id'):
            print("✅ session_id column already exists in visitor_log table")
            conn.close()
            return True
        
        # Add the session_id column
        print("🔄 Adding session_id column to visitor_log table...")
        cursor.execute("""
            ALTER TABLE visitor_log 
            ADD COLUMN session_id VARCHAR(100)
        """)
        
        # Commit the changes
        conn.commit()
        
        # Verify the column was added
        if check_column_exists(cursor, 'visitor_log', 'session_id'):
            print("✅ Successfully added session_id column to visitor_log table")
            
            # Get row count for reference
            cursor.execute("SELECT COUNT(*) FROM visitor_log")
            row_count = cursor.fetchone()[0]
            print(f"📊 Current visitor_log table has {row_count:,} records")
            
            conn.close()
            return True
        else:
            print("❌ Failed to add session_id column")
            conn.close()
            return False
            
    except Exception as e:
        print(f"❌ Error adding session_id column: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def create_session_id_index():
    """Create an index on session_id for better query performance."""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'tamermap_data.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if index already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_visitor_log_session_id'")
        if cursor.fetchone():
            print("✅ session_id index already exists")
            conn.close()
            return True
        
        # Create index
        print("🔄 Creating index on session_id column...")
        cursor.execute("""
            CREATE INDEX idx_visitor_log_session_id 
            ON visitor_log(session_id)
        """)
        
        conn.commit()
        print("✅ Successfully created session_id index")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error creating session_id index: {e}")
        if 'conn' in locals():
            conn.close()
        return False

def main():
    """Main migration function."""
    print("🚀 Starting session_id migration...")
    print(f"📅 Migration started at: {datetime.now()}")
    
    # Step 1: Add session_id column
    if not add_session_id_column():
        print("❌ Migration failed at step 1")
        return False
    
    # Step 2: Create index
    if not create_session_id_index():
        print("❌ Migration failed at step 2")
        return False
    
    print("🎉 Migration completed successfully!")
    print("📝 Next steps:")
    print("   1. Update your logging middleware to generate session IDs")
    print("   2. Restart your application")
    print("   3. New visits will automatically get session IDs")
    print("   4. Existing analytics will continue to work with fallback logic")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 