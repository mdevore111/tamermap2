# Multi-Site Flask Management Guide

This guide explains how to efficiently manage multiple Flask applications on a single server using the centralized nginx security configuration.

> **📢 SECURITY REFERENCE:** For complete nginx security configuration details, see:
> - **[nginx_security_overview.md](nginx_security_overview.md)** - Complete configuration overview
> - **[nginx_security_migration.md](nginx_security_migration.md)** - Production deployment process

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Site 1        │    │   Site 2        │    │   Site 3        │
│   (Port 8001)   │    │   (Port 8002)   │    │   (Port 8003)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Nginx         │
                    │   (Port 80/443) │
                    └─────────────────┘
                                 │
                    ┌─────────────────┐
                    │ Centralized     │
                    │ Security Config │
                    └─────────────────┘
```

## Benefits of Centralized Security

1. **Unified Security Posture**: All sites protected by the same security rules
2. **Easy Maintenance**: Update security once, applies to all sites  
3. **Consistent Rate Limiting**: Shared rate limiting zones across all applications
4. **Resource Efficient**: No duplicate security configuration
5. **Scalable**: Add new sites without reconfiguring security
6. **Compliance Friendly**: Centralized security audit trail

## Multi-Site Configuration Structure

### Infrastructure Files (Version Controlled)
```
infrastructure/
├── nginx.conf              # Main config with shared rate limiting zones
├── security_http.conf      # HTTP-level security (CSP, headers)
├── security_server.conf    # Per-vhost security guards
├── tamermap                # Site 1 configuration
├── bareista                # Site 2 configuration (example)
├── newsite                 # Site 3 configuration (example)
├── tamermap.service        # Site 1 systemd service
├── bareista.service        # Site 2 systemd service
└── newsite.service         # Site 3 systemd service
```

### Deployed Structure
```
/etc/nginx/
├── nginx.conf                      # Shared rate limiting zones
├── snippets/
│   ├── security_http.conf         # Shared HTTP security
│   └── security_server.conf       # Shared server security
├── sites-available/
│   ├── tamermap                   # Site-specific config
│   ├── bareista                   # Site-specific config  
│   └── newsite                    # Site-specific config
└── sites-enabled/ (symlinks to sites-available)

/etc/systemd/system/
├── tamermap.service
├── bareista.service
└── newsite.service
```

## Setting Up Additional Sites

### 1. Create Site-Specific Configuration

Create a new nginx site configuration based on the tamermap template:

```bash
# Copy the tamermap config as a template
sudo cp /etc/nginx/sites-available/tamermap /etc/nginx/sites-available/newsite

# Edit for your new site
sudo nano /etc/nginx/sites-available/newsite
```

**Key changes needed:**
- Update `server_name` to your domain
- Change upstream port (e.g., 8002, 8003, etc.)
- Update log file names  
- Adjust any site-specific paths

### 2. Create Systemd Service

```bash
# Copy the tamermap service as a template
sudo cp /etc/systemd/system/tamermap.service /etc/systemd/system/newsite.service

# Edit for your new site
sudo nano /etc/systemd/system/newsite.service
```

**Key changes needed:**
- Update `WorkingDirectory` path
- Change port in `ExecStart` command
- Update user/group if different
- Adjust environment variables

### 3. Enable and Start Services

```bash
# Enable nginx site
sudo ln -s /etc/nginx/sites-available/newsite /etc/nginx/sites-enabled/

# Test nginx configuration  
sudo nginx -t

# Reload nginx if test passes
sudo systemctl reload nginx

# Reload systemd and start new service
sudo systemctl daemon-reload
sudo systemctl enable newsite.service
sudo systemctl start newsite.service

# Check status
sudo systemctl status newsite.service
```

## Site Management Commands

### Individual Site Control

```bash
# Start/stop/restart specific site
sudo systemctl start newsite.service
sudo systemctl stop newsite.service  
sudo systemctl restart newsite.service

# Check site status
sudo systemctl status newsite.service

# View site logs
sudo journalctl -u newsite.service -n 50
```

### Nginx Site Management

```bash
# Disable site (remove from sites-enabled)
sudo rm /etc/nginx/sites-enabled/newsite
sudo systemctl reload nginx

