#!/usr/bin/env python3
"""
Add out_of_business field to message table
"""

import os
import sys
import sqlite3

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

def add_out_of_business_field():
    """Add out_of_business field to message table"""
    
    # Get database path
    db_path = os.path.join(project_root, 'instance', 'tamermap_data.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(message)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'out_of_business' in columns:
            print("Column 'out_of_business' already exists in message table")
            return True
        
        # Add the new column
        cursor.execute("ALTER TABLE message ADD COLUMN out_of_business BOOLEAN DEFAULT 0")
        
        # Commit changes
        conn.commit()
        print("Successfully added 'out_of_business' column to message table")
        
        # Verify the column was added
        cursor.execute("PRAGMA table_info(message)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'out_of_business' in columns:
            print("Column verification successful")
        else:
            print("Column verification failed")
            return False
            
        return True
        
    except Exception as e:
        print(f"Error adding column: {e}")
        return False
        
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    print("Adding out_of_business field to message table...")
    success = add_out_of_business_field()
    
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")
        sys.exit(1)
