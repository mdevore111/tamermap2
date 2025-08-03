#!/usr/bin/env python3
"""
Test script for the enhanced Tamermap monitor with frontend Stripe integration testing.
"""

import os
import sys
import time

# Add the app directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Set test mode
os.environ['MONITOR_TEST_MODE'] = 'true'

from monitor import TamermapMonitor, setup_logging

def test_frontend_stripe_integration():
    """Test the frontend Stripe integration monitoring"""
    print("Testing enhanced monitor with frontend Stripe integration...")
    
    # Setup logging
    logger = setup_logging()
    
    # Create monitor instance
    monitor = TamermapMonitor()
    
    # Run a single check cycle
    print("Running monitoring checks...")
    results = monitor.run_all_checks()
    
    # Display results
    print(f"\nResults ({len(results)} checks):")
    print("=" * 60)
    
    for result in results:
        status = "✅ PASS" if result.success else "❌ FAIL"
        print(f"{status} {result.name}: {result.message}")
        
        if not result.success and result.details:
            print(f"    Details: {result.details}")
    
    # Summary
    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed
    
    print(f"\nSummary: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\nFailed checks:")
        for result in results:
            if not result.success:
                print(f"  - {result.name}: {result.message}")
    
    return failed == 0

if __name__ == "__main__":
    success = test_frontend_stripe_integration()
    sys.exit(0 if success else 1) 