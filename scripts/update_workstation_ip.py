#!/usr/bin/env python3
"""
Update Workstation IP from Cloudflare DNS

This script runs on the server and checks workstation.tamermap.com
to get your current IP and updates nginx accordingly.
"""

import requests
import socket
import subprocess
import re
from datetime import datetime


def get_workstation_ip():
    """Get your workstation IP from DNS"""
    try:
        # Resolve the subdomain to get current IP
        ip = socket.gethostbyname('workstation.tamermap.com')
        return ip
    except Exception as e:
        print(f"❌ Error resolving workstation.tamermap.com: {e}")
        return None

def update_nginx_config(ip_address):
    """Update nginx config with new IP"""
    config_path = "/etc/nginx/sites-available/tamermap"
    
    try:
        # Read current config
        with open(config_path, 'r') as f:
            config = f.read()
        
        # Remove any existing emergency access entries
        config = re.sub(r'\n\s*# EMERGENCY ACCESS - .*\n\s*[0-9.]+\s+1;\n', '', config)
        
        # Find the workstation_domain geo block and add the IP
        geo_pattern = r'(geo \$workstation_domain \{[^}]*?)(\s*default 0;)'
        
        # Debug: Show what we're looking for
        print(f"🔍 Looking for pattern: {geo_pattern}")
        print(f"🔍 Config contains 'workstation_domain': {'workstation_domain' in config}")
        print(f"🔍 Config contains '$workstation_domain': {'$workstation_domain' in config}")
        
        if re.search(geo_pattern, config, re.DOTALL):
            # Add IP before "default 0;" with timestamp
            new_config = re.sub(
                geo_pattern,
                f'\\1\n    # WORKSTATION DOMAIN IP - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n    {ip_address} 1;\n\\2',
                config,
                flags=re.DOTALL
            )
            
            # Write updated config
            with open('/tmp/tamermap_workstation.conf', 'w') as f:
                f.write(new_config)
            
            # Backup and apply
            backup_path = f"/etc/nginx/sites-available/tamermap_backup_workstation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.conf"
            subprocess.run(['sudo', 'cp', config_path, backup_path], check=True)
            subprocess.run(['sudo', 'cp', '/tmp/tamermap_workstation.conf', config_path], check=True)
            
            # Test nginx config
            result = subprocess.run(['sudo', 'nginx', '-t'], capture_output=True, text=True)
            if result.returncode != 0:
                print(f"❌ Nginx configuration test failed:")
                print(result.stderr)
                # Restore backup
                subprocess.run(['sudo', 'cp', backup_path, config_path], check=True)
                return False
            
            # Reload nginx
            subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'], check=True)
            print(f"✅ Updated nginx with workstation IP: {ip_address}")
            return True
        else:
            print("❌ Could not find your_ip geo block in nginx config")
            return False
            
    except Exception as e:
        print(f"❌ Error updating nginx config: {e}")
        return False

def main():
    print("🔄 Checking workstation IP from DNS...")
    
    # Get workstation IP from DNS
    workstation_ip = get_workstation_ip()
    if not workstation_ip:
        return
    
    print(f"📍 Workstation IP: {workstation_ip}")
    
    # Update nginx config
    if update_nginx_config(workstation_ip):
        print("✅ Nginx updated successfully")
    else:
        print("❌ Failed to update nginx")

if __name__ == "__main__":
    main()
