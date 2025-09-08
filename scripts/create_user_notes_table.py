#!/usr/bin/env python3
"""
Create the user_notes table with correct foreign key references.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db

def create_user_notes_table():
    """Create the user_notes table."""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔧 Creating user_notes table...")
            
            # Create the table using raw SQL to avoid model loading issues
            with db.engine.connect() as conn:
                # Create the user_notes table
                conn.execute(db.text("""
                    CREATE TABLE IF NOT EXISTS user_notes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        retailer_id INTEGER NOT NULL,
                        notes TEXT NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES user (id),
                        FOREIGN KEY (retailer_id) REFERENCES retailers (id)
                    )
                """))
                conn.commit()
                print("✅ user_notes table created successfully")
                
                # Verify the table was created
                result = conn.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='user_notes'"))
                if result.fetchone():
                    print("✅ user_notes table verified in database")
                else:
                    print("❌ user_notes table not found in database")
                    return False
                    
            return True
            
        except Exception as e:
            print(f"❌ Error creating user_notes table: {e}")
            return False

if __name__ == "__main__":
    success = create_user_notes_table()
    sys.exit(0 if success else 1)
