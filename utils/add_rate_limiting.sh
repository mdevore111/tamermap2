#!/bin/bash

# Add Rate Limiting Zones to Main Nginx Configuration
# This script adds the rate limiting zones to the main nginx config to avoid conflicts

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MAIN_NGINX_CONFIG="/etc/nginx/nginx.conf"
RATE_LIMITING_FILE="nginx_rate_limiting.conf"

echo -e "${GREEN}Add Rate Limiting Zones to Nginx${NC}"
echo "====================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Check if rate limiting file exists
if [[ ! -f "$RATE_LIMITING_FILE" ]]; then
    echo -e "${RED}Error: $RATE_LIMITING_FILE not found in current directory${NC}"
    echo "Please run this script from the project root directory"
    exit 1
fi

# Get absolute path
PROJECT_ROOT=$(pwd)
RATE_LIMITING_PATH="$PROJECT_ROOT/$RATE_LIMITING_FILE"

# Check if rate limiting zones are already defined
echo -e "${BLUE}Checking current nginx configuration...${NC}"
RATE_LIMITING_INCLUDED=$(grep -c "limit_req_zone" "$MAIN_NGINX_CONFIG" 2>/dev/null || echo "0")

if [[ "$RATE_LIMITING_INCLUDED" -gt 0 ]]; then
    echo -e "${YELLOW}Rate limiting zones already found in nginx configuration${NC}"
    echo "This might be causing the conflict. Let's check what's defined:"
    echo ""
    grep -n "limit_req_zone" "$MAIN_NGINX_CONFIG"
    echo ""
    read -p "Do you want to remove existing rate limiting zones and add the new ones? (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Removing existing rate limiting zones...${NC}"
        # Remove existing limit_req_zone lines
        sed -i '/limit_req_zone/d' "$MAIN_NGINX_CONFIG"
        echo -e "${GREEN}✓ Existing rate limiting zones removed${NC}"
    else
        echo -e "${YELLOW}Operation cancelled${NC}"
        exit 0
    fi
fi

# Backup main nginx config
echo -e "${YELLOW}Backing up main nginx configuration...${NC}"
BACKUP_FILE="${MAIN_NGINX_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$MAIN_NGINX_CONFIG" "$BACKUP_FILE"
echo -e "${GREEN}✓ Backup created: $BACKUP_FILE${NC}"

# Add include directive to http block
echo -e "${YELLOW}Adding rate limiting zones to main nginx configuration...${NC}"
sed -i '/http {/a\    include '"$RATE_LIMITING_PATH"';' "$MAIN_NGINX_CONFIG"

echo -e "${GREEN}✓ Rate limiting zones added to main nginx config${NC}"

# Test configuration
echo -e "${YELLOW}Testing nginx configuration...${NC}"
if nginx -t; then
    echo -e "${GREEN}✓ Configuration test passed${NC}"
else
    echo -e "${RED}✗ Configuration test failed${NC}"
    echo -e "${YELLOW}Restoring backup...${NC}"
    cp "$BACKUP_FILE" "$MAIN_NGINX_CONFIG"
    echo -e "${GREEN}✓ Backup restored${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Rate limiting zones added successfully!${NC}"
echo ""
echo -e "${YELLOW}You can now run the migration script:${NC}"
echo "sudo ./utils/migrate_existing_site.sh"
echo ""
echo -e "${YELLOW}Or reload nginx to apply changes:${NC}"
echo "sudo systemctl reload nginx" 