#!/usr/bin/env python3
"""
Comprehensive script to show all traffic filtering results across the entire database.
Shows the impact of internal traffic filtering on all analytics.
"""

from datetime import datetime, timedelta
from app import create_app
from app.models import VisitorLog
from app.extensions import db
from sqlalchemy import func

def test_all_traffic_filtering():
    """Test all traffic filtering across the entire database."""
    app = create_app()
    
    with app.app_context():
        print("=== COMPREHENSIVE TRAFFIC FILTERING ANALYSIS ===")
        print()
        
        # Overall database statistics
        total_records = VisitorLog.query.count()
        total_internal = VisitorLog.query.filter_by(is_internal_referrer=True).count()
        total_external = VisitorLog.query.filter_by(is_internal_referrer=False).count()
        
        print(f"📊 DATABASE OVERVIEW:")
        print(f"   Total visits: {total_records:,}")
        print(f"   External visits: {total_external:,}")
        print(f"   Internal visits: {total_internal:,}")
        print(f"   Internal percentage: {(total_internal/total_records*100):.1f}%")
        print()
        
        # Monitor traffic analysis
        monitor_total = VisitorLog.query.filter_by(ip_address='10.48.0.2').count()
        monitor_internal = VisitorLog.query.filter_by(ip_address='10.48.0.2', is_internal_referrer=True).count()
        monitor_external = VisitorLog.query.filter_by(ip_address='10.48.0.2', is_internal_referrer=False).count()
        
        print(f"🔍 MONITOR TRAFFIC (10.48.0.2):")
        print(f"   Total monitor visits: {monitor_total:,}")
        print(f"   Monitor internal: {monitor_internal:,}")
        print(f"   Monitor external: {monitor_external:,}")
        print(f"   Monitor percentage of total: {(monitor_total/total_records*100):.1f}%")
        print()
        
        # Top pages analysis (all time)
        print(f"📈 TOP 10 PAGES (ALL TIME - EXTERNAL ONLY):")
        top_pages_external = db.session.query(
            VisitorLog.path,
            func.count(VisitorLog.id).label('visits')
        ).filter(
            VisitorLog.is_internal_referrer == False
        ).group_by(VisitorLog.path).order_by(
            func.count(VisitorLog.id).desc()
        ).limit(10).all()
        
        for i, (path, visits) in enumerate(top_pages_external, 1):
            print(f"   {i:2d}. {path}: {visits:,}")
        
        print()
        
        # Top pages analysis (all time - including internal)
        print(f"📈 TOP 10 PAGES (ALL TIME - INCLUDING INTERNAL):")
        top_pages_all = db.session.query(
            VisitorLog.path,
            func.count(VisitorLog.id).label('visits')
        ).group_by(VisitorLog.path).order_by(
            func.count(VisitorLog.id).desc()
        ).limit(10).all()
        
        for i, (path, visits) in enumerate(top_pages_all, 1):
            print(f"   {i:2d}. {path}: {visits:,}")
        
        print()
        
        # Checkout page detailed analysis
        print(f"💳 CHECKOUT PAGE ANALYSIS:")
        checkout_total = VisitorLog.query.filter_by(path='/payment/create-checkout-session').count()
        checkout_external = VisitorLog.query.filter_by(
            path='/payment/create-checkout-session', 
            is_internal_referrer=False
        ).count()
        checkout_internal = VisitorLog.query.filter_by(
            path='/payment/create-checkout-session', 
            is_internal_referrer=True
        ).count()
        checkout_monitor = VisitorLog.query.filter_by(
            path='/payment/create-checkout-session',
            ip_address='10.48.0.2'
        ).count()
        
        print(f"   Total checkout visits: {checkout_total:,}")
        print(f"   External checkout visits: {checkout_external:,}")
        print(f"   Internal checkout visits: {checkout_internal:,}")
        print(f"   Monitor checkout visits: {checkout_monitor:,}")
        print(f"   External percentage: {(checkout_external/checkout_total*100):.1f}%")
        print()
        
        # Monthly breakdown
        print(f"📅 MONTHLY BREAKDOWN (LAST 6 MONTHS):")
        for i in range(6):
            month_start = datetime.utcnow().replace(day=1) - timedelta(days=30*i)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_total = VisitorLog.query.filter(
                VisitorLog.timestamp >= month_start,
                VisitorLog.timestamp <= month_end
            ).count()
            
            month_external = VisitorLog.query.filter(
                VisitorLog.timestamp >= month_start,
                VisitorLog.timestamp <= month_end,
                VisitorLog.is_internal_referrer == False
            ).count()
            
            month_internal = VisitorLog.query.filter(
                VisitorLog.timestamp >= month_start,
                VisitorLog.timestamp <= month_end,
                VisitorLog.is_internal_referrer == True
            ).count()
            
            print(f"   {month_start.strftime('%Y-%m')}: {month_total:,} total, {month_external:,} external, {month_internal:,} internal")
        
        print()
        
        # IP address analysis
        print(f"🌐 TOP INTERNAL IP ADDRESSES:")
        top_internal_ips = db.session.query(
            VisitorLog.ip_address,
            func.count(VisitorLog.id).label('visits')
        ).filter(
            VisitorLog.is_internal_referrer == True
        ).group_by(VisitorLog.ip_address).order_by(
            func.count(VisitorLog.id).desc()
        ).limit(10).all()
        
        for i, (ip, visits) in enumerate(top_internal_ips, 1):
            print(f"   {i:2d}. {ip}: {visits:,}")
        
        print()
        
        # Validation checks
        print(f"✅ VALIDATION CHECKS:")
        
        # Math check
        if total_records == total_external + total_internal:
            print(f"   ✅ Total = External + Internal: {total_records:,} = {total_external:,} + {total_internal:,}")
        else:
            print(f"   ❌ Math check failed!")
        
        # Monitor check
        if monitor_external == 0:
            print(f"   ✅ Monitor traffic properly excluded from external")
        else:
            print(f"   ❌ Monitor traffic incorrectly included in external: {monitor_external}")
        
        if monitor_internal == monitor_total:
            print(f"   ✅ Monitor traffic properly marked as internal")
        else:
            print(f"   ❌ Monitor traffic incorrectly marked: {monitor_internal}/{monitor_total}")
        
        # Checkout page check
        if checkout_external + checkout_internal == checkout_total:
            print(f"   ✅ Checkout page math check passed")
        else:
            print(f"   ❌ Checkout page math check failed!")
        
        if checkout_external == 0:
            print(f"   ✅ Checkout page properly shows 0 external visits")
        else:
            print(f"   ❌ Checkout page incorrectly shows {checkout_external} external visits")

if __name__ == "__main__":
    test_all_traffic_filtering() 