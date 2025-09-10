#!/usr/bin/env python3
"""
Fix SCP Access with Cloudflare Protection

This script adds SCP/SSH access exceptions to your existing Cloudflare protection
configuration to ensure SCP connections work properly.
"""

import requests
import subprocess
import os
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
        return [], []

def get_current_ip():
    """Get your current public IP"""
    try:
        response = requests.get('https://api.ipify.org', timeout=10)
        return response.text.strip()
    except:
        return None

def create_scp_friendly_config(ipv4_ranges, ipv6_ranges, your_ip=None):
    """Create nginx configuration that allows SCP access"""
    
    # Allow your IP if provided
    ssh_allow = f"allow {your_ip};" if your_ip else ""
    
    config = f"""
# Cloudflare Protection Configuration with SCP Access
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

# Define Cloudflare IP ranges
geo $cloudflare_ip {{
    default 0;
    
    # Your SSH/SCP access
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

# Allow SCP/SSH tools by user agent
map $http_user_agent $is_scp {
    default 0;
    ~*WinSCP 1;
    ~*FileZilla 1;
    ~*scp 1;
    ~*sftp 1;
    ~*rsync 1;
    ~*curl 1;
    ~*wget 1;
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
    
    # Block direct access unless from Cloudflare, monitoring, or SCP tools
    if ($cloudflare_ip = 0) {
        if ($is_monitor = 0) {
            if ($is_scp = 0) {
                return 403 "Access denied. Please use the official website.";
            }
        }
    }
    
    # SCP/File transfer endpoints - allow direct access
    location ~ ^/(files|uploads|downloads|admin/files)/ {
        # Allow SCP tools and your IP
        if ($cloudflare_ip = 0) {
            if ($is_scp = 0) {
                return 403 "Access denied for file operations.";
            }
        }
        
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Cloudflare headers
        proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
        proxy_set_header CF-Ray $http_cf_ray;
        proxy_set_header CF-Visitor $http_cf_visitor;
        
        # File upload settings
        client_max_body_size 100M;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
    
    # Your existing location blocks
    location / {
        proxy_pass http://127.0.0.1:5000;
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
    
    # Block suspicious user agents (but allow SCP tools)
    if ($http_user_agent ~* (bot|crawler|spider|scraper)) {
        if ($is_monitor = 0) {
            if ($is_scp = 0) {
                return 403;
            }
        }
    }
}
"""
    
    return config

def backup_existing_config():
    """Backup existing nginx configuration"""
    backup_path = f"/etc/nginx/sites-available/tamermap_backup_scp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.conf"
    
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
        with open('/tmp/tamermap_scp_fixed.conf', 'w') as f:
            f.write(config_content)
        
        # Copy to nginx directory
        subprocess.run(['sudo', 'cp', '/tmp/tamermap_scp_fixed.conf', config_path], check=True)
        
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
    print("🔧 Fix SCP Access with Cloudflare Protection")
    print("=" * 50)
    
    # Get your current IP
    current_ip = get_current_ip()
    if current_ip:
        print(f"📍 Your current IP: {current_ip}")
    else:
        print("⚠️  Could not detect your IP automatically")
    
    # Get your SSH IP (optional)
    ssh_ip = input(f"Enter your SSH IP address (current detected: {current_ip}): ").strip()
    if not ssh_ip and current_ip:
        ssh_ip = current_ip
        print(f"Using detected IP: {ssh_ip}")
    elif not ssh_ip:
        print("⚠️  No SSH IP provided - SCP access may be limited")
    
    # Fetch Cloudflare IPs
    ipv4_ranges, ipv6_ranges = get_cloudflare_ips()
    
    # Create configuration
    config = create_scp_friendly_config(ipv4_ranges, ipv6_ranges, ssh_ip)
    
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
        print("\n✅ SCP access fixed!")
        print("\n📊 What this does:")
        print("  • Allows your IP for direct access")
        print("  • Allows SCP tools (WinSCP, FileZilla, etc.)")
        print("  • Allows file transfer endpoints")
        print("  • Maintains Cloudflare protection for other traffic")
        print("  • Improves file upload/download performance")
        
        if backup_path:
            print(f"\n💾 Backup saved at: {backup_path}")
            print("   To restore: sudo cp {backup_path} /etc/nginx/sites-available/tamermap && sudo systemctl reload nginx")
    else:
        print("❌ Configuration failed - check nginx logs")

if __name__ == "__main__":
    main()
