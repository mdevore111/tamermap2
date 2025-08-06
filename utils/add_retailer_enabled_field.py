#!/usr/bin/env python3
"""
Migration script to add 'enabled' field to retailers table.
This script adds a boolean 'enabled' field with default value True.
"""

import sys
sys.path.append('.')

from app import create_app
from app.extensions import db
from sqlalchemy import text
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_retailer_enabled_field():
    """Add enabled field to retailers table."""
    app = create_app()
    
    with app.app_context():
        logger.info("Starting migration: Add 'enabled' field to retailers table...")
        
        try:
            # Check if the column already exists
            check_result = db.session.execute(
                text("PRAGMA table_info(retailers)")
            ).fetchall()
            
            existing_columns = [row[1] for row in check_result]
            
            if 'enabled' in existing_columns:
                logger.info("✅ 'enabled' column already exists in retailers table")
                return
            
            # Add the enabled column with default value True
            logger.info("Adding 'enabled' column to retailers table...")
            db.session.execute(
                text("ALTER TABLE retailers ADD COLUMN enabled BOOLEAN DEFAULT 1")
            )
            
            # Update existing records to have enabled = True
            logger.info("Setting enabled = True for all existing retailers...")
            db.session.execute(
                text("UPDATE retailers SET enabled = 1 WHERE enabled IS NULL")
            )
            
            # Commit the changes
            db.session.commit()
            
            logger.info("✅ Successfully added 'enabled' field to retailers table")
            logger.info("✅ All existing retailers set to enabled = True")
            
            # Verify the change
            verify_result = db.session.execute(
                text("PRAGMA table_info(retailers)")
            ).fetchall()
            
            enabled_column = None
            for row in verify_result:
                if row[1] == 'enabled':
                    enabled_column = row
                    break
            
            if enabled_column:
                logger.info(f"✅ Verification: 'enabled' column exists with type: {enabled_column[2]}")
                
                # Check count of enabled retailers
                count_result = db.session.execute(
                    text("SELECT COUNT(*) as total, SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) as enabled_count FROM retailers")
                ).fetchone()
                
                logger.info(f"📊 Retailer counts: Total={count_result[0]}, Enabled={count_result[1]}")
            else:
                logger.error("❌ Verification failed: 'enabled' column not found")
                
        except Exception as e:
            logger.error(f"❌ Migration failed: {str(e)}")
            db.session.rollback()
            raise

def verify_retailer_enabled_field():
    """Verify the enabled field was added correctly."""
    app = create_app()
    
    with app.app_context():
        logger.info("🔍 Verifying 'enabled' field in retailers table...")
        
        try:
            # Check column exists
            check_result = db.session.execute(
                text("PRAGMA table_info(retailers)")
            ).fetchall()
            
            enabled_column = None
            for row in check_result:
                if row[1] == 'enabled':
                    enabled_column = row
                    break
            
            if enabled_column:
                logger.info(f"✅ 'enabled' column exists: {enabled_column}")
                
                # Check data
                data_result = db.session.execute(
                    text("SELECT COUNT(*) as total, SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) as enabled_count, SUM(CASE WHEN enabled = 0 THEN 1 ELSE 0 END) as disabled_count FROM retailers")
                ).fetchone()
                
                logger.info(f"📊 Data verification:")
                logger.info(f"   Total retailers: {data_result[0]}")
                logger.info(f"   Enabled retailers: {data_result[1]}")
                logger.info(f"   Disabled retailers: {data_result[2]}")
                
                # Show a few sample records
                sample_result = db.session.execute(
                    text("SELECT id, retailer, enabled FROM retailers LIMIT 5")
                ).fetchall()
                
                logger.info("📋 Sample retailers:")
                for row in sample_result:
                    logger.info(f"   ID {row[0]}: {row[1]} (enabled: {row[2]})")
                    
            else:
                logger.error("❌ 'enabled' column not found in retailers table")
                
        except Exception as e:
            logger.error(f"❌ Verification failed: {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Add enabled field to retailers table')
    parser.add_argument('--verify-only', action='store_true', help='Only verify the field exists')
    parser.add_argument('--migrate-only', action='store_true', help='Only run migration, skip verification')
    
    args = parser.parse_args()
    
    if args.verify_only:
        verify_retailer_enabled_field()
    elif args.migrate_only:
        add_retailer_enabled_field()
    else:
        add_retailer_enabled_field()
        print("\n" + "="*50)
        verify_retailer_enabled_field() 