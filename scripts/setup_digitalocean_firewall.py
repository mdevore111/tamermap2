#!/usr/bin/env python3
"""
DigitalOcean Cloud Firewall Setup for Tamermap
Implements ChatGPT security recommendations by moving IP filtering to network level

This script creates firewall rules that:
1. Allow HTTP/HTTPS only from Cloudflare IP ranges
2. Allow SSH only from your admin IP
3. Block everything else at the network level (before reaching Nginx)

Usage:
    python3 setup_digitalocean_firewall.py --admin-ip YOUR_IP
    python3 setup_digitalocean_firewall.py --admin-ip YOUR_IP --apply (to actually create the firewall)
"""

import requests
import json
import sys
import argparse
from datetime import datetime

def get_cloudflare_ips():
    """Get current Cloudflare IP ranges from their API"""
    try:
        print("🌐 Fetching current Cloudflare IP ranges...")
        
        # Get IPv4 ranges
        ipv4_response = requests.get('https://www.cloudflare.com/ips-v4', timeout=10)
        ipv4_ranges = ipv4_response.text.strip().split('\n')
        
        # Get IPv6 ranges
        ipv6_response = requests.get('https://www.cloudflare.com/ips-v6', timeout=10)
        ipv6_ranges = ipv6_response.text.strip().split('\n')
        
        print(f"✅ Found {len(ipv4_ranges)} IPv4 ranges and {len(ipv6_ranges)} IPv6 ranges")
        return ipv4_ranges, ipv6_ranges
        
    except Exception as e:
        print(f"❌ Error fetching Cloudflare IPs: {e}")
        return None, None

def get_current_ip():
    """Get current public IP address"""
    try:
        response = requests.get('https://ipv4.icanhazip.com', timeout=10)
        return response.text.strip()
    except:
        return None

def create_firewall_rules(ipv4_ranges, ipv6_ranges, admin_ip):
    """Create DigitalOcean firewall rules configuration"""
    
    # Inbound rules
    inbound_rules = []
    
    # SSH access - only from admin IP
    if admin_ip:
        inbound_rules.append({
            "type": "tcp",
            "ports": "22",
            "sources": {
                "addresses": [f"{admin_ip}/32"]
            }
        })
    
    # HTTP (port 80) - only from Cloudflare
    cf_addresses = ipv4_ranges + ipv6_ranges
    inbound_rules.append({
        "type": "tcp", 
        "ports": "80",
        "sources": {
            "addresses": cf_addresses
        }
    })
    
    # HTTPS (port 443) - only from Cloudflare
    inbound_rules.append({
        "type": "tcp",
        "ports": "443", 
        "sources": {
            "addresses": cf_addresses
        }
    })
    
    # Outbound rules (allow all outbound traffic)
    outbound_rules = [
        {
            "type": "tcp",
            "ports": "1-65535",
            "destinations": {
                "addresses": ["0.0.0.0/0", "::/0"]
            }
        },
        {
            "type": "udp",
            "ports": "1-65535", 
            "destinations": {
                "addresses": ["0.0.0.0/0", "::/0"]
            }
        },
        {
            "type": "icmp",
            "destinations": {
                "addresses": ["0.0.0.0/0", "::/0"]
            }
        }
    ]
    
    return {
        "name": f"tamermap-cloudflare-protection-{datetime.now().strftime('%Y%m%d')}",
        "inbound_rules": inbound_rules,
        "outbound_rules": outbound_rules,
        "droplet_ids": [],  # Will be populated when applying
        "tags": ["tamermap", "cloudflare-protection"]
    }

def print_firewall_summary(firewall_config, admin_ip):
    """Print a human-readable summary of the firewall configuration"""
    print(f"\n{'='*60}")
    print("🛡️  DIGITALOCEAN FIREWALL CONFIGURATION")
    print(f"{'='*60}")
    print(f"📝 Name: {firewall_config['name']}")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    print(f"\n🔒 INBOUND RULES (what can reach your server):")
    for rule in firewall_config['inbound_rules']:
        port = rule['ports']
        protocol = rule['type'].upper()
        sources = rule['sources']['addresses']
        
        if port == "22":
            print(f"  ✅ SSH ({protocol}/{port}): Admin IP only ({admin_ip})")
        elif port == "80":
            print(f"  ✅ HTTP ({protocol}/{port}): {len(sources)} Cloudflare IP ranges")
        elif port == "443":
            print(f"  ✅ HTTPS ({protocol}/{port}): {len(sources)} Cloudflare IP ranges")
    
    print(f"\n🌐 OUTBOUND RULES (what your server can reach):")
    print(f"  ✅ All traffic allowed (TCP/UDP/ICMP to anywhere)")
    
    print(f"\n❌ BLOCKED BY DEFAULT:")
    print(f"  • Direct HTTP/HTTPS access (bypassing Cloudflare)")
    print(f"  • SSH from unauthorized IPs")
    print(f"  • All other inbound traffic")

