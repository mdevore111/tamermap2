# Nginx Security Deployment Guide

> **📢 IMPORTANT:** This guide has been superseded by the comprehensive nginx security documentation. Please refer to:
> - **[nginx_security_overview.md](nginx_security_overview.md)** - Complete overview of all configuration files and their purposes
> - **[nginx_security_migration.md](nginx_security_migration.md)** - Step-by-step deployment process for production rollouts

## Quick Reference

The nginx security implementation provides:

### Security Features
- **Rate Limiting**: API (10 req/s), Admin (5 req/s), General (30 req/s)
- **Attack Prevention**: Blocks malicious file extensions, path traversal, injection attempts
- **Security Headers**: CSP, HSTS, X-Frame-Options, X-Content-Type-Options, etc.
- **Request Limits**: 10MB max body size with optimized buffer configurations

### Configuration Structure
- **`/etc/nginx/nginx.conf`** - Main config with rate limiting zones
- **`/etc/nginx/snippets/security_http.conf`** - HTTP-level security headers
- **`/etc/nginx/snippets/security_server.conf`** - Per-vhost security guards  
- **`/etc/nginx/sites-available/tamermap`** - Site-specific configuration
- **`/etc/systemd/system/tamermap.service`** - Application service

## For Existing Installations

If you have an existing nginx installation, follow the **[Production Rollout Process](nginx_security_migration.md)** which includes:

1. **Version Control & Backups** - Commit configurations and backup existing files
2. **Staging Tests** - Test with CSP Report-Only mode first
3. **Canary Deployment** - Deploy to subset of servers initially  
4. **Zero-Downtime Reload** - Graceful reloads across all servers
5. **Final Enforcement** - Switch to enforcing CSP mode

## For New Installations

For new installations, all security configurations are included in the infrastructure files:

```
infrastructure/
├── nginx.conf              # Main nginx config
├── security_http.conf      # HTTP security snippet
├── security_server.conf    # Server security snippet  
├── tamermap                # Site configuration
└── tamermap.service        # Systemd service
```

## SSL/HTTPS Setup

For production HTTPS setup:

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## Troubleshooting

### Common Issues

1. **Configuration Test Fails**
   ```bash
   sudo nginx -t
   ```
   Check error messages and verify file paths exist.

2. **502 Bad Gateway**
   ```bash
   sudo systemctl status tamermap.service
   sudo journalctl -u tamermap.service -n 50
   ```

3. **Rate Limiting Issues**
   Monitor logs: `/var/log/nginx/tamermap_error.log`

### Monitoring

```bash
# Monitor access logs
sudo tail -f /var/log/nginx/tamermap_access.log

# Monitor error logs  
sudo tail -f /var/log/nginx/tamermap_error.log

# Check blocked requests
sudo grep "444" /var/log/nginx/tamermap_access.log
```

## Additional Resources

- **[nginx_security_overview.md](nginx_security_overview.md)** - Complete configuration overview
- **[nginx_security_migration.md](nginx_security_migration.md)** - Production deployment process
- **[multi_site_management.md](multi_site_management.md)** - Managing multiple Flask applications
- **[update_systemd_service.md](update_systemd_service.md)** - Systemd service configuration 