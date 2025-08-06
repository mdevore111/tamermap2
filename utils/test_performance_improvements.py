#!/usr/bin/env python3
"""
Script to test and measure performance improvements from the new database indexes.
"""

import time
from app import create_app
from app.extensions import db
from app.models import VisitorLog, Retailer, Event, User, BillingEvent
from sqlalchemy import text, func, desc, and_, or_
from datetime import datetime, timedelta

def measure_query_time(func, *args, **kwargs):
    """Measure the execution time of a function."""
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    return result, (end_time - start_time) * 1000  # Convert to milliseconds

def test_visitor_log_queries():
    """Test VisitorLog query performance."""
    print("🔍 Testing VisitorLog Query Performance:")
    
    # Test 1: Date range filtering
    def test_timestamp_filter():
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        return VisitorLog.query.filter(VisitorLog.timestamp >= thirty_days_ago).count()
    
    result, time_ms = measure_query_time(test_timestamp_filter)
    print(f"   📅 Date range filter (30 days): {result:,} records in {time_ms:.2f}ms")
    
    # Test 2: Internal traffic filtering
    def test_internal_filter():
        return VisitorLog.query.filter_by(is_internal_referrer=False).count()
    
    result, time_ms = measure_query_time(test_internal_filter)
    print(f"   🌐 External traffic filter: {result:,} records in {time_ms:.2f}ms")
    
    # Test 3: Combined timestamp and internal filter
    def test_combined_filter():
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        return VisitorLog.query.filter(
            and_(
                VisitorLog.timestamp >= thirty_days_ago,
                VisitorLog.is_internal_referrer == False
            )
        ).count()
    
    result, time_ms = measure_query_time(test_combined_filter)
    print(f"   🔗 Combined date + external filter: {result:,} records in {time_ms:.2f}ms")
    
    # Test 4: Page analytics
    def test_page_analytics():
        return db.session.query(
            VisitorLog.path,
            func.count(VisitorLog.id).label('visits')
        ).filter(
            and_(
                VisitorLog.timestamp >= datetime.utcnow() - timedelta(days=30),
                VisitorLog.is_internal_referrer == False
            )
        ).group_by(VisitorLog.path).order_by(desc('visits')).limit(10).all()
    
    result, time_ms = measure_query_time(test_page_analytics)
    print(f"   📊 Top pages analytics: {len(result)} results in {time_ms:.2f}ms")
    
    # Test 5: Referral code analytics
    def test_ref_code_analytics():
        return db.session.query(
            VisitorLog.ref_code,
            func.count(VisitorLog.id).label('visits')
        ).filter(
            and_(
                VisitorLog.timestamp >= datetime.utcnow() - timedelta(days=30),
                VisitorLog.ref_code.isnot(None),
                VisitorLog.is_internal_referrer == False
            )
        ).group_by(VisitorLog.ref_code).order_by(desc('visits')).limit(10).all()
    
    result, time_ms = measure_query_time(test_ref_code_analytics)
    print(f"   🎯 Top referral codes: {len(result)} results in {time_ms:.2f}ms")

def test_retailer_queries():
    """Test Retailer query performance."""
    print("\n🏪 Testing Retailer Query Performance:")
    
    # Test 1: Type filtering
    def test_type_filter():
        return Retailer.query.filter_by(retailer_type='kiosk').count()
    
    result, time_ms = measure_query_time(test_type_filter)
    print(f"   🏪 Kiosk filter: {result:,} records in {time_ms:.2f}ms")
    
    # Test 2: Status filtering
    def test_status_filter():
        return Retailer.query.filter_by(status='active').count()
    
    result, time_ms = measure_query_time(test_status_filter)
    print(f"   ✅ Active status filter: {result:,} records in {time_ms:.2f}ms")
    
    # Test 3: Combined type and status
    def test_combined_retailer():
        return Retailer.query.filter(
            and_(
                Retailer.retailer_type == 'kiosk',
                Retailer.status == 'active'
            )
        ).count()
    
    result, time_ms = measure_query_time(test_combined_retailer)
    print(f"   🔗 Kiosk + active filter: {result:,} records in {time_ms:.2f}ms")
    
    # Test 4: Machine count sorting
    def test_machine_sort():
        return Retailer.query.order_by(desc(Retailer.machine_count)).limit(10).all()
    
    result, time_ms = measure_query_time(test_machine_sort)
    print(f"   🔢 Top machine count: {len(result)} results in {time_ms:.2f}ms")

def test_event_queries():
    """Test Event query performance."""
    print("\n📅 Testing Event Query Performance:")
    
    # Test 1: Date filtering
    def test_date_filter():
        return Event.query.filter(Event.start_date >= '2025-08-01').count()
    
    result, time_ms = measure_query_time(test_date_filter)
    print(f"   📅 Future events filter: {result:,} records in {time_ms:.2f}ms")
    
    # Test 2: Date and time sorting
    def test_date_time_sort():
        return Event.query.filter(
            Event.start_date >= '2025-08-01'
        ).order_by(Event.start_date, Event.start_time).limit(10).all()
    
    result, time_ms = measure_query_time(test_date_time_sort)
    print(f"   ⏰ Chronological events: {len(result)} results in {time_ms:.2f}ms")

