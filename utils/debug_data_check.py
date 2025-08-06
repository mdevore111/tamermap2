#!/usr/bin/env python3
"""
Debug script to check if there's data in the key tables for analytics
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models import User, VisitorLog, Event, Retailer, Message, Role, PinInteraction, BillingEvent
from datetime import datetime, timedelta

def check_data():
    app = create_app()
    with app.app_context():
        print("=== Database Data Check ===\n")
        
        # Check basic counts
        print("Basic Table Counts:")
        print(f"Users: {User.query.count()}")
        print(f"VisitorLogs: {VisitorLog.query.count()}")
        print(f"Events: {Event.query.count()}")
        print(f"Retailers: {Retailer.query.count()}")
        print(f"Messages: {Message.query.count()}")
        print(f"PinInteractions: {PinInteraction.query.count()}")
        print(f"BillingEvents: {BillingEvent.query.count()}")
        
        print("\n=== Recent Data (Last 30 Days) ===")
        since = datetime.utcnow() - timedelta(days=30)
        
        recent_visits = VisitorLog.query.filter(VisitorLog.timestamp >= since).count()
        print(f"Recent visits (30 days): {recent_visits}")
        
        recent_visits_with_ref = VisitorLog.query.filter(
            VisitorLog.timestamp >= since,
            VisitorLog.ref_code.isnot(None),
            VisitorLog.ref_code != ''
        ).count()
        print(f"Recent visits with referral codes: {recent_visits_with_ref}")
        
        # Check for referral codes
        ref_codes = db.session.query(VisitorLog.ref_code).filter(
            VisitorLog.ref_code.isnot(None),
            VisitorLog.ref_code != ''
        ).distinct().all()
        print(f"Unique referral codes: {len(ref_codes)}")
        if ref_codes:
            print(f"Sample referral codes: {[r[0] for r in ref_codes[:5]]}")
        
        # Check for pin interactions
        recent_pins = PinInteraction.query.filter(PinInteraction.timestamp >= since).count()
        print(f"Recent pin interactions (30 days): {recent_pins}")
        
        # Check for pro users
        pro_users = User.query.filter(User.pro_end_date > datetime.utcnow()).count()
        print(f"Active pro users: {pro_users}")
        
        print("\n=== Sample Data ===")
        
        # Sample visitor logs
        sample_visits = VisitorLog.query.limit(3).all()
        print(f"Sample visitor logs: {len(sample_visits)}")
        for visit in sample_visits:
            print(f"  - {visit.timestamp}: {visit.path} (ref_code: {visit.ref_code})")
        
        # Sample pin interactions
        sample_pins = PinInteraction.query.limit(3).all()
        print(f"Sample pin interactions: {len(sample_pins)}")
        for pin in sample_pins:
            print(f"  - {pin.timestamp}: session_id={pin.session_id}")

if __name__ == "__main__":
    check_data() 