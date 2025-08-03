#!/usr/bin/env python3
"""
Simple test to isolate the admin_utils issue.
"""

import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def simple_test():
    """Simple test of admin_utils."""
    try:
        print("🧪 Simple Admin Utils Test...")
        print("=" * 30)
        
        # Test 1: Import
        print("1. Testing imports...")
        from app import create_app
        from app.admin_utils import exclude_monitor_traffic
        print("   ✅ Imports successful")
        
        # Test 2: App context
        print("2. Testing app context...")
        app = create_app()
        with app.app_context():
            print("   ✅ App context successful")
            
            # Test 3: Basic query
            print("3. Testing basic query...")
            from app.models import VisitorLog
            from sqlalchemy import func
            
            # Simple count query
            count = VisitorLog.query.count()
            print(f"   ✅ Total visits: {count}")
            
            # Test 4: Referral codes query
            print("4. Testing referral codes query...")
            from datetime import datetime, timedelta
            
            since = datetime.utcnow() - timedelta(days=7)
            
            ref_codes = VisitorLog.query.filter(
                VisitorLog.ref_code.isnot(None),
                VisitorLog.ref_code != '',
                VisitorLog.timestamp >= since
            ).group_by(VisitorLog.ref_code).all()
            
            print(f"   ✅ Found {len(ref_codes)} referral codes")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = simple_test()
    sys.exit(0 if success else 1) 