# Re-enable site  
sudo ln -s /etc/nginx/sites-available/newsite /etc/nginx/sites-enabled/
sudo systemctl reload nginx

# Test all configurations
sudo nginx -t
```

### Bulk Operations

```bash
# Restart all Flask services
sudo systemctl restart tamermap.service bareista.service newsite.service

# Check status of all sites
sudo systemctl status tamermap.service bareista.service newsite.service

# View nginx access logs for all sites
sudo tail -f /var/log/nginx/*_access.log

# View nginx error logs for all sites
sudo tail -f /var/log/nginx/*_error.log
```

## Port Management

### Standard Port Allocation
- **Site 1 (tamermap)**: Port 8001
- **Site 2 (bareista)**: Port 8002  
- **Site 3 (newsite)**: Port 8003
- **Continue incrementing**: 8004, 8005, etc.

### Port Conflict Resolution

```bash
# Check what's using a port
sudo netstat -tlnp | grep :8002

# Kill process if needed
sudo kill -9 <PID>

# Or use lsof
sudo lsof -i :8002
```

## SSL Certificate Management

### Multiple Domain Certificates

```bash
# Single certificate for multiple domains
sudo certbot --nginx -d tamermap.com -d www.tamermap.com

# Separate certificates for each site  
sudo certbot --nginx -d bareista.com -d www.bareista.com
sudo certbot --nginx -d newsite.com -d www.newsite.com

# Wildcard certificate (if using subdomains)
sudo certbot certonly --dns-cloudflare -d *.yourdomain.com
```

### Certificate Renewal

```bash
# Test renewal for all certificates
sudo certbot renew --dry-run

# Manual renewal if needed
sudo certbot renew

# Nginx will automatically reload after successful renewal
```

## Security Features (Centralized)

All sites automatically inherit:

- **Rate Limiting**: API (10 req/s), Admin (5 req/s), General (30 req/s)
- **Attack Prevention**: Malicious file blocking, path traversal protection  
- **Security Headers**: CSP, HSTS, X-Frame-Options, etc.
- **Request Limits**: 10MB max body size, optimized buffers

*For detailed security configuration, see [nginx_security_overview.md](nginx_security_overview.md)*

## Monitoring Multiple Sites

### Log Aggregation

```bash
# Monitor all access logs
sudo tail -f /var/log/nginx/tamermap_access.log /var/log/nginx/bareista_access.log

# Monitor all error logs
sudo tail -f /var/log/nginx/*_error.log

# Monitor all application logs
sudo journalctl -f -u tamermap.service -u bareista.service -u newsite.service
```

### Health Checks

```bash
# Quick health check script
#!/bin/bash
sites=("tamermap.com" "bareista.com" "newsite.com")
for site in "${sites[@]}"; do
    echo "Checking $site..."
    curl -I "https://$site" | head -1
done
```

## Troubleshooting Multi-Site Issues

### Common Problems

1. **Port Conflicts**
   ```bash
   # Check all listening ports
   sudo netstat -tlnp | grep :80[0-9][0-9]
   ```

2. **SSL Certificate Issues**  
   ```bash
   # Check certificate status
   sudo certbot certificates
   ```

3. **Service Dependencies**
   ```bash
   # Check all Flask services
   sudo systemctl status tamermap.service bareista.service newsite.service
   ```

4. **Nginx Configuration Conflicts**
   ```bash
   # Test configuration
   sudo nginx -t
   
   # Check for duplicate server_name entries
   grep -r "server_name" /etc/nginx/sites-enabled/
   ```

## Best Practices

1. **Consistent Naming**: Use consistent naming patterns for sites, logs, and services
2. **Port Management**: Document port assignments to avoid conflicts
3. **Version Control**: Keep all configurations in the infrastructure directory
4. **Testing**: Always test configurations before applying to production
5. **Monitoring**: Set up monitoring for all sites, not just the primary one
6. **Backup**: Regular backup of all site configurations and data

## Additional Resources

- **[nginx_security_overview.md](nginx_security_overview.md)** - Complete security configuration
- **[nginx_security_migration.md](nginx_security_migration.md)** - Production deployment process  
- **[nginx_deployment.md](nginx_deployment.md)** - Quick deployment reference
- **[update_systemd_service.md](update_systemd_service.md)** - Systemd service configuration 