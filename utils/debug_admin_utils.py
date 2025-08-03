#!/usr/bin/env python3
"""
Debug script to test admin_utils functions directly.
"""

import sys
import os
import traceback

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_admin_utils():
    """Test admin_utils functions directly."""
    try:
        from app import create_app, db
        from app.admin_utils import get_referral_codes_with_journeys
        
        app = create_app()
        
        with app.app_context():
            print("🧪 Testing Admin Utils Functions...")
            print("=" * 50)
            
            # Test the function that's causing the 500 error
            print("Testing get_referral_codes_with_journeys...")
            data = get_referral_codes_with_journeys(days=7, limit=5)
            print(f"✅ Function returned: {len(data)} items")
            
            if data:
                print("Sample data:")
                for item in data[:2]:
                    print(f"  - {item.get('ref_code', 'N/A')}: {item.get('total_visits', 0)} visits")
            else:
                print("No data returned (this is normal if no referral codes exist)")
            
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Full traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_admin_utils()
    sys.exit(0 if success else 1) 