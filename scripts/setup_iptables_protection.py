#!/usr/bin/env python3
"""
IPTables Cloudflare Protection Setup

Alternative approach using iptables to block direct access.
This is simpler but less flexible than nginx approach.

Requirements:
- iptables
- Root/sudo access
"""

import requests
import subprocess
import json

def get_cloudflare_ips():
    """Fetch Cloudflare IP ranges"""
    try:
        response = requests.get('https://www.cloudflare.com/ips-v4', timeout=10)
        return response.text.strip().split('\n')
    except:
        # Fallback ranges
        return [
            '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22',
            '103.31.4.0/22', '141.101.64.0/18', '108.162.192.0/18',
            '190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22',
            '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
            '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22'
        ]

def setup_iptables_rules(your_ip=None):
    """Set up iptables rules to block direct access"""
    
    print("🛡️  Setting up iptables Cloudflare protection...")
    
    # Get Cloudflare IPs
    cf_ips = get_cloudflare_ips()
    
    # Create iptables script
    script = """#!/bin/bash
# Cloudflare Protection iptables rules
# Generated automatically

# Flush existing rules (be careful!)
iptables -F
iptables -X
iptables -t nat -F
iptables -t nat -X

# Default policies
iptables -P INPUT DROP
iptables -P FORWARD DROP  
iptables -P OUTPUT ACCEPT

# Allow loopback
iptables -A INPUT -i lo -j ACCEPT

# Allow established connections
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allow SSH (port 22) - IMPORTANT!
iptables -A INPUT -p tcp --dport 22 -j ACCEPT
"""
    
    # Add your IP if provided
    if your_ip:
        script += f"# Allow your IP for SSH access\n"
        script += f"iptables -A INPUT -s {your_ip} -j ACCEPT\n\n"
    
    # Allow Cloudflare IPs
    script += "# Allow Cloudflare IPs\n"
    for ip in cf_ips:
        script += f"iptables -A INPUT -s {ip} -j ACCEPT\n"
    
    script += """
# Allow HTTP/HTTPS from Cloudflare only
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Log blocked attempts
iptables -A INPUT -j LOG --log-prefix "BLOCKED: " --log-level 4

# Save rules
iptables-save > /etc/iptables/rules.v4
"""
    
    # Write and execute script
    with open('/tmp/cloudflare_protection.sh', 'w') as f:
        f.write(script)
    
    try:
        subprocess.run(['chmod', '+x', '/tmp/cloudflare_protection.sh'], check=True)
        subprocess.run(['sudo', '/tmp/cloudflare_protection.sh'], check=True)
        print("✅ iptables rules applied successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error applying iptables rules: {e}")
        return False

def main():
    print("🛡️  IPTables Cloudflare Protection")
    print("=" * 40)
    print("⚠️  WARNING: This will block direct access to your server!")
    print("   Make sure you have SSH access and Cloudflare is configured.")
    
    your_ip = input("Enter your IP address (for SSH access): ").strip()
    if not your_ip:
        print("❌ IP address required for SSH access")
        return
    
    response = input("Continue with iptables setup? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Setup cancelled")
        return
    
    if setup_iptables_rules(your_ip):
        print("\n✅ Protection enabled!")
        print("📊 What this does:")
        print("  • Blocks all direct HTTP/HTTPS access")
        print("  • Allows only Cloudflare IPs")
        print("  • Allows SSH access from your IP")
        print("  • Forces all web traffic through Cloudflare")
        
        print("\n🔧 To disable protection:")
        print("  sudo iptables -F && sudo iptables -P INPUT ACCEPT")
    else:
        print("❌ Setup failed")

if __name__ == "__main__":
    main()
