"""
Test script for rate limiting functionality.
Tests the rate limiting on various API endpoints.
"""

import os
import sys
import argparse
import requests
import time
from datetime import datetime

def check_environment(base_url, headers):
    """
    Check the environment configuration of the target server.
    
    Args:
        base_url: The base URL of the application
        headers: Request headers including test key
    
    Returns:
        dict: Environment information or None if check fails
    """
    try:
        response = requests.get(f"{base_url}/dev/environment-check", headers=headers)
        if response.ok:
            return response.json()
        print(f"Environment check failed: {response.status_code}")
        return None
    except Exception as e:
        print(f"Error checking environment: {e}")
        return None

def test_rate_limit(base_url="http://localhost:5000"):
    """
    Test the rate limiting functionality by making multiple rapid requests.
    
    Args:
        base_url: The base URL of the application (default: http://localhost:5000)
    """
    # Get test API key from environment or use default for local testing
    test_key = os.environ.get('TEST_API_KEY', 'test_key_local')
    headers = {'X-Test-Key': test_key}
    
    # Check environment first
    print("\nChecking environment configuration...")
    env_info = check_environment(base_url, headers)
    if env_info:
        print(f"Environment Info:")
        print(f"  FLASK_ENV: {env_info.get('FLASK_ENV', 'unknown')}")
        print(f"  Host: {env_info.get('HOST', 'unknown')}")
        print(f"  Is Staging: {env_info.get('IS_STAGING', False)}")
        print("-" * 50)
    
    endpoint = f"{base_url}/dev/test-limit"
    
    print("\nTesting rate limiting...")
    print(f"Endpoint: {endpoint}")
    print("Making 5 rapid requests (limit is 3 per minute)...")
    print("-" * 50)
    
    for i in range(5):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\nRequest {i+1} at {timestamp}:")
        
        try:
            response = requests.get(endpoint, headers=headers)
            print(f"Status Code: {response.status_code}")
            
            # Get rate limit headers if they exist
            remaining = response.headers.get('X-RateLimit-Remaining', 'N/A')
            reset = response.headers.get('X-RateLimit-Reset', 'N/A')
            
            print(f"Rate Limit Remaining: {remaining}")
            print(f"Rate Limit Reset: {reset}")
            if response.ok:
                print(f"Response: {response.text}")
            else:
                print(f"Error: {response.text}")
            
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
        
        time.sleep(0.1)  # Small delay between requests

def main():
    parser = argparse.ArgumentParser(description='Test rate limiting functionality')
    parser.add_argument('--env', choices=['local', 'staging'], default='local',
                      help='Environment to test (local or staging)')
    parser.add_argument('--url', help='Custom base URL to test')
    
    args = parser.parse_args()
    
    if args.url:
        base_url = args.url
    else:
        base_url = {
            'local': 'http://localhost:5000',
            'staging': 'https://dev.tamermap.com'
        }[args.env]
    
    # Ensure we're in development mode for local testing
    if args.env == 'local':
        os.environ.setdefault('FLASK_ENV', 'development')
    
    test_rate_limit(base_url)

if __name__ == "__main__":
    main() 