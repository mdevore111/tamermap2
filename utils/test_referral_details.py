#!/usr/bin/env python3
"""
Test script to check referral detail functions with actual referral codes
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.admin_utils import get_referral_time_analysis, get_referral_geographic_data, get_referral_device_data, get_referral_funnel_data

def test_referral_details():
    app = create_app()
    with app.app_context():
        print("=== Testing Referral Detail Functions ===\n")
        
        # Test with the actual referral codes from your data
        ref_codes = ['clingkiosk', 'kioskcard']
        
        for ref_code in ref_codes:
            print(f"=== Testing {ref_code} ===\n")
            
            # Test time analysis
            try:
                time_data = get_referral_time_analysis(ref_code, days=30)
                print(f"Time Analysis:")
                print(f"  Hourly data: {len(time_data['hourly'])} entries")
                print(f"  Daily data: {len(time_data['daily'])} entries")
                if time_data['hourly']:
                    print(f"  Sample hourly: {time_data['hourly'][:3]}")
                if time_data['daily']:
                    print(f"  Sample daily: {time_data['daily'][:3]}")
            except Exception as e:
                print(f"  Time Analysis Error: {e}")
            
            # Test geographic data
            try:
                geo_data = get_referral_geographic_data(ref_code, days=30)
                print(f"Geographic Data: {len(geo_data)} entries")
                if geo_data:
                    print(f"  Sample: {geo_data[:3]}")
            except Exception as e:
                print(f"  Geographic Data Error: {e}")
            
            # Test device data
            try:
                device_data = get_referral_device_data(ref_code, days=30)
                print(f"Device Data: {len(device_data)} entries")
                if device_data:
                    print(f"  Sample: {device_data}")
            except Exception as e:
                print(f"  Device Data Error: {e}")
            
            # Test funnel data
            try:
                funnel_data = get_referral_funnel_data(ref_code, days=30)
                print(f"Funnel Data: {len(funnel_data)} entries")
                if funnel_data:
                    print(f"  Sample: {funnel_data}")
            except Exception as e:
                print(f"  Funnel Data Error: {e}")
            
            print()

if __name__ == "__main__":
    test_referral_details() 