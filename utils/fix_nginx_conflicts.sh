#!/bin/bash

# Fix Nginx Configuration Conflicts
# This script identifies and fixes duplicate location blocks and other conflicts

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SITE_NAME="tamermap"
NGINX_SITES_AVAILABLE="/etc/nginx/sites-available"
NGINX_SITES_ENABLED="/etc/nginx/sites-enabled"

echo -e "${GREEN}Fix Nginx Configuration Conflicts${NC}"
echo "====================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Check if site config exists
if [[ ! -f "$NGINX_SITES_AVAILABLE/$SITE_NAME" ]]; then
    echo -e "${RED}Error: Site configuration not found at $NGINX_SITES_AVAILABLE/$SITE_NAME${NC}"
    exit 1
fi

# Backup current configuration
echo -e "${YELLOW}Backing up current configuration...${NC}"
BACKUP_FILE="$NGINX_SITES_AVAILABLE/${SITE_NAME}.backup.$(date +%Y%m%d_%H%M%S)"
cp "$NGINX_SITES_AVAILABLE/$SITE_NAME" "$BACKUP_FILE"
echo -e "${GREEN}✓ Backup created: $BACKUP_FILE${NC}"

# Analyze current configuration
echo -e "${BLUE}Analyzing current configuration for conflicts...${NC}"

# Check for duplicate location blocks
echo -e "${YELLOW}Checking for duplicate location blocks...${NC}"
DUPLICATE_LOCATIONS=$(grep -n "location" "$NGINX_SITES_AVAILABLE/$SITE_NAME" | awk '{print $2}' | sort | uniq -d)

if [[ -n "$DUPLICATE_LOCATIONS" ]]; then
    echo -e "${RED}Found duplicate location blocks:${NC}"
    echo "$DUPLICATE_LOCATIONS"
    echo ""
    
    # Show the duplicate locations with line numbers
    echo -e "${YELLOW}Duplicate location blocks with line numbers:${NC}"
    grep -n "location" "$NGINX_SITES_AVAILABLE/$SITE_NAME" | grep -E "(api|admin|static|/)" | head -20
    echo ""
    
    read -p "Do you want to see the full configuration to identify conflicts? (y/N): " show_config
    if [[ "$show_config" =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Current configuration:${NC}"
        cat -n "$NGINX_SITES_AVAILABLE/$SITE_NAME"
        echo ""
    fi
else
    echo -e "${GREEN}✓ No duplicate location blocks found${NC}"
fi

# Check for other potential conflicts
echo -e "${YELLOW}Checking for other potential conflicts...${NC}"

# Check for multiple server blocks
SERVER_BLOCKS=$(grep -c "server {" "$NGINX_SITES_AVAILABLE/$SITE_NAME" 2>/dev/null || echo "0")
if [[ "$SERVER_BLOCKS" -gt 1 ]]; then
    echo -e "${RED}Found $SERVER_BLOCKS server blocks (should be 1)${NC}"
fi

# Check for multiple upstream blocks
UPSTREAM_BLOCKS=$(grep -c "upstream" "$NGINX_SITES_AVAILABLE/$SITE_NAME" 2>/dev/null || echo "0")
if [[ "$UPSTREAM_BLOCKS" -gt 1 ]]; then
    echo -e "${RED}Found $UPSTREAM_BLOCKS upstream blocks (should be 1)${NC}"
fi

# Check for include directives that might cause conflicts
INCLUDE_COUNT=$(grep -c "include" "$NGINX_SITES_AVAILABLE/$SITE_NAME" 2>/dev/null || echo "0")
echo -e "${BLUE}Found $INCLUDE_COUNT include directives${NC}"

# Show current configuration structure
echo -e "${YELLOW}Current configuration structure:${NC}"
grep -E "^(server|upstream|location|include)" "$NGINX_SITES_AVAILABLE/$SITE_NAME" | head -20

echo ""
echo -e "${BLUE}Options to fix conflicts:${NC}"
echo "1. Use migration script to create clean configuration"
echo "2. Manually edit the configuration"
echo "3. Restore from backup and try different approach"

read -p "Choose option (1-3): " choice

case $choice in
    1)
        echo -e "${YELLOW}Running migration script to create clean configuration...${NC}"
        if [[ -f "utils/migrate_existing_site.sh" ]]; then
            ./utils/migrate_existing_site.sh
        else
            echo -e "${RED}Migration script not found${NC}"
            exit 1
        fi
        ;;
    2)
        echo -e "${YELLOW}Opening configuration for manual editing...${NC}"
        echo "Please remove duplicate location blocks and save the file."
        nano "$NGINX_SITES_AVAILABLE/$SITE_NAME"
        
        echo -e "${YELLOW}Testing configuration after manual edit...${NC}"
        if nginx -t; then
            echo -e "${GREEN}✓ Configuration test passed${NC}"
            echo -e "${YELLOW}Reloading nginx...${NC}"
            systemctl reload nginx
            echo -e "${GREEN}✓ Nginx reloaded successfully${NC}"
        else
            echo -e "${RED}✗ Configuration test failed${NC}"
            echo -e "${YELLOW}Restoring backup...${NC}"
            cp "$BACKUP_FILE" "$NGINX_SITES_AVAILABLE/$SITE_NAME"
            echo -e "${GREEN}✓ Backup restored${NC}"
        fi
        ;;
    3)
        echo -e "${YELLOW}Restoring from backup...${NC}"
        cp "$BACKUP_FILE" "$NGINX_SITES_AVAILABLE/$SITE_NAME"
        echo -e "${GREEN}✓ Backup restored${NC}"
        echo -e "${YELLOW}You can now try a different approach${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Conflict resolution completed!${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test your site: curl -I http://yourdomain.com"
echo "2. Check nginx status: sudo systemctl status nginx"
echo "3. Monitor logs: sudo tail -f /var/log/nginx/tamermap_error.log" 