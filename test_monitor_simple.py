#!/usr/bin/env python3
"""
Test script for the new simple frontend Stripe test
Run this to verify the monitor is working correctly
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from monitor import check_frontend_stripe_simple

def test_frontend_stripe_simple():
    """Test the simple frontend Stripe test function"""
    print("🧪 Testing Simple Frontend Stripe Test")
    print("=" * 50)
    
    try:
        results = check_frontend_stripe_simple()
        
        print(f"\n📊 Test Results ({len(results)} checks):")
        print("-" * 30)
        
        for result in results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            print(f"{status} {result.name}: {result.message}")
            
            if result.details:
                print(f"    Details: {result.details}")
        
        # Summary
        passed = sum(1 for r in results if r.success)
        total = len(results)
        
        print(f"\n📈 Summary: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Monitor should work correctly.")
        else:
            print("⚠️  Some tests failed. Check the details above.")
            
    except Exception as e:
        print(f"❌ Test script error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_frontend_stripe_simple()
