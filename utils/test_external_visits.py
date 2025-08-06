#!/usr/bin/env python3
"""
Test script to validate external visits for a single day directly from the database.
This helps verify that internal traffic filtering is working correctly.
"""

from datetime import datetime, timedelta
from app import create_app
from app.models import VisitorLog
from app.extensions import db
from sqlalchemy import func

def test_external_visits():
    """Test external visits for a single day to validate internal traffic filtering."""
    app = create_app()
    
    with app.app_context():
        # Test for today and yesterday
        today = datetime.utcnow().date()
        yesterday = today - timedelta(days=1)
        
        print("=== EXTERNAL VISITS VALIDATION ===")
        print(f"Testing for: {today} (today) and {yesterday} (yesterday)")
        print()
        
        for test_date in [yesterday, today]:
            print(f"--- {test_date} ---")
            
            # Get all visits for this date
            all_visits = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date
            ).count()
            
            # Get external visits (not internal)
            external_visits = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.is_internal_referrer == False
            ).count()
            
            # Get internal visits
            internal_visits = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.is_internal_referrer == True
            ).count()
            
            # Get visits from 10.48.0.2 specifically
            monitor_visits = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.ip_address == '10.48.0.2'
            ).count()
            
            # Get external visits from 10.48.0.2 (should be 0)
            monitor_external = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.ip_address == '10.48.0.2',
                VisitorLog.is_internal_referrer == False
            ).count()
            
            # Get internal visits from 10.48.0.2 (should be all)
            monitor_internal = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.ip_address == '10.48.0.2',
                VisitorLog.is_internal_referrer == True
            ).count()
            
            print(f"Total visits: {all_visits}")
            print(f"External visits: {external_visits}")
            print(f"Internal visits: {internal_visits}")
            print(f"Monitor visits (10.48.0.2): {monitor_visits}")
            print(f"Monitor external: {monitor_external} (should be 0)")
            print(f"Monitor internal: {monitor_internal} (should be {monitor_visits})")
            print()
            
            # Validate the math
            if all_visits == external_visits + internal_visits:
                print("✅ Math check: Total = External + Internal")
            else:
                print("❌ Math check failed!")
            
            if monitor_external == 0:
                print("✅ Monitor traffic properly excluded from external")
            else:
                print(f"❌ Monitor traffic incorrectly included in external: {monitor_external}")
            
            if monitor_internal == monitor_visits:
                print("✅ Monitor traffic properly marked as internal")
            else:
                print(f"❌ Monitor traffic incorrectly marked: {monitor_internal}/{monitor_visits}")
            
            print()
        
        # Test specific page visits
        print("--- TOP PAGES VALIDATION ---")
        for test_date in [yesterday, today]:
            print(f"\n{test_date} - Top pages (external only):")
            
            # Get top pages for external visits only
            top_pages = db.session.query(
                VisitorLog.path,
                func.count(VisitorLog.id).label('visits')
            ).filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.is_internal_referrer == False
            ).group_by(VisitorLog.path).order_by(
                func.count(VisitorLog.id).desc()
            ).limit(10).all()
            
            for path, visits in top_pages:
                print(f"  {path}: {visits}")
        
        # Test checkout page specifically
        print("\n--- CHECKOUT PAGE VALIDATION ---")
        for test_date in [yesterday, today]:
            print(f"\n{test_date} - /payment/create-checkout-session:")
            
            # Total visits to checkout page
            total_checkout = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.path == '/payment/create-checkout-session'
            ).count()
            
            # External visits to checkout page
            external_checkout = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.path == '/payment/create-checkout-session',
                VisitorLog.is_internal_referrer == False
            ).count()
            
            # Internal visits to checkout page
            internal_checkout = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.path == '/payment/create-checkout-session',
                VisitorLog.is_internal_referrer == True
            ).count()
            
            # Monitor visits to checkout page
            monitor_checkout = VisitorLog.query.filter(
                func.date(VisitorLog.timestamp) == test_date,
                VisitorLog.path == '/payment/create-checkout-session',
                VisitorLog.ip_address == '10.48.0.2'
            ).count()
            
            print(f"  Total: {total_checkout}")
            print(f"  External: {external_checkout}")
            print(f"  Internal: {internal_checkout}")
            print(f"  Monitor: {monitor_checkout}")
            
            if external_checkout + internal_checkout == total_checkout:
                print("  ✅ Math check passed")
            else:
                print("  ❌ Math check failed")

if __name__ == "__main__":
    test_external_visits() 