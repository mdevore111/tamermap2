#!/bin/bash

# Complete Nginx Restart and Verification Script
# This script ensures nginx is properly restarted and configured

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Complete Nginx Restart and Verification${NC}"
echo "============================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Step 1: Stop nginx completely
echo -e "${YELLOW}Step 1: Stopping nginx completely...${NC}"
systemctl stop nginx
sleep 2

# Step 2: Check if nginx is still running
echo -e "${YELLOW}Step 2: Checking if nginx processes are stopped...${NC}"
if pgrep nginx > /dev/null; then
    echo -e "${YELLOW}Nginx processes still running, waiting for them to stop naturally...${NC}"
    # Wait for nginx to stop naturally
    for i in {1..10}; do
        if ! pgrep nginx > /dev/null; then
            echo -e "${GREEN}✓ Nginx processes stopped naturally${NC}"
            break
        fi
        echo "Waiting for nginx to stop... ($i/10)"
        sleep 2
    done
    
    # If still running after 20 seconds, just continue
    if pgrep nginx > /dev/null; then
        echo -e "${YELLOW}Warning: Some nginx processes may still be running, but continuing...${NC}"
    fi
else
    echo -e "${GREEN}✓ Nginx processes stopped${NC}"
fi

# Step 3: Test configuration
echo -e "${YELLOW}Step 3: Testing nginx configuration...${NC}"
if nginx -t; then
    echo -e "${GREEN}✓ Configuration test passed${NC}"
else
    echo -e "${RED}✗ Configuration test failed${NC}"
    echo -e "${YELLOW}Let's check what's wrong...${NC}"
    
    # Show the error in detail
    nginx -t 2>&1 | head -10
    
    echo ""
    echo -e "${YELLOW}Current nginx configuration files:${NC}"
    ls -la /etc/nginx/sites-available/
    echo ""
    
    echo -e "${YELLOW}Main nginx config:${NC}"
    grep -n "include" /etc/nginx/nginx.conf | head -5
    
    exit 1
fi

# Step 4: Start nginx
echo -e "${YELLOW}Step 4: Starting nginx...${NC}"
systemctl start nginx
sleep 3

# Step 5: Check nginx status
echo -e "${YELLOW}Step 5: Checking nginx status...${NC}"
if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✓ Nginx is running${NC}"
else
    echo -e "${RED}✗ Nginx failed to start${NC}"
    systemctl status nginx
    exit 1
fi

# Step 6: Check nginx processes
echo -e "${YELLOW}Step 6: Checking nginx processes...${NC}"
ps aux | grep nginx | grep -v grep
echo ""

# Step 7: Check listening ports
echo -e "${YELLOW}Step 7: Checking listening ports...${NC}"
netstat -tlnp | grep :80 || echo "Port 80 not listening"
echo ""

# Step 8: Test site accessibility
echo -e "${YELLOW}Step 8: Testing site accessibility...${NC}"
if curl -s -I http://localhost > /dev/null; then
    echo -e "${GREEN}✓ Site is accessible on localhost${NC}"
else
    echo -e "${RED}✗ Site not accessible on localhost${NC}"
fi

# Step 9: Check error logs
echo -e "${YELLOW}Step 9: Checking recent error logs...${NC}"
if [[ -f /var/log/nginx/error.log ]]; then
    echo -e "${BLUE}Recent nginx errors:${NC}"
    tail -5 /var/log/nginx/error.log
else
    echo -e "${YELLOW}No nginx error log found${NC}"
fi

# Step 10: Check site-specific logs
echo -e "${YELLOW}Step 10: Checking site-specific logs...${NC}"
if [[ -f /var/log/nginx/tamermap_error.log ]]; then
    echo -e "${BLUE}Recent tamermap errors:${NC}"
    tail -5 /var/log/nginx/tamermap_error.log
else
    echo -e "${YELLOW}No tamermap error log found${NC}"
fi

echo ""
echo -e "${GREEN}Nginx restart and verification completed!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test your site: curl -I http://yourdomain.com"
echo "2. Check nginx status: sudo systemctl status nginx"
echo "3. Monitor logs: sudo tail -f /var/log/nginx/tamermap_error.log" 