# Testing Guide

This document describes how to test rate limiting and caching functionality in both local development and staging environments.

> **Security Testing**: For testing nginx security configuration (headers, attack prevention, etc.), see the security testing procedures in [nginx_security_migration.md](nginx_security_migration.md#staging-test-with-report-only-csp)

## Environment Setup

### Local Development
```powershell
# Set environment variables
$env:FLASK_ENV = "development"
$env:TEST_API_KEY = "test_key_local"  # Or your custom key

# Start the development server
python run.py
```

### Staging (dev.tamermap.com)
The staging environment is already configured for testing. Make sure you have:
- Access to dev.tamermap.com
- The correct TEST_API_KEY value

## Rate Limiting Tests

### Using the Test Script

1. Test on Local Development:
```powershell
# Basic local test
python -m tests.test_rate_limit --env local

# Or with custom URL
python -m tests.test_rate_limit --url http://localhost:5000
```

2. Test on Staging:
```powershell
# Basic staging test
python -m tests.test_rate_limit --env staging

# Or with custom URL
python -m tests.test_rate_limit --url https://dev.tamermap.com
```

### Manual Testing with curl

1. Local Development:
```powershell
# Check environment
curl -H "X-Test-Key: test_key_local" http://localhost:5000/dev/environment-check

# Test rate limit
curl -H "X-Test-Key: test_key_local" http://localhost:5000/dev/test-limit
```

2. Staging:
```powershell
# Check environment
curl -H "X-Test-Key: test_key_local" https://dev.tamermap.com/dev/environment-check

# Test rate limit
curl -H "X-Test-Key: test_key_local" https://dev.tamermap.com/dev/test-limit
```

## Cache Testing

### Web Interface

1. Local Development:
- Visit: `http://localhost:5000/dev/test-cache`
- Add header: `X-Test-Key: test_key_local`

2. Staging:
- Visit: `https://dev.tamermap.com/dev/test-cache`
- Add header: `X-Test-Key: test_key_local`

### API Endpoints

Test the cache API directly:

1. Local Development:
```powershell
curl -H "X-Test-Key: test_key_local" http://localhost:5000/dev/api/test-cache-data
```

2. Staging:
```powershell
curl -H "X-Test-Key: test_key_local" https://dev.tamermap.com/dev/api/test-cache-data
```

## Security Testing

### Attack Prevention Tests

These tests verify that Nginx blocks various attack patterns in the URL **path**:

```bash
# Path Traversal Attacks (should return 444)
curl -I "https://dev.tamermap.com/../../../etc/passwd"
curl -I "https://dev.tamermap.com/..%2F..%2F..%2Fetc%2Fpasswd"

# Dangerous File Extensions (should return 444)
curl -I "https://dev.tamermap.com/test.php"
curl -I "https://dev.tamermap.com/shell.jsp"
curl -I "https://dev.tamermap.com/backup.asp"

# Wrapper/Stream Attacks in Path (should return 444)
curl -I "https://dev.tamermap.com/php://filter/resource=index.html"
curl -I "https://dev.tamermap.com/data://test"
curl -I "https://dev.tamermap.com/file:///etc/passwd"
```

### Query Parameter Wrapper Tests

**Note**: The current configuration only blocks wrappers in the URL path, not in query parameters:

```bash
# Blocked (wrapper in path) - returns 444
curl -I "https://dev.tamermap.com/php://filter/resource=index.html"

# Allowed (wrapper in query string) - returns 200 OK
curl -I "https://dev.tamermap.com/?url=php://filter/resource=index.html"
curl -I "https://dev.tamermap.com/?data://something"
```

### Enhanced Query Parameter Protection (Optional)

If you want to block wrappers in query parameters as well, add this to `/etc/nginx/snippets/security_http.conf`:

```nginx
# Block wrappers in query parameters
if ($args ~* "(php://|data://|file://|ftp://|https?://)") {
    return 444;
}
```

After adding this rule:
1. Test the configuration: `sudo nginx -t`
2. Reload nginx: `sudo systemctl reload nginx`
3. Test again - query parameter wrappers should now return 444

### Security Headers Verification

```bash
# Check security headers
curl -I "https://dev.tamermap.com/" | grep -E "(X-Frame-Options|X-Content-Type-Options|X-XSS-Protection|Content-Security-Policy|Strict-Transport-Security)"

# Expected headers:
# X-Frame-Options: SAMEORIGIN
# X-Content-Type-Options: nosniff
# X-XSS-Protection: 1; mode=block
# Content-Security-Policy: [your CSP policy]
# Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## Comprehensive Security Testing

### 🛡️ **Test Attack Prevention (Should Return 444)**

```bash
# 1. Path Traversal Attacks
curl -I "https://dev.tamermap.com/../../../etc/passwd"
curl -I "https://dev.tamermap.com/..%2F..%2F..%2Fetc%2Fpasswd"
curl -I "https://dev.tamermap.com/%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd"

# 2. Dangerous File Extensions
curl -I "https://dev.tamermap.com/test.php"
curl -I "https://dev.tamermap.com/shell.jsp"
curl -I "https://dev.tamermap.com/backup.asp"
curl -I "https://dev.tamermap.com/script.pl"
curl -I "https://dev.tamermap.com/backup.sh"

# 3. Wrapper/Stream Attacks
curl -I "https://dev.tamermap.com/php://filter/resource=index.html"
curl -I "https://dev.tamermap.com/data://test"
curl -I "https://dev.tamermap.com/file:///etc/passwd"
curl -I "https://dev.tamermap.com/ftp://malicious.com/file"

# 4. SQL Injection Attempts
curl -I "https://dev.tamermap.com/?id=1' UNION SELECT * FROM users--"
curl -I "https://dev.tamermap.com/?id=1%20UNION%20SELECT%20*%20FROM%20users--"

# 5. Code Injection Attempts
curl -I "https://dev.tamermap.com/?cmd=eval(base64_decode('test'))"
curl -I "https://dev.tamermap.com/?cmd=exec('ls')"

# 6. PHP Info Attacks
curl -I "https://dev.tamermap.com/phpinfo.php"
curl -I "https://dev.tamermap.com/?page=phpinfo()"

# 7. Suspicious User Agents
curl -I -H "User-Agent: sqlmap/1.0" "https://dev.tamermap.com/"
curl -I -H "User-Agent: nikto/2.1.6" "https://dev.tamermap.com/"
curl -I -H "User-Agent: nmap/7.80" "https://dev.tamermap.com/"

# 8. Malicious Referer Headers
curl -I -H "Referer: http://evil.com/phpinfo" "https://dev.tamermap.com/"
curl -I -H "Referer: http://evil.com/eval" "https://dev.tamermap.com/"
```

### ✅ **Test Legitimate Traffic (Should Return 200)**

```bash
# 1. Normal Pages
curl -I "https://dev.tamermap.com/"
curl -I "https://dev.tamermap.com/login"
curl -I "https://dev.tamermap.com/admin/"

# 2. API Endpoints (require proper referrer)
curl -I -H "Referer: https://dev.tamermap.com/" "https://dev.tamermap.com/api/retailers"
curl -I -H "Referer: https://dev.tamermap.com/" "https://dev.tamermap.com/api/events"
curl -I -H "Referer: https://dev.tamermap.com/" "https://dev.tamermap.com/api/map-data"

# 3. Static Assets
curl -I "https://dev.tamermap.com/static/css/main.css"
curl -I "https://dev.tamermap.com/static/js/app.js"
curl -I "https://dev.tamermap.com/static/images/logo.png"

# 4. Webhooks
curl -I "https://dev.tamermap.com/webhooks/stripe"

# 5. Normal Query Parameters
curl -I "https://dev.tamermap.com/?page=about"
curl -I "https://dev.tamermap.com/?id=123"
curl -I "https://dev.tamermap.com/?search=test"

# 6. Normal User Agents
curl -I -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" "https://dev.tamermap.com/"
curl -I -H "User-Agent: curl/7.68.0" "https://dev.tamermap.com/"

# 7. Normal Referer Headers
curl -I -H "Referer: https://google.com" "https://dev.tamermap.com/"
curl -I -H "Referer: https://dev.tamermap.com/" "https://dev.tamermap.com/admin/"
```

### 🔍 **Test Rate Limiting**

```bash
# Test API rate limiting (30 req/s)
for i in {1..35}; do
  echo "Request $i:"
  curl -I -H "Referer: https://dev.tamermap.com/" "https://dev.tamermap.com/api/retailers"
  sleep 0.1
done

# Test admin rate limiting (10 req/s)
for i in {1..15}; do
  echo "Admin Request $i:"
  curl -I "https://dev.tamermap.com/admin/"
  sleep 0.1
done
```

### 📊 **Monitor Security Logs**

```bash
# Monitor nginx access logs for blocked requests (444 responses)
sudo tail -f /var/log/nginx/tamermap_access.log | grep " 444 "

# Monitor nginx error logs
sudo tail -f /var/log/nginx/tamermap_error.log

# Check for rate limiting responses (429)
sudo tail -f /var/log/nginx/tamermap_access.log | grep " 429 "
```

## Expected Results

### Rate Limiting
- First 3 requests within a minute: Success (200 OK)
- 4th and subsequent requests: Rate Limited (429 Too Many Requests)
- Headers show remaining requests and reset time

### Caching
- First request: Fresh data with new timestamp
- Subsequent requests within 60 seconds: Same timestamp (cached)
- After 60 seconds: New timestamp (cache expired)

### Security Testing
- **Attack attempts**: Should return 444 (Connection Closed)
- **Legitimate traffic**: Should return 200 OK
- **Rate limiting**: Should return 429 when exceeded
- **Security headers**: Should be present in all responses

## Troubleshooting

### Common Issues

1. 404 Not Found
- Check if the development server is running
- Verify the correct URL
- Ensure FLASK_ENV is set to "development"

2. 403 Forbidden
- Check if X-Test-Key header is present
- Verify TEST_API_KEY value is correct

3. Connection Refused
- Check if the development server is running
- Verify the port number
- Check for firewall issues

4. 444 Connection Closed
- This is expected for attack attempts
- Verify legitimate traffic still works

5. 429 Too Many Requests
- Rate limiting is working
- Wait for the rate limit window to reset

### Getting Help

If you encounter issues:
1. Check the application logs
2. Run environment check endpoint
3. Verify all environment variables
4. Contact the development team

## Security Note

The test endpoints are:
- Only available in development and staging environments
- Protected by API key authentication
- Rate limited to prevent abuse
- Not accessible in production

**Additional Security Testing**: The nginx security layer provides comprehensive protection including CSP, attack prevention, and security headers. For testing these features:
- Use CSP Report-Only mode in staging first
- Test rate limiting with the provided scripts
- Monitor security logs for blocked attacks  
- Verify security headers with browser dev tools

*For complete security configuration testing, see [nginx_security_migration.md](nginx_security_migration.md)*

Remember to never expose test endpoints or API keys in production environments. 