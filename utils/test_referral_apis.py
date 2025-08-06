#!/usr/bin/env python3
"""
Test script to check if the referral API endpoints are working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.admin_utils import get_referral_funnel_data, get_referral_time_analysis, get_referral_device_data

def test_api_functions():
    app = create_app()
    with app.app_context():
        print("=== Testing API Functions ===\n")
        
        ref_code = 'clingkiosk'
        
        # Test funnel data
        try:
            funnel_data = get_referral_funnel_data(ref_code, days=30)
            print(f"✅ Funnel API: {len(funnel_data)} entries")
            print(f"   Sample: {funnel_data[:2]}")
        except Exception as e:
            print(f"❌ Funnel API Error: {e}")
        
        # Test time analysis
        try:
            time_data = get_referral_time_analysis(ref_code, days=30)
            print(f"✅ Time API: {len(time_data['hourly'])} hourly, {len(time_data['daily'])} daily")
            print(f"   Sample hourly: {time_data['hourly'][:2]}")
        except Exception as e:
            print(f"❌ Time API Error: {e}")
        
        # Test device data
        try:
            device_data = get_referral_device_data(ref_code, days=30)
            print(f"✅ Device API: {len(device_data)} entries")
            print(f"   Sample: {device_data}")
        except Exception as e:
            print(f"❌ Device API Error: {e}")

if __name__ == "__main__":
    test_api_functions() 