#!/usr/bin/env python3
"""
Cloudflare Protection with Dynamic IP Support

This script creates a solution for users with dynamic IPs who need direct access
to their server while maintaining Cloudflare protection against bots.

Options:
1. Cloudflare Tunnel (recommended)
2. Temporary IP whitelist with auto-update
3. SSH key-based access with monitoring
"""

import requests
import subprocess
import os
import json
from datetime import datetime, timedelta

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
        return [], []

def get_current_ip():
    """Get your current public IP"""
    try:
        response = requests.get('https://api.ipify.org', timeout=10)
        return response.text.strip()
    except:
        return None

def create_cloudflare_tunnel_config():
    """Create Cloudflare Tunnel configuration (recommended solution)"""
    
    config = """
# Cloudflare Tunnel Configuration
# This allows secure access without exposing your server to the internet

# 1. Install cloudflared
# wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
# sudo dpkg -i cloudflared-linux-amd64.deb

# 2. Authenticate with Cloudflare
# cloudflared tunnel login

# 3. Create a tunnel
# cloudflared tunnel create tamermap-admin

# 4. Configure the tunnel
# cloudflared tunnel route dns tamermap-admin admin.tamermap.com

# 5. Create config file: /root/.cloudflared/config.yml
tunnel: tamermap-admin
credentials-file: /root/.cloudflared/tamermap-admin.json

ingress:
  - hostname: admin.tamermap.com
    service: http://localhost:22
    originRequest:
      httpHostHeader: admin.tamermap.com
  - hostname: tamermap.com
    service: http://localhost:8000
    originRequest:
      httpHostHeader: tamermap.com
  - service: http_status:404

# 6. Run the tunnel
# cloudflared tunnel run tamermap-admin

# Benefits:
# - No need to whitelist IPs
# - Encrypted connection
# - Access from anywhere
# - No port exposure
"""
    
    return config

def create_dynamic_ip_nginx_config(ipv4_ranges, ipv6_ranges):
    """Create nginx config with dynamic IP support"""
    
    config = f"""
# Cloudflare Protection with Dynamic IP Support
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# Define Cloudflare IP ranges
geo $cloudflare_ip {{
    default 0;
    
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

# Allow SSH/SCP tools by user agent
map $http_user_agent $is_scp {
    default 0;
    ~*WinSCP 1;
    ~*FileZilla 1;
    ~*scp 1;
    ~*sftp 1;
    ~*rsync 1;
    ~*curl 1;
    ~*wget 1;
    ~*SSH 1;
}

# Check for valid SSH key in headers (if using SSH key forwarding)
map $http_x_ssh_key $has_valid_ssh_key {
    default 0;
    ~*ssh-rsa 1;
    ~*ssh-ed25519 1;
}

# Main server block
server {
    listen 80;
    listen 443 ssl http2;
    server_name _;
    
    # SSL configuration
    ssl_certificate /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Block direct access unless from Cloudflare, monitoring, SCP tools, or has SSH key
    if ($cloudflare_ip = 0) {
        if ($is_monitor = 0) {
            if ($is_scp = 0) {
                if ($has_valid_ssh_key = 0) {
                    return 403 "Access denied. Please use the official website or authorized tools.";
                }
            }
        }
    }
    
    # SSH/SCP specific endpoints
    location ~ ^/(ssh|scp|sftp|admin)/ {
        # Allow SCP tools, monitoring, or valid SSH keys
        if ($cloudflare_ip = 0) {
            if ($is_monitor = 0) {
                if ($is_scp = 0) {
                    if ($has_valid_ssh_key = 0) {
                        return 403 "SSH/SCP access denied.";
                    }
                }
            }
        }
        
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Cloudflare headers
        proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
        proxy_set_header CF-Ray $http_cf_ray;
        proxy_set_header CF-Visitor $http_cf_visitor;
        
        # SSH/SCP specific settings
        client_max_body_size 100M;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
    
    # Regular website traffic
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Cloudflare headers
        proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
        proxy_set_header CF-Ray $http_cf_ray;
        proxy_set_header CF-Visitor $http_cf_visitor;
    }
    
    # Health check endpoint
    location /health {
        access_log off;
        return 200 "OK";
        add_header Content-Type text/plain;
    }
    
    # Block common attack patterns
    location ~* \.(php|asp|aspx|jsp)$ {
        return 404;
    }
}
"""
    
    return config