def generate_doctl_commands(firewall_config, admin_ip):
    """Generate doctl commands to create the firewall"""
    
    # Escape quotes for shell
    name = firewall_config['name']
    
    commands = [
        "# DigitalOcean Firewall Setup Commands",
        "# Run these commands if you have doctl installed and configured",
        "",
        "# 1. Create the firewall",
        f'doctl compute firewall create \\',
        f'  --name "{name}" \\',
        f'  --tag-names "tamermap,cloudflare-protection"',
        "",
        "# 2. Add SSH rule (admin access only)",
        f'doctl compute firewall add-rules {name} \\',
        f'  --inbound-rules "protocol:tcp,ports:22,address:{admin_ip}/32"',
        "",
        "# 3. Add HTTP rule (Cloudflare only - this will be a long command with all IPs)",
        f'# doctl compute firewall add-rules {name} \\',
        f'#   --inbound-rules "protocol:tcp,ports:80,address:CLOUDFLARE_IPS"',
        "",
        "# 4. Add HTTPS rule (Cloudflare only)",
        f'# doctl compute firewall add-rules {name} \\',
        f'#   --inbound-rules "protocol:tcp,ports:443,address:CLOUDFLARE_IPS"',
        "",
        "# 5. Apply to your droplet",
        f'# doctl compute firewall apply-droplets {name} --droplet-ids YOUR_DROPLET_ID',
    ]
    
    return "\n".join(commands)

def save_firewall_config(firewall_config, admin_ip):
    """Save firewall configuration to files"""
    
    # Save JSON config
    config_file = f"infrastructure/do_firewall_config_{datetime.now().strftime('%Y%m%d')}.json"
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(firewall_config, f, indent=2)
    
    # Save doctl commands
    commands_file = f"infrastructure/do_firewall_commands_{datetime.now().strftime('%Y%m%d')}.sh"
    with open(commands_file, 'w', encoding='utf-8') as f:
        f.write(generate_doctl_commands(firewall_config, admin_ip))
    
    # Save human-readable summary
    summary_file = f"infrastructure/do_firewall_summary_{datetime.now().strftime('%Y%m%d')}.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        # Capture print output
        import io
        from contextlib import redirect_stdout
        
        output = io.StringIO()
        with redirect_stdout(output):
            print_firewall_summary(firewall_config, admin_ip)
        
        f.write(output.getvalue())
    
    return config_file, commands_file, summary_file

def create_manual_setup_guide(admin_ip):
    """Create a step-by-step manual setup guide for DigitalOcean control panel"""
    
    guide = f"""
# DigitalOcean Cloud Firewall Manual Setup Guide
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Step 1: Access DigitalOcean Control Panel
1. Login to your DigitalOcean account
2. Navigate to "Networking" → "Firewalls"
3. Click "Create Firewall"

## Step 2: Basic Configuration
- **Name**: tamermap-cloudflare-protection-{datetime.now().strftime('%Y%m%d')}
- **Description**: Cloudflare-only HTTP/HTTPS access with admin SSH

## Step 3: Inbound Rules
Add these rules in order:

### Rule 1: SSH Access (Admin Only)
- **Type**: SSH
- **Protocol**: TCP
- **Port Range**: 22
- **Sources**: Custom → {admin_ip}/32
- **Description**: Admin SSH access only

### Rule 2: HTTP Access (Cloudflare Only)
- **Type**: HTTP
- **Protocol**: TCP  
- **Port Range**: 80
- **Sources**: Custom → [Paste all Cloudflare IPv4 ranges - see CF_IPS_V4.txt]

### Rule 3: HTTPS Access (Cloudflare Only)
- **Type**: HTTPS
- **Protocol**: TCP
- **Port Range**: 443
- **Sources**: Custom → [Paste all Cloudflare IPv4 + IPv6 ranges - see CF_IPS_ALL.txt]

## Step 4: Outbound Rules
Keep the default "All TCP", "All UDP", "All ICMP" outbound rules.

## Step 5: Apply to Droplet
1. In the "Apply to Droplets" section
2. Select your tamermap server droplet
3. Click "Create Firewall"

## Step 6: Test
1. Verify SSH still works: ssh tamermap@mail.tamermap.com
2. Verify website works: https://tamermap.com
3. Verify direct IP is blocked: curl -k https://YOUR_SERVER_IP (should timeout/fail)

## Important Notes:
- ⚠️  Test SSH access immediately after applying
- ⚠️  Keep this terminal open until you confirm SSH works
- ⚠️  If locked out, use DigitalOcean's console access to remove firewall
- 📱 Have DigitalOcean mobile app ready for emergency access

## Rollback Plan:
If something goes wrong:
1. DigitalOcean Control Panel → Firewalls
2. Find your firewall → Settings → Delete
3. Or use console access to run: doctl compute firewall delete FIREWALL_ID
"""
    
    return guide

