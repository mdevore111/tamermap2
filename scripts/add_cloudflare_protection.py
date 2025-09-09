#!/usr/bin/env python3
"""
Add Cloudflare Protection to Existing Nginx Setup

This script modifies your existing nginx configuration to add Cloudflare IP filtering
while preserving all your current settings and structure.

Requirements:
- Existing nginx config at /etc/nginx/sites-available/tamermap
- Root/sudo access
- Python requests library
"""

import requests
import subprocess
import shutil
from datetime import datetime
import os

def get_cloudflare_ips():
    """Fetch current Cloudflare IP ranges"""
    print("🌐 Fetching Cloudflare IP ranges...")
    
    try:
        # IPv4 ranges
        response = requests.get('https://www.cloudflare.com/ips-v4', timeout=10)
        ipv4_ranges = response.text.strip().split('\n')
        
        # IPv6 ranges  
        response = requests.get('https://www.cloudflare.com/ips-v6', timeout=10)
        ipv6_ranges = response.text.strip().split('\n')
        
        print(f"✅ Fetched {len(ipv4_ranges)} IPv4 and {len(ipv6_ranges)} IPv6 ranges")
        return ipv4_ranges, ipv6_ranges
        
    except Exception as e:
        print(f"❌ Error fetching Cloudflare IPs: {e}")
        print("Using fallback IP ranges...")
        # Fallback to known ranges
        return [
            '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22',
            '103.31.4.0/22', '141.101.64.0/18', '108.162.192.0/18',
            '190.93.240.0/20', '188.114.96.0/20', '197.234.240.0/22',
            '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
            '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22'
        ], [
            '2400:cb00::/32', '2606:4700::/32', '2803:f800::/32',
            '2405:b500::/32', '2405:8100::/32', '2a06:98c0::/29',
            '2c0f:f248::/32'
        ]

def create_cloudflare_geo_block(ipv4_ranges, ipv6_ranges, your_ssh_ip=None):
    """Create the geo block for Cloudflare IPs"""
    
    geo_block = f"""
# ────────────────────────────────────────────────────────────
# Cloudflare IP Protection
# Added on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ────────────────────────────────────────────────────────────

# Define Cloudflare IP ranges
geo $cloudflare_ip {{
    default 0;
    
    # Your SSH access (if specified)
"""
    
    if your_ssh_ip:
        geo_block += f"    {your_ssh_ip} 1;\n"
    
    geo_block += """
    # Cloudflare IPv4 ranges
"""
    
    for ip_range in ipv4_ranges:
        geo_block += f"    {ip_range} 1;\n"
    
    geo_block += """
    # Cloudflare IPv6 ranges
"""
    
    for ip_range in ipv6_ranges:
        geo_block += f"    {ip_range} 1;\n"
    
    geo_block += """
}

# Allow monitoring traffic by user agent
map $http_user_agent $is_monitor {
    default 0;
    ~*Tamermap-Monitor 1;
}
"""
    
    return geo_block

def add_protection_to_server_block():
    """Add protection rules to the HTTPS server block"""
    
    protection_rules = """
    # ────────────────────────────────────────────────────────────
    # Cloudflare Protection Rules
    # Block direct access unless from Cloudflare or monitoring
    # ────────────────────────────────────────────────────────────
    
    # Block direct access unless from Cloudflare or monitoring
    if ($cloudflare_ip = 0) {
        if ($is_monitor = 0) {
            return 403 "Access denied. Please use the official website.";
        }
    }
    
    # Add Cloudflare headers for proper IP detection
    proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
    proxy_set_header CF-Ray $http_cf_ray;
    proxy_set_header CF-Visitor $http_cf_visitor;
"""
    
    return protection_rules

