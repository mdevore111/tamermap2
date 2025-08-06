#!/usr/bin/env python3
"""
Test script to compare visit trends with referral code trends
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.admin_utils import get_visit_trends_30d, get_referral_code_trends_30d

def test_trends():
    app = create_app()
    with app.app_context():
        print("=== Comparing Trends ===\n")
        
        # Test visit trends
        visit_result = get_visit_trends_30d(days=30)
        print("Visit Trends:")
        print(f"  Total visits: {sum(day['total'] for day in visit_result)}")
        print(f"  Max daily visits: {max(day['total'] for day in visit_result)}")
        print(f"  Min daily visits: {min(day['total'] for day in visit_result)}")
        
        # Test referral code trends
        ref_result = get_referral_code_trends_30d(days=30)
        print("\nReferral Code Trends:")
        for code in ref_result['codes']:
            total = sum(day.get(code, 0) for day in ref_result['data'])
            max_daily = max(day.get(code, 0) for day in ref_result['data'])
            print(f"  {code}: {total} total, {max_daily} max daily")
        
        print(f"\nScale comparison:")
        print(f"  Visit trends scale: 0 to {max(day['total'] for day in visit_result)}")
        print(f"  Referral code scale: 0 to {max(max(day.get(code, 0) for day in ref_result['data']) for code in ref_result['codes'])}")

if __name__ == "__main__":
    test_trends() 