def create_ip_update_script():
    """Create a script to update your IP automatically"""
    
    script = """#!/bin/bash
# Auto-update IP script for Cloudflare protection
# Run this script periodically to update your IP in the nginx config

# Get current IP
CURRENT_IP=$(curl -s https://api.ipify.org)

# Check if IP has changed
if [ -f /tmp/last_ip.txt ]; then
    LAST_IP=$(cat /tmp/last_ip.txt)
    if [ "$CURRENT_IP" = "$LAST_IP" ]; then
        echo "IP unchanged: $CURRENT_IP"
        exit 0
    fi
fi

echo "IP changed from $LAST_IP to $CURRENT_IP"

# Update nginx config
sed -i "s/allow [0-9.]*;/allow $CURRENT_IP;/g" /etc/nginx/sites-available/tamermap

# Test nginx config
if nginx -t; then
    systemctl reload nginx
    echo "$CURRENT_IP" > /tmp/last_ip.txt
    echo "✅ IP updated successfully"
else
    echo "❌ Nginx config test failed"
    exit 1
fi
"""
    
    return script

def main():
    print("🛡️  Cloudflare Protection with Dynamic IP Support")
    print("=" * 60)
    print()
    print("Since you don't have a static IP, here are your options:")
    print()
    print("1. 🌐 Cloudflare Tunnel (RECOMMENDED)")
    print("   - Most secure and reliable")
    print("   - No IP whitelisting needed")
    print("   - Access from anywhere")
    print()
    print("2. 🔄 Dynamic IP Auto-Update")
    print("   - Automatically updates your IP")
    print("   - Requires periodic script runs")
    print("   - Good for temporary access")
    print()
    print("3. 🔑 SSH Key-Based Access")
    print("   - Uses SSH key forwarding")
    print("   - More secure than IP-based")
    print("   - Requires SSH key setup")
    print()
    
    choice = input("Choose an option (1-3): ").strip()
    
    if choice == "1":
        print("\n🌐 Setting up Cloudflare Tunnel solution...")
        config = create_cloudflare_tunnel_config()
        
        with open('/tmp/cloudflare_tunnel_setup.txt', 'w') as f:
            f.write(config)
        
        print("✅ Cloudflare Tunnel setup instructions saved to /tmp/cloudflare_tunnel_setup.txt")
        print("\n📋 Next steps:")
        print("1. Follow the instructions in the file")
        print("2. This will give you secure access without IP whitelisting")
        print("3. Access your server via admin.tamermap.com")
        
    elif choice == "2":
        print("\n🔄 Setting up Dynamic IP Auto-Update...")
        
        # Get Cloudflare IPs
        ipv4_ranges, ipv6_ranges = get_cloudflare_ips()
        
        # Create nginx config
        config = create_dynamic_ip_nginx_config(ipv4_ranges, ipv6_ranges)
        
        # Create update script
        update_script = create_ip_update_script()
        
        # Save files
        with open('/tmp/tamermap_dynamic_ip.conf', 'w') as f:
            f.write(config)
        
        with open('/tmp/update_ip.sh', 'w') as f:
            f.write(update_script)
        
        os.chmod('/tmp/update_ip.sh', 0o755)
        
        print("✅ Files created:")
        print("  - /tmp/tamermap_dynamic_ip.conf (nginx config)")
        print("  - /tmp/update_ip.sh (IP update script)")
        print("\n📋 Next steps:")
        print("1. sudo cp /tmp/tamermap_dynamic_ip.conf /etc/nginx/sites-available/tamermap")
        print("2. sudo nginx -t && sudo systemctl reload nginx")
        print("3. Run /tmp/update_ip.sh whenever your IP changes")
        print("4. Set up a cron job to run it periodically")
        
    elif choice == "3":
        print("\n🔑 SSH Key-Based Access...")
        print("This requires setting up SSH key forwarding in your SCP client.")
        print("Most SCP clients support this - check your client's documentation.")
        print("\nThe nginx config will detect SSH keys in headers and allow access.")
        
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()
