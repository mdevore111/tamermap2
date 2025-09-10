#!/usr/bin/env python3
"""
Cloudflare Dynamic DNS Update Script

This script updates a Cloudflare DNS record with your current IP address.
Run this on your workstation to keep workstation.tamermap.com updated.
"""

import requests
import json
import os
from datetime import datetime

# Configuration - Update these values
ZONE_ID = "909f91b90c0bc9bdd472bfaaf16609f0"  # tamermap.com zone ID
RECORD_ID = "your_record_id_here"  # Get after creating workstation.tamermap.com A record
API_TOKEN = "V7oVqj_N_VOjhM166Zlx8f0AkM1zfacEj57KewzD"  # Cloudflare API token
SUBDOMAIN = "workstation.tamermap.com"

def get_current_ip():
    """Get your current public IP"""
    try:
        response = requests.get('https://api.ipify.org', timeout=10)
        return response.text.strip()
    except Exception as e:
        print(f"❌ Error getting current IP: {e}")
        return None

def get_current_dns_ip():
    """Get the current IP from DNS record"""
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{RECORD_ID}"
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data['result']['content']
        else:
            print(f"❌ Error getting DNS record: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error getting DNS record: {e}")
        return None

def update_dns_record(new_ip):
    """Update the DNS record with new IP"""
    try:
        url = f"https://api.cloudflare.com/client/v4/zones/{ZONE_ID}/dns_records/{RECORD_ID}"
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json"
        }
        
        data = {
            "type": "A",
            "name": SUBDOMAIN,
            "content": new_ip,
            "ttl": 300  # 5 minutes TTL
        }
        
        response = requests.put(url, headers=headers, json=data)
        if response.status_code == 200:
            return True
        else:
            print(f"❌ Error updating DNS record: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error updating DNS record: {e}")
        return False

def main():
    print(f"🌐 Cloudflare Dynamic DNS Update - {SUBDOMAIN}")
    print("=" * 50)
    
    # Check configuration
    if ZONE_ID == "your_zone_id_here" or RECORD_ID == "your_record_id_here" or API_TOKEN == "your_api_token_here":
        print("❌ Please update the configuration variables in this script:")
        print("   - ZONE_ID")
        print("   - RECORD_ID") 
        print("   - API_TOKEN")
        return
    
    # Get current IP
    current_ip = get_current_ip()
    if not current_ip:
        return
    
    print(f"📍 Current IP: {current_ip}")
    
    # Get current DNS IP
    dns_ip = get_current_dns_ip()
    if not dns_ip:
        return
    
    print(f"🌐 DNS IP: {dns_ip}")
    
    # Check if update is needed
    if current_ip == dns_ip:
        print("✅ IP is up to date - no changes needed")
        return
    
    # Update DNS record
    print(f"🔄 Updating {SUBDOMAIN} from {dns_ip} to {current_ip}...")
    
    if update_dns_record(current_ip):
        print(f"✅ Successfully updated {SUBDOMAIN} to {current_ip}")
        print(f"⏰ Updated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("❌ Failed to update DNS record")

if __name__ == "__main__":
    main()
