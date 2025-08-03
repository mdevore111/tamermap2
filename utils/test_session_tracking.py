#!/usr/bin/env python3
"""
Test script to verify session tracking is working correctly.
Run this after implementing the session tracking integration.
"""

import sys
import os
from datetime import datetime, timedelta

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_session_tracking():
    """Test that session tracking is working."""
    try:
        from app import create_app, db
        from app.models import VisitorLog
        from app.session_middleware import get_or_create_session_id, generate_session_id
        
        app = create_app()
        
        with app.app_context():
            print("🧪 Testing Session Tracking Integration...")
            print("=" * 50)
            
            # Test 1: Session ID Generation
            print("1. Testing session ID generation...")
            session_id = generate_session_id()
            print(f"   ✅ Generated session ID: {session_id[:8]}...")
            
            # Test 2: Database Schema
            print("\n2. Testing database schema...")
            # Check if session_id column exists
            try:
                # Try to query the session_id column
                recent_visits = VisitorLog.query.filter(
                    VisitorLog.session_id.isnot(None)
                ).limit(1).all()
                print("   ✅ session_id column exists and is queryable")
            except Exception as e:
                print(f"   ❌ Error querying session_id: {e}")
                return False
            
            # Test 3: Recent Data
            print("\n3. Checking recent visitor data...")
            total_visits = VisitorLog.query.count()
            visits_with_session = VisitorLog.query.filter(
                VisitorLog.session_id.isnot(None)
            ).count()
            
            print(f"   📊 Total visits: {total_visits:,}")
            print(f"   📊 Visits with session_id: {visits_with_session:,}")
            print(f"   📊 Percentage with session_id: {(visits_with_session/total_visits*100):.1f}%")
            
            if visits_with_session > 0:
                print("   ✅ Session tracking is active!")
            else:
                print("   ⚠️  No visits with session_id yet - this is normal for new implementation")
            
            # Test 4: Sample Recent Visits
            print("\n4. Sample recent visits:")
            recent_visits = VisitorLog.query.order_by(
                VisitorLog.timestamp.desc()
            ).limit(5).all()
            
            for i, visit in enumerate(recent_visits, 1):
                session_status = "✅" if visit.session_id else "❌"
                print(f"   {i}. {visit.path} - {visit.timestamp.strftime('%Y-%m-%d %H:%M')} - Session: {session_status}")
            
            # Test 5: Analytics Functions
            print("\n5. Testing analytics functions...")
            try:
                from app.admin_utils import get_referral_journey_data
                
                # Test with a sample referral code (if any exist)
                sample_ref = db.session.query(VisitorLog.ref_code).filter(
                    VisitorLog.ref_code.isnot(None),
                    VisitorLog.ref_code != ''
                ).first()
                
                if sample_ref:
                    journey_data = get_referral_journey_data(sample_ref[0], days=7)
                    print(f"   ✅ Analytics function works - tracking method: {journey_data.get('tracking_method', 'unknown')}")
                else:
                    print("   ⚠️  No referral codes found to test analytics")
                    
            except Exception as e:
                print(f"   ❌ Error testing analytics: {e}")
            
            print("\n" + "=" * 50)
            print("🎉 Session Tracking Test Complete!")
            print("\n📝 Next Steps:")
            print("   1. Restart your application")
            print("   2. Visit your site to generate new session IDs")
            print("   3. Check admin analytics for improved tracking")
            print("   4. Monitor the percentage of visits with session_id")
            
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_session_tracking()
    sys.exit(0 if success else 1) 