def modify_nginx_config(ipv4_ranges, ipv6_ranges, your_ssh_ip=None):
    """Modify the existing nginx configuration"""
    
    config_path = "/etc/nginx/sites-available/tamermap"
    
    # Read current config
    try:
        with open(config_path, 'r') as f:
            current_config = f.read()
    except FileNotFoundError:
        print(f"❌ Config file not found: {config_path}")
        return False
    
    # Create backup
    backup_path = f"/etc/nginx/sites-available/tamermap_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(config_path, backup_path)
    print(f"✅ Backup created: {backup_path}")
    
    # Add geo block after the http { line
    geo_block = create_cloudflare_geo_block(ipv4_ranges, ipv6_ranges, your_ssh_ip)
    
    # Find the http { line and add geo block after it
    if "http {" in current_config:
        current_config = current_config.replace(
            "http {",
            f"http {{{geo_block}"
        )
    else:
        print("❌ Could not find 'http {' in config")
        return False
    
    # Add protection rules to the HTTPS server block
    protection_rules = add_protection_to_server_block()
    
    # Find the HTTPS server block and add protection rules
    if "listen 443 ssl;" in current_config:
        # Add protection rules after the SSL configuration
        ssl_end_marker = "ssl_ciphers               HIGH:!aNULL:!MD5;"
        if ssl_end_marker in current_config:
            current_config = current_config.replace(
                ssl_end_marker,
                f"{ssl_end_marker}{protection_rules}"
            )
        else:
            print("❌ Could not find SSL configuration end marker")
            return False
    else:
        print("❌ Could not find HTTPS server block")
        return False
    
    # Write modified config
    with open('/tmp/tamermap_cloudflare_modified.conf', 'w') as f:
        f.write(current_config)
    
    # Copy to nginx directory
    try:
        subprocess.run(['sudo', 'cp', '/tmp/tamermap_cloudflare_modified.conf', config_path], check=True)
        print("✅ Modified configuration written")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error writing config: {e}")
        return False

def test_and_reload_nginx():
    """Test nginx configuration and reload if valid"""
    
    try:
        # Test configuration
        result = subprocess.run(['sudo', 'nginx', '-t'], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"❌ Nginx configuration test failed:")
            print(result.stderr)
            return False
        
        # Reload nginx
        subprocess.run(['sudo', 'systemctl', 'reload', 'nginx'], check=True)
        print("✅ Nginx configuration applied and reloaded")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error testing/reloading nginx: {e}")
        return False

def main():
    print("🛡️  Add Cloudflare Protection to Existing Nginx")
    print("=" * 55)
    print("This will modify your existing nginx configuration to add Cloudflare IP filtering.")
    print("Your current settings and structure will be preserved.")
    
    # Get your SSH IP (optional)
    ssh_ip = input("Enter your SSH IP address (optional, for direct access): ").strip()
    if not ssh_ip:
        print("⚠️  No SSH IP provided - you'll need to access via Cloudflare if locked out")
    
    # Fetch Cloudflare IPs
    ipv4_ranges, ipv6_ranges = get_cloudflare_ips()
    
    # Show what will be added
    print(f"\n📋 What will be added:")
    print(f"  • Geo block with {len(ipv4_ranges)} IPv4 and {len(ipv6_ranges)} IPv6 ranges")
    print(f"  • Monitoring traffic detection (Tamermap-Monitor user agent)")
    print(f"  • Protection rules in HTTPS server block")
    print(f"  • Cloudflare header forwarding")
    
    # Confirm
    response = input("\nModify nginx configuration? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Configuration cancelled")
        return
    
    # Modify configuration
    if modify_nginx_config(ipv4_ranges, ipv6_ranges, ssh_ip):
        if test_and_reload_nginx():
            print("\n✅ Cloudflare protection added successfully!")
            print("\n📊 What this does:")
            print("  • Preserves all your existing nginx settings")
            print("  • Adds Cloudflare IP filtering")
            print("  • Allows monitoring traffic (Tamermap-Monitor)")
            print("  • Blocks all other direct traffic")
            print("  • Forwards Cloudflare headers to your app")
            
            print(f"\n💾 Backup saved - to restore:")
            print(f"   sudo cp /etc/nginx/sites-available/tamermap_backup_* /etc/nginx/sites-available/tamermap")
            print(f"   sudo systemctl reload nginx")
        else:
            print("❌ Failed to reload nginx - check configuration")
    else:
        print("❌ Failed to modify configuration")

if __name__ == "__main__":
    main()
