#!/usr/bin/env python3
"""
Test the referral journeys API endpoint directly.
"""

import sys
import os
import requests
import json

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_api_endpoint():
    """Test the referral journeys API endpoint."""
    try:
        print("🧪 Testing Referral Journeys API Endpoint...")
        print("=" * 50)
        
        # Test the API endpoint directly
        url = "http://localhost:5000/admin/api/analytics/referral-journeys"
        
        print(f"Testing URL: {url}")
        
        # Make the request
        response = requests.get(url, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"✅ API Response: {json.dumps(data, indent=2)}")
            except json.JSONDecodeError:
                print(f"⚠️  Response is not JSON: {response.text[:200]}...")
        else:
            print(f"❌ Error Response: {response.text}")
            
        return response.status_code == 200
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Is your Flask app running on localhost:5000?")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_api_endpoint()
    sys.exit(0 if success else 1) 