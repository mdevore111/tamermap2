#!/usr/bin/env python3
"""
Add is_new_location field to Message table.

This script adds the is_new_location boolean field to the Message table
to support the enhanced location reporting functionality.
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.insert(0, str(Path(__file__).parent.parent))

def add_is_new_location_field():
    """Add is_new_location field to Message table."""
    
    # Get database path - use Unix path for server deployment
    db_path = '/home/tamermap/app/instance/tamermap_data.db'
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if the column already exists
        cursor.execute("PRAGMA table_info(message)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_new_location' in columns:
            print("is_new_location field already exists in Message table")
            return True
        
        # Add the new column
        cursor.execute("""
            ALTER TABLE message 
            ADD COLUMN is_new_location BOOLEAN DEFAULT 0
        """)
        
        conn.commit()
        print("Successfully added is_new_location field to Message table")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(message)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_new_location' in columns:
            print("Verification: is_new_location field successfully added")
            return True
        else:
            print("Error: is_new_location field was not added")
            return False
            
    except Exception as e:
        print(f"Error adding is_new_location field: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = add_is_new_location_field()
    sys.exit(0 if success else 1)
