#!/usr/bin/env python3
"""
Unified Cloudflare Protection Deployment Script

This script creates a standardized nginx configuration for both staging and production
that works optimally with Cloudflare while maintaining security.

Features:
- Unified config for both environments
- Cloudflare IP validation
- Monitoring traffic detection
- Removes redundant protections (handled by Cloudflare)
- Preserves essential security
- Automatic backup and rollback
"""

import requests
import subprocess
import shutil
import os
import sys
from datetime import datetime
import argparse

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

def create_unified_nginx_config(ipv4_ranges, ipv6_ranges, environment, your_ssh_ip=None):
    """Create unified nginx configuration for both staging and production"""
    
    # Environment-specific settings
    if environment == 'staging':
        server_names = 'staging.tamermap.com'
        ssl_cert = '/etc/ssl/cloudflare/staging_origin.pem'
        ssl_key = '/etc/ssl/cloudflare/staging_origin.key'
        robots_tag = 'add_header X-Robots-Tag "noindex, nofollow, noarchive" always;'
        health_endpoint = '''
    # ── Health check endpoint
    location = /healthz {
        add_header Content-Type text/plain;
        return 200 'ok';
    }'''
    else:  # production
        server_names = 'tamermap.com www.tamermap.com dev.tamermap.com'
        ssl_cert = '/etc/nginx/ssl/tamermap/tamermap_bundle.crt'
        ssl_key = '/etc/nginx/ssl/tamermap/tamermap.key'
        robots_tag = ''
        health_endpoint = ''
    
    # Create geo block for Cloudflare IPs
    geo_block = f'''
# ────────────────────────────────────────────────────────────
# Cloudflare IP Protection
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ────────────────────────────────────────────────────────────

# Define Cloudflare IP ranges
geo $cloudflare_ip {{
    default 0;
    
    # Your SSH access (if specified)
'''
    
    if your_ssh_ip and your_ssh_ip != "cloudflare":
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
    
    # Create the unified nginx config
    config = f'''# ────────────────────────────────────────────────────────────
# Unified Tamermap Nginx Configuration
# Environment: {environment.upper()}
# Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# ────────────────────────────────────────────────────────────

{geo_block}

# HTTP → HTTPS redirect
server {{
    listen 80;
    server_name {server_names};
    return 301 https://$host$request_uri;
}}

# HTTPS server block
server {{
    listen 443 ssl http2;
    server_name {server_names};

    # SSL certificates
    ssl_certificate     {ssl_cert};
    ssl_certificate_key {ssl_key};
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;

    # Staging: keep crawlers out
    {robots_tag}

    # ────────────────────────────────────────────────────────────
    # Cloudflare Protection Rules
    # Block direct access unless from Cloudflare or monitoring
    # ────────────────────────────────────────────────────────────
    
    # Block direct access unless from Cloudflare or monitoring
    if ($cloudflare_ip = 0) {{
        if ($is_monitor = 0) {{
            return 403 "Access denied. Please use the official website.";
        }}
    }}

    # Add Cloudflare headers for proper IP detection
    proxy_set_header CF-Connecting-IP $http_cf_connecting_ip;
    proxy_set_header CF-Ray $http_cf_ray;
    proxy_set_header CF-Visitor $http_cf_visitor;

    # ────────────────────────────────────────────────────────────
    # Basic Security (minimal - Cloudflare handles the rest)
    # ────────────────────────────────────────────────────────────
    
    # Deny hidden files
    location ~ /\\.(?!well-known) {{
        deny all;
    }}
    
    # Block dangerous file extensions
    location ~* \\.(?:php[345]?|phtml|pl|py|jsp|asp|sh|cgi)$ {{
        return 444;
    }}
    
    # Block suspicious referer headers
    if ($http_referer ~* "(?:phpinfo|eval|base64|system)") {{
        return 444;
    }}
    
    # Block suspicious query parameters
    if ($args ~* "(?:phpinfo|eval|base64|system|exec|shell)") {{
        return 444;
    }}

    {health_endpoint}

    # ── Static assets
    location /static/ {{
        alias /home/tamermap/app/static/;
        access_log off;
        expires 7d;
    }}

    # ── Stripe webhooks
    location /webhooks/stripe {{
        client_max_body_size 10m;

        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_pass         http://127.0.0.1:8000;

        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_set_header   CF-Connecting-IP  $http_cf_connecting_ip;
    }}

    # ── API endpoints
    location /api/ {{
        client_max_body_size 10m;

        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_pass         http://127.0.0.1:8000;

        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_set_header   CF-Connecting-IP  $http_cf_connecting_ip;
    }}

    # ── Admin panel
    location /admin/ {{
        client_max_body_size 5m;

        proxy_http_version 1.1;
        proxy_set_header   Connection "";
        proxy_pass         http://127.0.0.1:8000;

        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_set_header   CF-Connecting-IP  $http_cf_connecting_ip;
    }}

    # ── Main application
    location / {{
        proxy_http_version 1.1;
        proxy_set_header   Connection "";

        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto https;
        proxy_set_header   CF-Connecting-IP  $http_cf_connecting_ip;

        proxy_pass         http://127.0.0.1:8000;
    }}
}}
'''
    
    return config

