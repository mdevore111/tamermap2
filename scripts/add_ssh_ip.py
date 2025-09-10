#!/usr/bin/env python3
"""
Quick Fix: Add SSH IP to Cloudflare Protection

This script adds your current IP to the existing Cloudflare protection
configuration to restore SCP/SSH access.
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

def add_ip_to_config(ip_address):
    """Add IP to existing nginx configuration"""
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
            # Add IP before "default 0;"
            new_config = re.sub(
                geo_pattern,
                f'\\1\n    # Your SSH access - added {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n    allow {ip_address};\n\\2',
                config,
                flags=re.DOTALL
            )
            
            # Write updated config
            with open('/tmp/tamermap_updated.conf', 'w') as f:
                f.write(new_config)
            
            # Backup and apply
            backup_path = f"/etc/nginx/sites-available/tamermap_backup_ip_{datetime.now().strftime('%Y%m%d_%H%M%S')}.conf"
            subprocess.run(['sudo', 'cp', config_path, backup_path], check=True)
            subprocess.run(['sudo', 'cp', '/tmp/tamermap_updated.conf', config_path], check=True)
            
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
            print(f"✅ IP {ip_address} added to configuration")
            print(f"💾 Backup saved at: {backup_path}")
            return True
        else:
            print("❌ Could not find geo block in configuration")
            return False
            
    except Exception as e:
        print(f"❌ Error updating configuration: {e}")
        return False

def main():
    print("🔧 Quick Fix: Add SSH IP to Cloudflare Protection")
    print("=" * 50)
    
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
    
    # Add IP to config
    if add_ip_to_config(current_ip):
        print("\n✅ SCP/SSH access should now work!")
        print("Try your SCP connection again.")
    else:
        print("\n❌ Failed to update configuration")
        print("You may need to manually edit the nginx config or use the full fix script.")

if __name__ == "__main__":
    main()
