#!/usr/bin/env python3
"""
Script to create performance indexes for the tamermap database.

This script analyzes the query patterns and creates indexes to improve performance
for the most common database operations.
"""

from app import create_app
from app.extensions import db
from sqlalchemy import text

def create_performance_indexes():
    """Create indexes to improve database performance."""
    app = create_app()
    
    with app.app_context():
        print("Creating performance indexes...")
        
        # List of indexes to create with their purposes
        indexes = [
            # VisitorLog table - Most critical for analytics
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_timestamp',
                'columns': 'timestamp',
                'purpose': 'Analytics queries by date range'
            },
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_internal_referrer',
                'columns': 'is_internal_referrer',
                'purpose': 'Filter internal vs external traffic'
            },
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_ip_address',
                'columns': 'ip_address',
                'purpose': 'IP-based filtering and grouping'
            },
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_path',
                'columns': 'path',
                'purpose': 'Page visit analytics'
            },
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_ref_code',
                'columns': 'ref_code',
                'purpose': 'Referral code analytics'
            },
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_user_id',
                'columns': 'user_id',
                'purpose': 'User-specific analytics'
            },
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_timestamp_internal',
                'columns': 'timestamp, is_internal_referrer',
                'purpose': 'Combined date and internal traffic filtering'
            },
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_timestamp_path',
                'columns': 'timestamp, path',
                'purpose': 'Page analytics over time'
            },
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_timestamp_ref_code',
                'columns': 'timestamp, ref_code',
                'purpose': 'Referral analytics over time'
            },
            {
                'table': 'visitor_log',
                'name': 'idx_visitor_session_user',
                'columns': 'session_id, user_id',
                'purpose': 'Session-to-user linking for funnel tracking'
            },
            
            # Retailers table - Map performance
            {
                'table': 'retailers',
                'name': 'idx_retailer_type',
                'columns': 'retailer_type',
                'purpose': 'Filter by retailer type (kiosk, store, etc.)'
            },
            {
                'table': 'retailers',
                'name': 'idx_retailer_status',
                'columns': 'status',
                'purpose': 'Filter by retailer status'
            },
            {
                'table': 'retailers',
                'name': 'idx_retailer_machine_count',
                'columns': 'machine_count',
                'purpose': 'Sort by machine count'
            },
            {
                'table': 'retailers',
                'name': 'idx_retailer_type_status',
                'columns': 'retailer_type, status',
                'purpose': 'Combined type and status filtering'
            },
            {
                'table': 'retailers',
                'name': 'idx_retailer_enabled',
                'columns': 'enabled',
                'purpose': 'Filter enabled/disabled retailers'
            },
            
            # Events table - Event performance
            {
                'table': 'events',
                'name': 'idx_event_start_date',
                'columns': 'start_date',
                'purpose': 'Filter events by date range'
            },
            {
                'table': 'events',
                'name': 'idx_event_start_date_time',
                'columns': 'start_date, start_time',
                'purpose': 'Sort events chronologically'
            },
            
            # User table - User management
            {
                'table': 'user',
                'name': 'idx_user_pro_end_date',
                'columns': 'pro_end_date',
                'purpose': 'Pro user filtering and expiration tracking'
            },
            {
                'table': 'user',
                'name': 'idx_user_confirmed_at',
                'columns': 'confirmed_at',
                'purpose': 'User registration date analytics'
            },
            {
                'table': 'user',
                'name': 'idx_user_last_login',
                'columns': 'last_login',
                'purpose': 'User activity tracking'
            },
            {
                'table': 'user',
                'name': 'idx_user_active_pro',
                'columns': 'active, pro_end_date',
                'purpose': 'Active pro user queries'
            },
            
            # BillingEvent table - Payment analytics
            {
                'table': 'billing_event',
                'name': 'idx_billing_user_timestamp',
                'columns': 'user_id, event_timestamp',
                'purpose': 'User payment history'
            },
            {
                'table': 'billing_event',
                'name': 'idx_billing_event_type',
                'columns': 'event_type',
                'purpose': 'Payment event type filtering'
            },
            {
                'table': 'billing_event',
                'name': 'idx_billing_timestamp',
                'columns': 'event_timestamp',
                'purpose': 'Payment analytics by date'
            },
            
            # PinInteraction table - Map interaction analytics
            {
                'table': 'pin_interactions',
                'name': 'idx_pin_session_timestamp',
                'columns': 'session_id, timestamp',
                'purpose': 'Session interaction history'
            },
            {
                'table': 'pin_interactions',
                'name': 'idx_pin_marker_session',
                'columns': 'marker_id, session_id',
                'purpose': 'Marker-specific interactions'
            }
        ]
        
        # Create each index
        created_count = 0
        skipped_count = 0
        
        for index in indexes:
            try:
                # Check if index already exists
                check_result = db.session.execute(
                    text(f"PRAGMA index_list({index['table']})")
                ).fetchall()
                
                existing_indexes = [row[1] for row in check_result]
                
                if index['name'] in existing_indexes:
                    print(f"⏭️  Skipping {index['name']} (already exists)")
                    skipped_count += 1
                    continue
                
                # Create the index
                create_sql = f"CREATE INDEX {index['name']} ON {index['table']} ({index['columns']})"
                db.session.execute(text(create_sql))
                
                print(f"✅ Created {index['name']} on {index['table']} ({index['columns']})")
                print(f"   Purpose: {index['purpose']}")
                created_count += 1
                
            except Exception as e:
                print(f"❌ Failed to create {index['name']}: {str(e)}")
        
        # Commit all changes
        db.session.commit()
        
        print(f"\n📊 Index Creation Summary:")
        print(f"   Created: {created_count} indexes")
        print(f"   Skipped: {skipped_count} indexes (already exist)")
        print(f"   Total: {created_count + skipped_count} indexes")
        
        # Show current index count per table
        print(f"\n📋 Current Index Count by Table:")
        tables = ['visitor_log', 'retailers', 'events', 'user', 'billing_event', 'pin_interactions']
        for table in tables:
            result = db.session.execute(text(f"PRAGMA index_list({table})")).fetchall()
            print(f"   {table}: {len(result)} indexes")

def analyze_query_performance():
    """Analyze current query performance and suggest optimizations."""
    app = create_app()
    
    with app.app_context():
        print("\n🔍 Query Performance Analysis:")
        
        # Check table sizes
        tables = ['visitor_log', 'retailers', 'events', 'user', 'billing_event', 'pin_interactions']
        for table in tables:
            try:
                result = db.session.execute(text(f"SELECT COUNT(*) as count FROM {table}")).fetchone()
                print(f"   {table}: {result[0]:,} rows")
            except Exception as e:
                print(f"   {table}: Error - {str(e)}")
        
        # Check most common query patterns
        print(f"\n📈 Most Critical Query Patterns:")
        print(f"   1. VisitorLog timestamp filtering (analytics)")
        print(f"   2. VisitorLog is_internal_referrer filtering")
        print(f"   3. Retailers latitude/longitude range queries (map)")
        print(f"   4. Events start_date filtering (upcoming events)")
        print(f"   5. User pro_end_date filtering (pro users)")
        print(f"   6. BillingEvent user_id + event_timestamp (payment history)")

if __name__ == "__main__":
    create_performance_indexes()
    analyze_query_performance() 