#!/usr/bin/env python3
"""
Fix the message table schema by adding missing columns.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db

def fix_message_table_schema():
    """Add missing columns to the message table."""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔧 Checking message table schema...")
            
            # Check current columns
            with db.engine.connect() as conn:
                result = conn.execute(db.text("PRAGMA table_info(message)"))
                current_columns = [row[1] for row in result.fetchall()]
                print(f"📋 Current columns: {current_columns}")
                
                # Define all required columns
                required_columns = {
                    'is_new_location': 'BOOLEAN DEFAULT 0',
                    'is_admin_report': 'BOOLEAN DEFAULT 0', 
                    'form_type': 'VARCHAR(50)',
                    'name': 'VARCHAR(255)',
                    'address': 'VARCHAR(255)',
                    'email': 'VARCHAR(255)',
                    'win_type': 'VARCHAR(50)',
                    'location_used': 'VARCHAR(255)',
                    'cards_found': 'VARCHAR(255)',
                    'time_saved': 'VARCHAR(100)',
                    'money_saved': 'VARCHAR(100)',
                    'allow_feature': 'BOOLEAN DEFAULT 0'
                }
                
                # Add missing columns
                for column_name, column_def in required_columns.items():
                    if column_name not in current_columns:
                        print(f"➕ Adding missing column: {column_name}")
                        try:
                            conn.execute(db.text(f"ALTER TABLE message ADD COLUMN {column_name} {column_def}"))
                            print(f"✅ Added {column_name}")
                        except Exception as e:
                            print(f"❌ Error adding {column_name}: {e}")
                    else:
                        print(f"✅ {column_name} already exists")
                
                conn.commit()
                print("✅ Message table schema updated successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

if __name__ == "__main__":
    success = fix_message_table_schema()
    sys.exit(0 if success else 1)
