# Production Rollout Process for Tamermap Security Configuration

This guide describes a step-by-step process to deploy the hardened Nginx security configuration into the production environment with minimal downtime and risk.

---

## 1. Version Control and Backups

1. **Commit and tag** all configuration changes in your Git repository:

   * `/etc/nginx/nginx.conf`
   * `/etc/nginx/snippets/security_http.conf`
   * `/etc/nginx/snippets/security_server.conf`
   * `/etc/nginx/sites-available/tamermap`
   * `/etc/systemd/system/tamermap.service`

   ```bash
   git add etc/nginx/* etc/systemd/system/tamermap.service
   git commit -m "Hardening: add CSP, rate-limits, security snippets"
   git tag vX.Y-security-rollout
   ```

2. **Backup existing production configs** on each server:

   ```bash
   sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak_$(date +%F_%T)
   sudo cp /etc/nginx/sites-available/tamermap /etc/nginx/sites-available/tamermap.bak_$(date +%F_%T)
   ```

---

## 2. Staging Test with Report-Only CSP

1. **Switch CSP enforcement to Report-Only** in staging:

   ```nginx
   # In /etc/nginx/sites-available/tamermap (staging)
   proxy_hide_header Content-Security-Policy-Report-Only;
   add_header Content-Security-Policy-Report-Only "<your CSP here>" always;
   ```
2. **Reload Nginx**:

   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. **Collect violation reports**:

   * Configure `report-uri` or `report-to` to point to a logging endpoint.
   * Monitor for any blocked resource reports over 24–48 hours.
4. **Tweak** your policy to whitelist any legitimate sources missed.

---

## 3. Canary Deployment

If you have multiple production servers behind a load balancer:

1. **Deploy** updated configs to a small subset (10–20%) of servers.
2. **Gracefully reload** on those servers:

   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. **Monitor**:

   * Nginx error logs for 403/503 responses.
   * Application logs and user feedback.
4. **Rollback** immediately by restoring backups if critical issues appear.
5. **Roll forward** to remaining servers once stable.

---

## 4. Zero-Downtime Reload on All Servers

For each server individually (or via automation) after canary succeeds:

1. **Lint** the configuration:

   ```bash
   sudo nginx -t
   ```
2. **Reload** gracefully:

   ```bash
   sudo systemctl reload nginx
   ```

   * Nginx spawns new workers with the updated config and retires old workers after active connections finish.
3. **Smoke-test** key endpoints:

   ```bash
   curl -I https://tamermap.com/       # 200 or 301→HTTPS
   curl -I https://tamermap.com/api/health
   curl -I https://tamermap.com/admin/ # 401 or 200
   curl -I https://tamermap.com/static/css/main.css
   ```

---

## 5. Automate the Process

* **Shell script or Ansible playbook** that:

  1. Pulls latest Git tag
  2. Runs `nginx -t`
  3. Executes `systemctl reload nginx`
  4. Sends a notification on Slack/email if any step fails.
* Store automation in your deployment repository alongside your code.

---

## 6. Final Enforcement and Cleanup

1. **Switch back** from Report-Only to enforcing CSP in production:

   ```nginx
   proxy_hide_header Content-Security-Policy;
   add_header Content-Security-Policy "<your final CSP>" always;
   ```
2. **Reload** Nginx:

   ```bash
   sudo nginx -t && sudo systemctl reload nginx
   ```
3. **Monitor** for any new CSP violations in your logs or report endpoint.
4. **Remove** any temporary reporting endpoints or debug settings.
5. **Document** the rollout in `nginx_deployment.md` and update version tags.

---

> **Pro Tip:** Always test in an incognito window or with CSP disabled in your browser to confirm the expected behavior before and after enforcement.

## 7. Version Control of Config Files

It is highly recommended to version control your server configuration alongside your application code. Commit the following files (or templated copies) into your Git repository under a `config/` or `infrastructure/` directory:

* **Nginx main config:** `/etc/nginx/nginx.conf`
* **Rate limiting snippet:** `/etc/nginx/snippets/nginx_rate_limiting.conf`
* **HTTP security snippet:** `security_http.conf`
* **Per-vhost security snippet:** `/etc/nginx/snippets/security_server.conf`
* **Tamermap vhost:** `/etc/nginx/sites-available/tamermap`
* **Systemd service:** `/etc/systemd/system/tamermap.service`

### Best Practices

* Use placeholders or environment variables for any secrets (avoid hard-coding keys).
* Implement CI checks to run `nginx -t` on pull requests.
* Tag and branch configuration for production vs staging (e.g., `prod-config`).
* Backup production overrides and store them securely separate from the code repository.
