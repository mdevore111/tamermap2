#!/usr/bin/env python3
"""
Database setup script to create all required tables.
This script creates all necessary tables for the TamerMap application.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import User, Retailer, Event, UserNote, LegendClick, VisitorLog

def setup_database_tables():
    """Create all required database tables."""
    app = create_app()
    
    with app.app_context():
        try:
            print("🔧 Setting up database tables...")
            
            # Get all existing tables
            with db.engine.connect() as conn:
                result = conn.execute(db.text("SELECT name FROM sqlite_master WHERE type='table'"))
                existing_tables = [row[0] for row in result.fetchall()]
                print(f"📋 Existing tables: {existing_tables}")
            
            # Create all tables
            print("🏗️  Creating all tables...")
            db.create_all()
            print("✅ All tables created successfully")
            
            # Verify tables were created
            with db.engine.connect() as conn:
                result = conn.execute(db.text("SELECT name FROM sqlite_master WHERE type='table'"))
                new_tables = [row[0] for row in result.fetchall()]
                print(f"📋 Tables after creation: {new_tables}")
                
                # Check specific tables
                required_tables = ['user', 'retailer', 'event', 'user_notes', 'legend_click', 'visitor_log']
                for table in required_tables:
                    if table in new_tables:
                        print(f"✅ {table} table exists")
                    else:
                        print(f"❌ {table} table missing")
            
            return True
            
        except Exception as e:
            print(f"❌ Error setting up database tables: {e}")
            return False

if __name__ == "__main__":
    success = setup_database_tables()
    sys.exit(0 if success else 1)