def main():
    parser = argparse.ArgumentParser(description='Setup DigitalOcean Cloud Firewall for Tamermap')
    parser.add_argument('--admin-ip', help='Your admin IP address for SSH access')
    parser.add_argument('--auto-detect-ip', action='store_true', help='Auto-detect your current IP')
    parser.add_argument('--apply', action='store_true', help='Actually create the firewall (requires doctl)')
    
    args = parser.parse_args()
    
    print("🛡️  DigitalOcean Cloud Firewall Setup for Tamermap")
    print("=" * 60)
    
    # Get admin IP
    admin_ip = args.admin_ip
    if args.auto_detect_ip:
        detected_ip = get_current_ip()
        if detected_ip:
            admin_ip = detected_ip
            print(f"🔍 Auto-detected your IP: {admin_ip}")
        else:
            print("❌ Could not auto-detect IP")
    
    if not admin_ip:
        print("❌ Admin IP required. Use --admin-ip YOUR_IP or --auto-detect-ip")
        sys.exit(1)
    
    # Get Cloudflare IPs
    ipv4_ranges, ipv6_ranges = get_cloudflare_ips()
    if not ipv4_ranges:
        print("❌ Could not fetch Cloudflare IPs")
        sys.exit(1)
    
    # Create firewall configuration
    firewall_config = create_firewall_rules(ipv4_ranges, ipv6_ranges, admin_ip)
    
    # Save configuration files
    config_file, commands_file, summary_file = save_firewall_config(firewall_config, admin_ip)
    
    # Save Cloudflare IPs for manual setup
    with open('infrastructure/CF_IPS_V4.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(ipv4_ranges))
    
    with open('infrastructure/CF_IPS_V6.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(ipv6_ranges))
    
    with open('infrastructure/CF_IPS_ALL.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(ipv4_ranges + ipv6_ranges))
    
    # Save manual setup guide
    guide = create_manual_setup_guide(admin_ip)
    with open('infrastructure/DO_FIREWALL_MANUAL_SETUP.md', 'w', encoding='utf-8') as f:
        f.write(guide)
    
    # Display summary
    print_firewall_summary(firewall_config, admin_ip)
    
    print(f"\n📁 FILES CREATED:")
    print(f"  📄 {config_file} - Full firewall configuration (JSON)")
    print(f"  🖥️  {commands_file} - doctl commands")
    print(f"  📋 {summary_file} - Human-readable summary")
    print(f"  📝 infrastructure/DO_FIREWALL_MANUAL_SETUP.md - Step-by-step guide")
    print(f"  📊 infrastructure/CF_IPS_*.txt - Cloudflare IP lists")
    
    if args.apply:
        print(f"\n🚀 --apply flag detected, but doctl implementation not included.")
        print(f"Use the generated commands in {commands_file} or follow the manual guide.")
    else:
        print(f"\n💡 NEXT STEPS:")
        print(f"  1. Review the manual setup guide: infrastructure/DO_FIREWALL_MANUAL_SETUP.md")
        print(f"  2. Follow the steps in DigitalOcean control panel")
        print(f"  3. Or use doctl with the commands in: {commands_file}")
        print(f"  4. Test thoroughly before proceeding to step 2!")

if __name__ == "__main__":
    main()
