#!/usr/bin/env python3
"""
Emergency IP Access - Remote Version

This script runs on your workstation and connects to the server
to add your IP to the nginx configuration.
"""

import requests
import subprocess
import re
from datetime import datetime

def get_current_ip():
    """Get your current public IP"""
    try:
        response = requests.get('https://api.ipify.org', timeout=10)
        return response.text.strip()
    except:
        return None

def add_emergency_ip_access_remote(ip_address, server_host, username):
    """Add IP to nginx config on remote server"""
    
    try:
        # Create the sed command to add the IP
        sed_command = f"""sed -i '/default 0;/i\\    # EMERGENCY ACCESS - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\\n    allow {ip_address};' /etc/nginx/sites-available/tamermap"""
        
        # Test nginx config
        test_command = "nginx -t"
        
        # Reload nginx
        reload_command = "systemctl reload nginx"
        
        # Execute commands on remote server
        print(f"🔧 Connecting to {username}@{server_host}...")
        
        # Add IP to config
        result = subprocess.run([
            'ssh', f'{username}@{server_host}', sed_command
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Error adding IP to config: {result.stderr}")
            return False
        
        # Test nginx config
        test_result = subprocess.run([
            'ssh', f'{username}@{server_host}', test_command
        ], capture_output=True, text=True)
        
        if test_result.returncode != 0:
            print(f"❌ Nginx configuration test failed:")
            print(test_result.stderr)
            return False
        
        # Reload nginx
        reload_result = subprocess.run([
            'ssh', f'{username}@{server_host}', reload_command
        ], capture_output=True, text=True)
        
        if reload_result.returncode != 0:
            print(f"❌ Error reloading nginx: {reload_result.stderr}")
            return False
        
        print(f"✅ Emergency access granted for IP: {ip_address}")
        return True
        
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return False

def main():
    print("🚨 Emergency IP Access - Remote Version")
    print("=" * 45)
    print("This will add your current IP to the server's nginx config.")
    print()
    
    # Get your current IP
    current_ip = get_current_ip()
    if current_ip:
        print(f"📍 Your current IP: {current_ip}")
    else:
        print("⚠️  Could not detect your IP automatically")
        current_ip = input("Enter your IP address: ").strip()
    
    if not current_ip:
        print("❌ No IP address provided")
        return
    
    # Get server details
    server_host = input("Enter server hostname/IP (e.g., staging-server): ").strip()
    if not server_host:
        print("❌ No server hostname provided")
        return
    
    username = input(f"Enter username for {server_host} (default: tamermap): ").strip()
    if not username:
        username = "tamermap"
    
    # Confirm
    response = input(f"\nAdd {current_ip} to {username}@{server_host}? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Cancelled")
        return
    
    # Add IP to config
    if add_emergency_ip_access_remote(current_ip, server_host, username):
        print("\n✅ Emergency access granted!")
        print("You should now be able to use SCP/SSH.")
        print("\n📋 Next steps:")
        print("1. Test your SCP connection")
        print("2. Set up a permanent solution for your dynamic IP")
    else:
        print("\n❌ Failed to grant emergency access")
        print("You may need to access the server directly")

if __name__ == "__main__":
    main()
