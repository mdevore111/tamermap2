#!/usr/bin/env python3
"""
Test script to see what the referral code trends function returns
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.admin_utils import get_referral_code_trends_30d
import json

def test_referral_trends():
    app = create_app()
    with app.app_context():
        print("=== Testing Referral Code Trends ===\n")
        
        # Test with 30 days
        result = get_referral_code_trends_30d(days=30)
        
        print(f"Dates: {len(result['dates'])}")
        print(f"Codes: {result['codes']}")
        print(f"Data entries: {len(result['data'])}")
        
        print("\n=== Sample Data ===")
        for i, day_data in enumerate(result['data'][:5]):  # Show first 5 days
            print(f"Day {i+1}: {day_data['date']}")
            for code in result['codes']:
                count = day_data.get(code, 0)
                avg = day_data.get(f'{code}_avg', 0)
                if count > 0 or avg > 0:
                    print(f"  {code}: {count} visits, {avg} avg")
        
        print("\n=== Summary ===")
        total_visits = {}
        for day_data in result['data']:
            for code in result['codes']:
                if code not in total_visits:
                    total_visits[code] = 0
                total_visits[code] += day_data.get(code, 0)
        
        for code, total in total_visits.items():
            print(f"{code}: {total} total visits in 30 days")

if __name__ == "__main__":
    test_referral_trends() 