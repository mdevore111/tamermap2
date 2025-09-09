#!/usr/bin/env python3
"""
Cloudflare Protection Setup Script

This script configures your server to:
1. Allow SSH (port 22) for WinSCP access
2. Allow monitoring traffic (Tamermap-Monitor user agent)
3. Block all other direct traffic - forces everything through Cloudflare
4. Minimal latency impact (Cloudflare actually improves performance)

Requirements:
- Nginx web server
- Cloudflare IP ranges (automatically fetched)
- Root/sudo access to modify nginx config
"""

import requests
import json
import os
import subprocess
from datetime import datetime

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
        # Fallback to known ranges (update these periodically)
        return [
            '173.245.48.0/20',
            '103.21.244.0/22', 
            '103.22.200.0/22',
            '103.31.4.0/22',
            '141.101.64.0/18',
            '108.162.192.0/18',
            '190.93.240.0/20',
            '188.114.96.0/20',
            '197.234.240.0/22',
            '198.41.128.0/17',
            '162.158.0.0/15',
            '104.16.0.0/13',
            '104.24.0.0/14',
            '172.64.0.0/13',
            '131.0.72.0/22'
        ], [
            '2400:cb00::/32',
            '2606:4700::/32',
            '2803:f800::/32',
            '2405:b500::/32',
            '2405:8100::/32',
            '2a06:98c0::/29',
            '2c0f:f248::/32'
        ]

def create_nginx_config(ipv4_ranges, ipv6_ranges, your_ssh_ip=None):
    """Create nginx configuration with Cloudflare protection"""
    
    # Allow your SSH IP if provided
    ssh_allow = f"allow {your_ssh_ip};" if your_ssh_ip else ""
    
    config = f"""
# Cloudflare Protection Configuration
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# Define Cloudflare IP ranges
geo $cloudflare_ip {{
    default 0;
    
    # Your SSH access (if specified)
    {ssh_allow}
    
    # Cloudflare IPv4 ranges
"""
    
    for ip_range in ipv4_ranges:
        config += f"    {ip_range} 1;\n"
    
    config += """
    # Cloudflare IPv6 ranges
"""
    
    for ip_range in ipv6_ranges:
        config += f"    {ip_range} 1;\n"
    
    config += """
}

# Allow monitoring traffic by user agent
map $http_user_agent $is_monitor {
    default 0;
    ~*Tamermap-Monitor 1;
}

# Main server block
server {
    listen 80;
    listen 443 ssl http2;
    server_name _;
    
    # SSL configuration (adjust paths as needed)
    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Block direct access unless from Cloudflare or monitoring
    if ($cloudflare_ip = 0) {
        if ($is_monitor = 0) {
            return 403 "Access denied. Please use the official website.";
        }
    }
    
    # Your existing location blocks
    location / {
        proxy_pass http://127.0.0.1:5000;  # Adjust port as needed
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Cloudflare headers
        proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
        proxy_set_header CF-Ray $http_cf_ray;
        proxy_set_header CF-Visitor $http_cf_visitor;
    }
    
    # Health check endpoint (allow monitoring)
    location /health {
        access_log off;
        return 200 "OK";
        add_header Content-Type text/plain;
    }
    
    # Block common attack patterns
    location ~* \.(php|asp|aspx|jsp)$ {
        return 404;
    }
    
    # Block suspicious user agents
    if ($http_user_agent ~* (bot|crawler|spider|scraper)) {
        if ($is_monitor = 0) {
            return 403;
        }
    }
}
"""
    
    return config

def backup_existing_config():
    """Backup existing nginx configuration"""
    backup_path = f"/etc/nginx/sites-available/tamermap_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.conf"
    
    try:
        subprocess.run(['sudo', 'cp', '/etc/nginx/sites-available/tamermap', backup_path], check=True)
        print(f"✅ Backup created: {backup_path}")
        return backup_path
    except subprocess.CalledProcessError:
        print("⚠️  Could not backup existing config (file may not exist)")
        return None

def apply_config(config_content):
    """Apply the new nginx configuration"""
    config_path = "/etc/nginx/sites-available/tamermap"
    
    try:
        # Write new config
        with open('/tmp/tamermap_cloudflare.conf', 'w') as f:
            f.write(config_content)
        
        # Copy to nginx directory
        subprocess.run(['sudo', 'cp', '/tmp/tamermap_cloudflare.conf', config_path], check=True)
        
        # Test nginx configuration
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
        print(f"❌ Error applying configuration: {e}")
        return False

def main():
    print("🛡️  Cloudflare Protection Setup")
    print("=" * 50)
    
    # Get your SSH IP (optional)
    ssh_ip = input("Enter your SSH IP address (optional, for direct access): ").strip()
    if not ssh_ip:
        print("⚠️  No SSH IP provided - you'll need to access via Cloudflare Tunnel if locked out")
    
    # Fetch Cloudflare IPs
    ipv4_ranges, ipv6_ranges = get_cloudflare_ips()
    
    # Create configuration
    config = create_nginx_config(ipv4_ranges, ipv6_ranges, ssh_ip)
    
    # Show preview
    print("\n📋 Configuration Preview:")
    print("-" * 30)
    print(config[:500] + "..." if len(config) > 500 else config)
    
    # Confirm
    response = input("\nApply this configuration? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        print("❌ Configuration cancelled")
        return
    
    # Backup existing config
    backup_path = backup_existing_config()
    
    # Apply new config
    if apply_config(config):
        print("\n✅ Cloudflare protection enabled!")
        print("\n📊 What this does:")
        print("  • Allows SSH access (port 22)")
        print("  • Allows monitoring traffic (Tamermap-Monitor user agent)")
        print("  • Blocks all other direct traffic")
        print("  • Forces legitimate traffic through Cloudflare")
        print("  • Improves performance and security")
        
        if backup_path:
            print(f"\n💾 Backup saved at: {backup_path}")
            print("   To restore: sudo cp {backup_path} /etc/nginx/sites-available/tamermap && sudo systemctl reload nginx")
    else:
        print("❌ Configuration failed - check nginx logs")

if __name__ == "__main__":
    main()
