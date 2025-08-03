**Tamermap Configuration Files Overview**

This document summarizes all configuration files modified or created during the Tamermap security hardening process. Include these in your Git repository for distribution, backup, and documentation.

---

## 1. Main Nginx Configuration

**Path:** `/etc/nginx/nginx.conf`
**Purpose:** Global settings for Nginx and HTTP block, including module loading, gzip settings, proxy header defaults, and rate-limit zone declarations:

* `limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;`
* `limit_req_zone $binary_remote_addr zone=admin:10m rate=5r/s;`
* Includes global snippets and site directories (`/etc/nginx/conf.d/*.conf`, `/etc/nginx/sites-enabled/*`).

## 2. Global HTTP Security Snippet

**Path:** `/etc/nginx/snippets/security_http.conf`
**Purpose:** HTTP-level security headers and request filters applied to *all* sites. Key elements:

* Content Security Policy (CSP) header removal when in Report-Only mode.
* Hardened HTTP headers (HSTS, X-Frame-Options, etc.)
* Common attack prevention (`if` checks for SQLi, XSS patterns)
* **Note:** Remove any duplicate `limit_req_zone` definitions here.

## 3. Per‑Vhost Security Snippet

**Path:** `/etc/nginx/snippets/security_server.conf`
**Purpose:** Per-site security guards (to include inside each `server {}` block):

* Deny hidden/backups (`location ~ /\.(?!well-known)`)
* Block dangerous extensions and wrappers
* Path-traversal and injection filters
* Rate limiting for `/admin/` (via `limit_req zone=admin`) if desired

## 4. Tamermap Virtual Host

**Path:** `/etc/nginx/sites-available/tamermap`
**Purpose:** Site-specific server block for Tamermap, with:

* HTTP to HTTPS redirect (port 80 → 443)
* SSL certificate and protocol settings
* CSP injection (`proxy_hide_header` + `add_header Content-Security-Policy`)
* Includes `security_server.conf` for guard rules
* Locations:

  * `/webhooks/stripe` (CIDR‑based bypass)
  * `/api/` (no auth; `limit_req zone=api`)
  * `/static/` (alias)
  * `/` (basic-auth; proxy\_pass to Flask)

**Symlink:** `/etc/nginx/sites-enabled/tamermap` → `../sites-available/tamermap`

## 5. Systemd Service File

**Path:** `/etc/systemd/system/tamermap.service`
**Purpose:** Manages the Gunicorn process for Tamermap:

* Runs as `User=tamermap`
* `WorkingDirectory=/home/tamermap/app`
* `ExecStart` points to the app's virtualenv Gunicorn command
* Reloaded after any config change (`systemctl daemon-reload`)

## 6. Documentation Files (Git Repo)

Include and version these markdown files in your repository under `/docs/`:

* `update_systemd_service.md`: Steps for updating systemd after path/user changes.
* `nginx_deployment.md`: Guide for deploying security config across sites (rate limits, headers, attack filters).
* `nginx_file_structure.md`: High-level file structure and dependencies (with updated file names/paths).
* `SECURITY.md`: Overview of security measures and TODOs (include CSP and rate-limit notes).
* `TESTING.md`: How to test rate limiting, CSP, and cache behavior in dev/staging.

## 7. Optional Geo-IP Blocking

**Path:** integrated into `/etc/nginx/nginx.conf` or a custom snippet (e.g. `/etc/nginx/snippets/geoip.conf`).

**Purpose:** Restrict access by country to reduce extraneous traffic and block attack sources outside your service region (North America).

**Implementation Steps:**

1. Install and prepare the GeoIP2 database (e.g., MaxMind GeoLite2-Country):

   ```bash
   sudo apt install nginx-module-geoip2
   wget -O /usr/share/GeoIP/GeoLite2-Country.mmdb "https://geolite.maxmind.com/download/geoip/database/GeoLite2-Country.mmdb.gz"
   gzip -d /usr/share/GeoIP/GeoLite2-Country.mmdb.gz
   ```

2. Configure Nginx to load the database (in `nginx.conf` http block or a snippet):

   ```nginx
   geoip2 /usr/share/GeoIP/GeoLite2-Country.mmdb {
       auto_reload  24h;
       $geoip2_country_code  country iso_code;
   }
   ```

3. Add access rules in your vhost (`/etc/nginx/sites-available/tamermap`):

   ```nginx
   server {
       # ... existing config ...

       # Block non-North America
       if ($geoip2_country_code !~ ^(US|CA|MX)$) {
           return 403;
       }

       # ... rest of server block ...
   }
   ```

**Considerations & Downsides:**

* **Database Updates:** The GeoIP DB changes monthly; automate `geoip2.auto_reload` or cron updates.
* **False Positives:** Legitimate users on VPNs or traveling outside North America may be blocked.
* **Proxy/CDN Traffic:** If behind a CDN (e.g., Cloudflare), you must restore real client IPs before GeoIP lookup using the `real_ip` module.
* **Performance Impact:** GeoIP lookups add a small per-request overhead; benchmark if under heavy load.

> **Tip:** Before enabling a hard block, test with `deny` rules in **`location /`** (e.g., `if ($geoip2_country_code !~ ...) { return 444; }`) or use logging only to gauge impact.

---

> **Tip:** Before deploying to production, use CSP Report-Only mode by changing the header name to `Content-Security-Policy-Report-Only` in your vhost, collect violation reports, then switch to enforcement once you have a clean report.