def test_user_queries():
    """Test User query performance."""
    print("\n👤 Testing User Query Performance:")
    
    # Test 1: Pro user filtering
    def test_pro_users():
        return User.query.filter(User.pro_end_date > datetime.utcnow()).count()
    
    result, time_ms = measure_query_time(test_pro_users)
    print(f"   👑 Pro users filter: {result:,} records in {time_ms:.2f}ms")
    
    # Test 2: Active pro users
    def test_active_pro():
        return User.query.filter(
            and_(
                User.active == True,
                User.pro_end_date > datetime.utcnow()
            )
        ).count()
    
    result, time_ms = measure_query_time(test_active_pro)
    print(f"   ✅ Active pro users: {result:,} records in {time_ms:.2f}ms")
    
    # Test 3: Recent registrations
    def test_recent_registrations():
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        return User.query.filter(User.confirmed_at >= thirty_days_ago).count()
    
    result, time_ms = measure_query_time(test_recent_registrations)
    print(f"   📈 Recent registrations: {result:,} records in {time_ms:.2f}ms")

def test_billing_queries():
    """Test BillingEvent query performance."""
    print("\n💳 Testing BillingEvent Query Performance:")
    
    # Test 1: User payment history
    def test_user_payments():
        return BillingEvent.query.filter_by(user_id=1).order_by(desc(BillingEvent.event_timestamp)).limit(10).all()
    
    result, time_ms = measure_query_time(test_user_payments)
    print(f"   👤 User payment history: {len(result)} results in {time_ms:.2f}ms")
    
    # Test 2: Event type filtering
    def test_event_type():
        return BillingEvent.query.filter_by(event_type='checkout.session.completed').count()
    
    result, time_ms = measure_query_time(test_event_type)
    print(f"   🎯 Completed checkouts: {result:,} records in {time_ms:.2f}ms")
    
    # Test 3: Recent payments
    def test_recent_payments():
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        return BillingEvent.query.filter(BillingEvent.event_timestamp >= thirty_days_ago).count()
    
    result, time_ms = measure_query_time(test_recent_payments)
    print(f"   📅 Recent payments: {result:,} records in {time_ms:.2f}ms")

def test_map_viewport_queries():
    """Test map viewport query performance."""
    print("\n🗺️ Testing Map Viewport Query Performance:")
    
    # Test 1: Retailer viewport query
    def test_retailer_viewport():
        # Simulate a viewport around San Francisco
        bounds = {
            'north': 37.8,
            'south': 37.7,
            'east': -122.4,
            'west': -122.5
        }
        
        query = """
            SELECT id, retailer, retailer_type, latitude, longitude
            FROM retailers
            WHERE latitude BETWEEN :south AND :north
            AND longitude BETWEEN :west AND :east
            AND latitude IS NOT NULL AND longitude IS NOT NULL
        """
        
        with db.engine.connect() as connection:
            result = connection.execute(text(query), bounds)
            return [dict(row._mapping) for row in result]
    
    result, time_ms = measure_query_time(test_retailer_viewport)
    print(f"   🏪 Retailer viewport query: {len(result)} results in {time_ms:.2f}ms")
    
    # Test 2: Event viewport query
    def test_event_viewport():
        bounds = {
            'north': 37.8,
            'south': 37.7,
            'east': -122.4,
            'west': -122.5
        }
        
        query = """
            SELECT id, event_title, start_date, latitude, longitude
            FROM events
            WHERE latitude BETWEEN :south AND :north
            AND longitude BETWEEN :west AND :east
            AND latitude IS NOT NULL AND longitude IS NOT NULL
            AND start_date >= date('now')
        """
        
        with db.engine.connect() as connection:
            result = connection.execute(text(query), bounds)
            return [dict(row._mapping) for row in result]
    
    result, time_ms = measure_query_time(test_event_viewport)
    print(f"   📅 Event viewport query: {len(result)} results in {time_ms:.2f}ms")

def run_performance_tests():
    """Run all performance tests."""
    app = create_app()
    
    with app.app_context():
        print("🚀 Database Performance Test Suite")
        print("=" * 50)
        
        test_visitor_log_queries()
        test_retailer_queries()
        test_event_queries()
        test_user_queries()
        test_billing_queries()
        test_map_viewport_queries()
        
        print("\n" + "=" * 50)
        print("✅ Performance tests completed!")
        print("\n💡 Performance Tips:")
        print("   • Queries under 10ms are excellent")
        print("   • Queries under 50ms are good")
        print("   • Queries over 100ms may need optimization")
        print("   • Monitor slow queries in production")

if __name__ == "__main__":
    run_performance_tests() 