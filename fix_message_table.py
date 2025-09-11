#!/usr/bin/env python3
"""
Quick fix script to create the message table if it doesn't exist.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import Message

def fix_message_table():
    """Create the message table if it doesn't exist."""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔧 Checking for message table...")
            
            # Check if message table exists
            with db.engine.connect() as conn:
                result = conn.execute(db.text("SELECT name FROM sqlite_master WHERE type='table' AND name='message'"))
                table_exists = result.fetchone() is not None
                
                if table_exists:
                    print("✅ Message table already exists")
                else:
                    print("❌ Message table missing, creating it...")
                    # Create just the message table
                    Message.__table__.create(db.engine)
                    print("✅ Message table created successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return False

if __name__ == "__main__":
    success = fix_message_table()
    sys.exit(0 if success else 1)
