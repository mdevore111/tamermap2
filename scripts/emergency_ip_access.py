#!/usr/bin/env python3
"""
Emergency IP Access - Quick Fix for Dynamic IP

This script adds your current IP to the nginx config temporarily
so you can regain access to your server.
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

def add_emergency_ip_access(ip_address):
    """Add IP to nginx config for emergency access"""
    config_path = "/etc/nginx/sites-available/tamermap"
    
    try:
        # Read current config
        with open(config_path, 'r') as f:
            config = f.read()
        
        # Check if IP is already in the config
        if ip_address in config:
            print(f"✅ IP {ip_address} is already in the configuration")
            return True
        
        # Find the geo block and add the IP
        geo_pattern = r'(geo \$cloudflare_ip \{[^}]*?)(\s*default 0;)'
        
        if re.search(geo_pattern, config, re.DOTALL):
            # Add IP before "default 0;" with emergency comment
            new_config = re.sub(
                geo_pattern,
                f'\\1\n    # EMERGENCY ACCESS - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n    allow {ip_address};\n\\2',
                config,
                flags=re.DOTALL
            )
            
            # Write updated config
            with open('/tmp/tamermap_emergency.conf', 'w') as f:
                f.write(new_config)
            
            # Backup and apply
            backup_path = f"/etc/nginx/sites-available/tamermap_backup_emergency_{datetime.now().strftime('%Y%m%d_%H%M%S')}.conf"
            subprocess.run(['sudo', 'cp', config_path, backup_path], check=True)
            subprocess.run(['sudo', 'cp', '/tmp/tamermap_emergency.conf', config_path], check=True)
            
            # Test nginx configuration
            result = subprocess.run(['sudo', 'nginx', '-t'], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Nginx configuration test failed:")
                print(result.stderr)
                # Restore backup
                subprocess.run(['sudo', 'cp', backup_path, config_path], check=True)
                return False
            
            # Reload nginx
            subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'], check=True)
            print(f"✅ Emergency access granted for IP: {ip_address}")
            print(f"💾 Backup saved at: {backup_path}")
            print("\n⚠️  This is temporary access - consider setting up a permanent solution")
            return True
        else:
            print("❌ Could not find geo block in configuration")
            return False
            
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return False

def main():
    print("🚨 Emergency IP Access - Quick Fix")
    print("=" * 40)
    print("This will add your current IP to allow direct access.")
    print("Use this to regain access, then set up a permanent solution.")
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
    
    # Confirm
    response = input(f"\nAdd {current_ip} for emergency access? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Cancelled")
        return
    
    # Add IP to config
    if add_emergency_ip_access(current_ip):
        print("\n✅ Emergency access granted!")
        print("You should now be able to use SCP/SSH.")
        print("\n📋 Next steps:")
        print("1. Test your SCP connection")
        print("2. Run: python3 scripts/cloudflare_dynamic_ip_solution.py")
        print("3. Choose a permanent solution for your dynamic IP")
    else:
        print("\n❌ Failed to grant emergency access")
        print("You may need to access the server directly or use Cloudflare Tunnel")

if __name__ == "__main__":
    main()
