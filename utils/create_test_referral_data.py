#!/usr/bin/env python3
"""
Create test referral data for local development testing.
This script adds some sample referral visits to test the admin analytics.
"""

import sys
import os
from datetime import datetime, timedelta
import random

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def create_test_referral_data():
    """Create test referral data for local testing."""
    try:
        from app import create_app, db
        from app.models import VisitorLog
        from app.session_middleware import generate_session_id
        
        app = create_app()
        
        with app.app_context():
            print("🧪 Creating Test Referral Data...")
            print("=" * 50)
            
            # Test referral codes
            test_refs = ['TEST123', 'DEMO456', 'LOCAL789', 'DEV001', 'SAMPLE002']
            
            # Sample paths
            paths = ['/', '/maps', '/learn', '/play', '/privacy', '/terms']
            
            # Create test data for the last 7 days
            for i in range(7):
                date = datetime.utcnow() - timedelta(days=i)
                
                for ref_code in test_refs:
                    # Create 2-5 visits per referral code per day
                    num_visits = random.randint(2, 5)
                    
                    for j in range(num_visits):
                        # Create session ID
                        session_id = generate_session_id()
                        
                        # Random time within the day
                        visit_time = date + timedelta(
                            hours=random.randint(0, 23),
                            minutes=random.randint(0, 59)
                        )
                        
                        # Create visitor log entry
                        visitor_log = VisitorLog(
                            session_id=session_id,
                            ip_address=f"192.168.1.{random.randint(1, 254)}",
                            path=random.choice(paths),
                            method='GET',
                            referrer=f"https://example.com/?ref={ref_code}",
                            ref_code=ref_code,
                            user_agent=f"Mozilla/5.0 (Test Browser) TestBot/1.0",
                            user_id=None,  # Guest visits
                            timestamp=visit_time,
                            country='US',
                            region='California',
                            city='San Francisco',
                            latitude=37.7749,
                            longitude=-122.4194,
                            is_internal_referrer=False
                        )
                        
                        db.session.add(visitor_log)
            
            # Commit all the test data
            db.session.commit()
            
            print("✅ Created test referral data!")
            print(f"📊 Added visits for referral codes: {', '.join(test_refs)}")
            print(f"📅 Data spans the last 7 days")
            print("\n🎯 Now try visiting:")
            print("   http://localhost:5000/admin/referral-journeys")
            print("\n📝 The page should now load with test data!")
            
            return True
            
    except Exception as e:
        print(f"❌ Error creating test data: {e}")
        return False

if __name__ == "__main__":
    success = create_test_referral_data()
    sys.exit(0 if success else 1) 