#!/usr/bin/env python3
"""
Add missing columns to the message table.
"""

import sqlite3

def add_missing_columns():
    """Add missing columns to the message table."""
    try:
        # Connect to the database
        conn = sqlite3.connect('instance/tamermap_data.db')
        cursor = conn.cursor()
        
        print("🔧 Checking message table schema...")
        
        # Check current columns
        cursor.execute("PRAGMA table_info(message)")
        current_columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Current columns: {current_columns}")
        
        # Define missing columns to add
        missing_columns = [
            "ALTER TABLE message ADD COLUMN is_new_location BOOLEAN DEFAULT 0",
            "ALTER TABLE message ADD COLUMN is_admin_report BOOLEAN DEFAULT 0", 
            "ALTER TABLE message ADD COLUMN form_type VARCHAR(50)",
            "ALTER TABLE message ADD COLUMN name VARCHAR(255)",
            "ALTER TABLE message ADD COLUMN address VARCHAR(255)",
            "ALTER TABLE message ADD COLUMN email VARCHAR(255)",
            "ALTER TABLE message ADD COLUMN win_type VARCHAR(50)",
            "ALTER TABLE message ADD COLUMN location_used VARCHAR(255)",
            "ALTER TABLE message ADD COLUMN cards_found VARCHAR(255)",
            "ALTER TABLE message ADD COLUMN time_saved VARCHAR(100)",
            "ALTER TABLE message ADD COLUMN money_saved VARCHAR(100)",
            "ALTER TABLE message ADD COLUMN allow_feature BOOLEAN DEFAULT 0"
        ]
        
        # Add missing columns
        for sql in missing_columns:
            column_name = sql.split("ADD COLUMN ")[1].split(" ")[0]
            if column_name not in current_columns:
                print(f"➕ Adding column: {column_name}")
                try:
                    cursor.execute(sql)
                    print(f"✅ Added {column_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        print(f"✅ {column_name} already exists")
                    else:
                        print(f"❌ Error adding {column_name}: {e}")
            else:
                print(f"✅ {column_name} already exists")
        
        conn.commit()
        conn.close()
        print("✅ Message table schema updated successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = add_missing_columns()
    exit(0 if success else 1)
