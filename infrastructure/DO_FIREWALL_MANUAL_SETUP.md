
# DigitalOcean Cloud Firewall Manual Setup Guide
Generated: 2025-09-19 07:18:48

## Step 1: Access DigitalOcean Control Panel
1. Login to your DigitalOcean account
2. Navigate to "Networking" → "Firewalls"
3. Click "Create Firewall"

## Step 2: Basic Configuration
- **Name**: tamermap-cloudflare-protection-20250919
- **Description**: Cloudflare-only HTTP/HTTPS access with admin SSH

## Step 3: Inbound Rules
Add these rules in order:

### Rule 1: SSH Access (Admin Only)
- **Type**: SSH
- **Protocol**: TCP
- **Port Range**: 22
- **Sources**: Custom → 50.106.16.6/32
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
