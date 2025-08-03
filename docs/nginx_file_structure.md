# Nginx File Structure Guide

> **📢 IMPORTANT:** For the complete and current nginx configuration structure, see **[nginx_security_overview.md](nginx_security_overview.md)** - the authoritative guide to all configuration files and their purposes.

This document provides a quick reference to the nginx file organization after the security implementation.

## Current File Structure (Production)

### Core Infrastructure Files

```
infrastructure/
├── nginx.conf              # Main nginx configuration
├── security_http.conf      # HTTP-level security snippet
├── security_server.conf    # Per-vhost security snippet
├── tamermap                # Tamermap site configuration
└── tamermap.service        # Systemd service file
```

### Deployed Configuration Locations

```
/etc/nginx/
├── nginx.conf                           # Main config (includes rate limiting zones)
├── snippets/
│   ├── security_http.conf              # HTTP security headers
│   └── security_server.conf            # Per-site security guards
├── sites-available/
│   └── tamermap                        # Site-specific configuration
└── sites-enabled/
    └── tamermap -> ../sites-available/tamermap

/etc/systemd/system/
└── tamermap.service                    # Application service
```

## File Dependencies & Includes

```
Main Flow:
nginx.conf
├── includes rate limiting zones (API, Admin, General)
├── loads sites-enabled/*
└── 
    sites-enabled/tamermap
    ├── includes security_server.conf (per-vhost guards)
    ├── references security_http.conf (HTTP headers)
    ├── proxy_pass to application service
    └── CSP and security header injection
```

## Key Configuration Elements

### Rate Limiting Zones (nginx.conf)
- `zone=api:10m rate=10r/s` - API endpoints
- `zone=admin:10m rate=5r/s` - Admin endpoints  
- `zone=general:30m rate=30r/s` - General requests

### Security Implementation
- **HTTP Level**: Global security headers and CSP
- **Server Level**: Per-vhost attack prevention and guards
- **Site Level**: Rate limiting usage and SSL configuration

## Migration from Legacy Structure

The previous file structure used:
- `nginx_rate_limiting.conf` → now in main `nginx.conf`
- `nginx_security_shared.conf` → now split into `security_http.conf` and `security_server.conf`
- `nginx_site_template.conf` → now replaced by actual `tamermap` site config

## Quick Administration Commands

```bash
# Test configuration
sudo nginx -t

# Reload configuration
sudo systemctl reload nginx

# Check site status
sudo systemctl status tamermap.service

# View logs
sudo tail -f /var/log/nginx/tamermap_error.log
```

## Version Control

All configuration files are stored in the `infrastructure/` directory for:
- Version control integration
- Easy deployment across environments
- Configuration backup and restore
- Infrastructure as code practices

## Documentation References

For comprehensive information:
- **[nginx_security_overview.md](nginx_security_overview.md)** - Complete file overview and purposes
- **[nginx_security_migration.md](nginx_security_migration.md)** - Production deployment process
- **[nginx_deployment.md](nginx_deployment.md)** - Quick deployment reference
- **[multi_site_management.md](multi_site_management.md)** - Multi-site management 