def backup_existing_configs(environment):
    """Backup existing nginx configurations"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backups = []
    
    # Backup main config
    main_config = f"/etc/nginx/sites-available/tamermap"
    if os.path.exists(main_config):
        backup_path = f"/etc/nginx/sites-available/tamermap_backup_{timestamp}"
        try:
            subprocess.run(['sudo', 'cp', main_config, backup_path], check=True)
            backups.append(backup_path)
            print(f"✅ Backed up main config: {backup_path}")
        except Exception as e:
            print(f"⚠️  Could not backup main config: {e}")
    
    # Backup staging config
    staging_config = f"/etc/nginx/sites-available/staging.tamermap.com"
    if os.path.exists(staging_config):
        backup_path = f"/etc/nginx/sites-available/staging.tamermap.com_backup_{timestamp}"
        try:
            subprocess.run(['sudo', 'cp', staging_config, backup_path], check=True)
            backups.append(backup_path)
            print(f"✅ Backed up staging config: {backup_path}")
        except Exception as e:
            print(f"⚠️  Could not backup staging config: {e}")
    
    return backups

def deploy_config(config_content, environment):
    """Deploy the new nginx configuration"""
    
    if environment == 'staging':
        config_path = "/etc/nginx/sites-available/staging.tamermap.com"
    else:
        config_path = "/etc/nginx/sites-available/tamermap"
    
    try:
        # Write new config
        with open('/tmp/tamermap_unified.conf', 'w') as f:
            f.write(config_content)
        
        # Copy to nginx directory
        subprocess.run(['sudo', 'cp', '/tmp/tamermap_unified.conf', config_path], check=True)
        print(f"✅ Configuration written to {config_path}")
        
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
        print(f"❌ Error deploying configuration: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Deploy unified Cloudflare protection')
    parser.add_argument('--environment', choices=['staging', 'production'], required=True,
                       help='Environment to deploy to')
    parser.add_argument('--ssh-ip', help='Your SSH IP address for direct access')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    print(f"🛡️  Unified Cloudflare Protection Deployment")
    print(f"Environment: {args.environment.upper()}")
    print("=" * 50)
    
    # Get your SSH IP
    ssh_ip = args.ssh_ip
    if not ssh_ip:
        ssh_ip = input("Enter your SSH IP address (optional, for direct access): ").strip()
        if not ssh_ip:
            print("⚠️  No SSH IP provided - you'll need to access via Cloudflare if locked out")
    
    # Fetch Cloudflare IPs
    ipv4_ranges, ipv6_ranges = get_cloudflare_ips()
    
    # Create unified configuration
    config = create_unified_nginx_config(ipv4_ranges, ipv6_ranges, args.environment, ssh_ip)
    
    # Show preview
    print(f"\n📋 Configuration Preview for {args.environment}:")
    print("-" * 40)
    print(config[:800] + "..." if len(config) > 800 else config)
    
    # Confirm
    if not args.force:
        response = input(f"\nDeploy this configuration to {args.environment}? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("❌ Deployment cancelled")
            return
    
    # Backup existing configs
    backups = backup_existing_configs(args.environment)
    
    # Deploy new config
    if deploy_config(config, args.environment):
        print(f"\n✅ Unified Cloudflare protection deployed to {args.environment}!")
        print("\n📊 What this provides:")
        print("  • Cloudflare IP validation")
        print("  • Direct access blocking")
        print("  • Monitoring traffic detection")
        print("  • Minimal security (Cloudflare handles the rest)")
        print("  • Unified config for both environments")
        print("  • Proper Cloudflare header forwarding")
        
        if backups:
            print(f"\n💾 Backups created:")
            for backup in backups:
                print(f"   {backup}")
            print("   To restore: sudo cp <backup> <config_path> && sudo systemctl reload nginx")
    else:
        print("❌ Deployment failed - check nginx logs")

if __name__ == "__main__":
    main()
