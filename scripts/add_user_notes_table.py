#!/usr/bin/env python3
"""
Database migration script to add user_notes table.

This script adds the user_notes table to support per-user notes for locations.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import UserNote

def add_user_notes_table():
    """Add the user_notes table to the database."""
    app = create_app()
    
    with app.app_context():
        try:
            # Create the user_notes table
            db.create_all()
            print("✅ Successfully created user_notes table")
            
            # Verify the table was created
            result = db.engine.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_notes'")
            if result.fetchone():
                print("✅ user_notes table verified in database")
            else:
                print("❌ user_notes table not found in database")
                
        except Exception as e:
            print(f"❌ Error creating user_notes table: {e}")
            return False
            
    return True

if __name__ == "__main__":
    success = add_user_notes_table()
    sys.exit(0 if success else 1)
