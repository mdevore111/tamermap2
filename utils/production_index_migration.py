#!/usr/bin/env python3
"""
Production-safe migration script for database performance indexes.
This script only creates indexes and can be safely run on production.
"""

import sys
import os
sys.path.append('.')

from app import create_app
from app.extensions import db
from sqlalchemy import text
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_production_indexes():
    """Create performance indexes on production database."""
    app = create_app()
    
    with app.app_context():
        logger.info("Starting production index migration...")
        
        # List of indexes to create
        indexes = [
            # VisitorLog table
            ('visitor_log', 'idx_visitor_timestamp', 'timestamp'),
            ('visitor_log', 'idx_visitor_internal_referrer', 'is_internal_referrer'),
            ('visitor_log', 'idx_visitor_ip_address', 'ip_address'),
            ('visitor_log', 'idx_visitor_path', 'path'),
            ('visitor_log', 'idx_visitor_ref_code', 'ref_code'),
            ('visitor_log', 'idx_visitor_user_id', 'user_id'),
            ('visitor_log', 'idx_visitor_timestamp_internal', 'timestamp, is_internal_referrer'),
            ('visitor_log', 'idx_visitor_timestamp_path', 'timestamp, path'),
            ('visitor_log', 'idx_visitor_timestamp_ref_code', 'timestamp, ref_code'),
            ('visitor_log', 'idx_visitor_session_user', 'session_id, user_id'),
            
            # Retailers table
            ('retailers', 'idx_retailer_type', 'retailer_type'),
            ('retailers', 'idx_retailer_status', 'status'),
            ('retailers', 'idx_retailer_machine_count', 'machine_count'),
            ('retailers', 'idx_retailer_type_status', 'retailer_type, status'),
            
            # Events table
            ('events', 'idx_event_start_date', 'start_date'),
            ('events', 'idx_event_start_date_time', 'start_date, start_time'),
            
            # User table
            ('user', 'idx_user_pro_end_date', 'pro_end_date'),
            ('user', 'idx_user_confirmed_at', 'confirmed_at'),
            ('user', 'idx_user_last_login', 'last_login'),
            ('user', 'idx_user_active_pro', 'active, pro_end_date'),
            
            # BillingEvent table
            ('billing_event', 'idx_billing_user_timestamp', 'user_id, event_timestamp'),
            ('billing_event', 'idx_billing_event_type', 'event_type'),
            ('billing_event', 'idx_billing_timestamp', 'event_timestamp'),
            
            # PinInteraction table
            ('pin_interactions', 'idx_pin_session_timestamp', 'session_id, timestamp'),
            ('pin_interactions', 'idx_pin_marker_session', 'marker_id, session_id')
        ]
        
        created_count = 0
        skipped_count = 0
        error_count = 0
        
        for table, index_name, columns in indexes:
            try:
                # Check if index already exists
                check_result = db.session.execute(
                    text(f"PRAGMA index_list({table})")
                ).fetchall()
                
                existing_indexes = [row[1] for row in check_result]
                
                if index_name in existing_indexes:
                    logger.info(f"⏭️  Skipping {index_name} (already exists)")
                    skipped_count += 1
                    continue
                
                # Create the index
                create_sql = f"CREATE INDEX {index_name} ON {table} ({columns})"
                db.session.execute(text(create_sql))
                
                logger.info(f"✅ Created {index_name} on {table} ({columns})")
                created_count += 1
                
            except Exception as e:
                logger.error(f"❌ Failed to create {index_name}: {str(e)}")
                error_count += 1
                db.session.rollback()
        
        # Commit all successful changes
        if created_count > 0:
            db.session.commit()
            logger.info(f"✅ Committed {created_count} new indexes")
        
        # Summary
        logger.info(f"\n📊 Migration Summary:")
        logger.info(f"   Created: {created_count} indexes")
        logger.info(f"   Skipped: {skipped_count} indexes (already exist)")
        logger.info(f"   Errors: {error_count} indexes")
        logger.info(f"   Total: {created_count + skipped_count + error_count} indexes")
        
        if error_count > 0:
            logger.warning(f"⚠️  {error_count} indexes failed to create. Check logs for details.")
        else:
            logger.info("🎉 All indexes created successfully!")

def verify_indexes():
    """Verify that all expected indexes exist."""
    app = create_app()
    
    with app.app_context():
        logger.info("🔍 Verifying indexes...")
        
        expected_indexes = {
            'visitor_log': 11,
            'retailers': 7,
            'events': 3,
            'user': 4,
            'billing_event': 3,
            'pin_interactions': 4
        }
        
        for table, expected_count in expected_indexes.items():
            try:
                result = db.session.execute(text(f"PRAGMA index_list({table})")).fetchall()
                actual_count = len(result)
                status = "✅" if actual_count >= expected_count else "❌"
                logger.info(f"   {status} {table}: {actual_count}/{expected_count} indexes")
            except Exception as e:
                logger.error(f"   ❌ {table}: Error - {str(e)}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Production index migration')
    parser.add_argument('--verify-only', action='store_true', help='Only verify existing indexes')
    parser.add_argument('--create-only', action='store_true', help='Only create indexes, skip verification')
    
    args = parser.parse_args()
    
    if args.verify_only:
        verify_indexes()
    elif args.create_only:
        create_production_indexes()
    else:
        create_production_indexes()
        print("\n" + "="*50)
        verify_indexes() 