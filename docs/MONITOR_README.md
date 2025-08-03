# Tamermap Application Monitor

A comprehensive monitoring system for the Tamermap Flask application that provides continuous health checks and automatic alerting.

## Features

### 🔍 **What It Monitors**

- **Process Health**: Gunicorn web server processes
- **Database**: SQLite connectivity and basic queries
- **Redis**: Session storage (DB 0) and cache (DB 1) connectivity
- **HTTP Endpoints**: Response codes and content verification
- **System Resources**: CPU, memory, disk usage, and load average
- **SSL Certificate**: Expiry date monitoring
- **Content Verification**: Map pins, Stripe checkout links, and key content

### 📧 **Smart Alerting**

- **Email Alerts**: Via existing Mailgun setup
- **Alert Throttling**: Prevents spam during extended outages
- **Severity Levels**: Critical vs. warning alerts
- **Detailed Reports**: Comprehensive failure information

### 🛠️ **Robust Design**

- **Single File**: Easy to maintain and deploy
- **Graceful Shutdown**: Handles SIGTERM/SIGINT properly
- **Error Recovery**: Continues monitoring after failures
- **Configurable**: Easy to adjust thresholds and endpoints
- **Comprehensive Logging**: File and console output

## Installation

### Prerequisites

- Python 3.7+
- Redis server
- Existing Tamermap application
- Mailgun configuration in environment

### Quick Setup

1. **Run the setup script**:
   ```bash
   sudo ./setup-monitor.sh
   ```

2. **Start the monitor**:
   ```bash
   sudo systemctl start tamermap-monitor
   ```

3. **Check status**:
   ```bash
   sudo systemctl status tamermap-monitor
   ```

### Manual Installation

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Make executable**:
   ```bash
   chmod +x monitor.py
   ```

3. **Install systemd service**:
   ```bash
   sudo cp tamermap-monitor.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable tamermap-monitor
   ```

4. **Start service**:
   ```bash
   sudo systemctl start tamermap-monitor
   ```

## Configuration

### 📊 **Monitoring Thresholds**

Edit `monitor.py` to adjust thresholds:

```python
# Monitoring intervals and thresholds
MONITOR_INTERVAL = 300  # 5 minutes between checks
DISK_THRESHOLD = 10     # Percent free space minimum
CPU_THRESHOLD = 80      # Percent CPU usage maximum
MEMORY_THRESHOLD = 85   # Percent memory usage maximum
LOAD_THRESHOLD = 5.0    # System load average maximum
```

### 📧 **Alert Recipients**

Update the alert recipients list:

```python
ALERT_RECIPIENTS = [
    "mark@markdevore.com",
    "admin@tamermap.com",  # Add more recipients
]
```

### 🌐 **Monitored Endpoints**

Add or modify endpoints to monitor:

```python
MONITOR_URLS = {
    "home": {
        "url": "https://tamermap.com/",
        "content_checks": [
            {"selector": ".map-container", "description": "Map container"},
            {"text": "Pokemon", "description": "Pokemon content"},
        ],
        "timeout": 15
    },
    "api": {  # Add new endpoint
        "url": "https://tamermap.com/api/health",
        "content_checks": [
            {"text": "OK", "description": "API health check"},
        ],
        "timeout": 5
    }
}
```

## Usage

### 🔧 **Service Management**

```bash
# Start service
sudo systemctl start tamermap-monitor

# Stop service
sudo systemctl stop tamermap-monitor

# Restart service
sudo systemctl restart tamermap-monitor

# Check status
sudo systemctl status tamermap-monitor

# Enable auto-start
sudo systemctl enable tamermap-monitor

# Disable auto-start
sudo systemctl disable tamermap-monitor
```

### 📝 **Viewing Logs**

```bash
# View systemd logs (live)
sudo journalctl -u tamermap-monitor -f

# View application logs
tail -f /var/www/tamermap/logs/monitor.log

# View recent logs
sudo journalctl -u tamermap-monitor --since "1 hour ago"
```

### 🧪 **Testing**

```bash
# Test monitor configuration
cd /var/www/tamermap
python3 -c "from monitor import TamermapMonitor; print('✅ Configuration OK')"

# Run single check cycle
python3 monitor.py --test-run  # (if implemented)
```

## Monitoring Details

### 🔍 **Check Types**

| Check | Description | Critical? |
|-------|-------------|-----------|
| `gunicorn` | Web server processes running | ✅ Yes |
| `database` | SQLite connectivity and queries | ✅ Yes |
| `redis` | Session/cache storage connectivity | ⚠️ Warning |
| `http_home` | Main page accessibility | ✅ Yes |
| `http_try_pro` | Pro signup page | ⚠️ Warning |
| `system_resources` | CPU, memory, disk usage | ⚠️ Warning |
| `ssl_cert` | Certificate expiry | ⚠️ Warning |

### 📧 **Alert Types**

- **Critical**: Service-disrupting failures (Gunicorn down, database inaccessible, main page down)
- **Warning**: Degraded performance or potential issues (high resource usage, SSL expiry)

### ⏰ **Alert Throttling**

- **Throttle Period**: 30 minutes per alert type
- **Prevents Spam**: During extended outages
- **Separate Tracking**: Critical and warning alerts tracked separately

## File Structure

```
/var/www/tamermap/
├── monitor.py                    # Main monitoring script
├── tamermap-monitor.service      # Systemd service file
├── requirements.txt             # Python dependencies (includes monitor deps)
├── setup-monitor.sh             # Installation script
├── MONITOR_README.md            # This documentation
└── logs/
    ├── monitor.log              # Monitor application logs
    └── alert_history.json       # Alert throttling data
```

## Troubleshooting

### 🚨 **Common Issues**

#### Service Won't Start
```bash
# Check service status
sudo systemctl status tamermap-monitor

# Check logs
sudo journalctl -u tamermap-monitor -n 50
```

#### Database Connection Issues
```bash
# Check database file permissions
ls -la /var/www/tamermap/instance/tamermap_data.db

# Test database connectivity
sqlite3 /var/www/tamermap/instance/tamermap_data.db "SELECT COUNT(*) FROM user;"
```

#### Redis Connection Issues
```bash
# Check Redis status
sudo systemctl status redis

# Test Redis connectivity
redis-cli ping
```

#### Email Alerts Not Working
```bash
# Check Mailgun configuration
grep MAILGUN /var/www/tamermap/.env

# Test email sending
cd /var/www/tamermap
python3 -c "from app.custom_email import custom_send_mail; print('Mailgun config OK')"
```

### 🔧 **Performance Tuning**

#### Adjust Check Interval
```python
# For more frequent checks (3 minutes)
MONITOR_INTERVAL = 180

# For less frequent checks (10 minutes)
MONITOR_INTERVAL = 600
```

#### Reduce Resource Usage
```python
# Increase CPU threshold
CPU_THRESHOLD = 90

# Reduce memory threshold
MEMORY_THRESHOLD = 75
```

## Advanced Features

### 📊 **Metrics Collection**

The monitor collects metrics that can be used for:
- Performance trend analysis
- Capacity planning
- Historical health reports

### 🔄 **Extensibility**

Easy to add new checks:

```python
def check_custom_service() -> CheckResult:
    """Check custom service"""
    try:
        # Your custom check logic here
        return CheckResult("custom", True, "Service OK")
    except Exception as e:
        return CheckResult("custom", False, f"Service error: {e}")

# Add to run_all_checks() method
results.append(check_custom_service())
```

### 🌐 **Multi-Environment Support**

The monitor can be adapted for:
- Development environments
- Staging environments
- Multiple production instances

## Security Considerations

- **Least Privilege**: Runs as dedicated user
- **File Permissions**: Restricted access to logs and database
- **Network**: Only required outbound connections
- **Secrets**: Uses existing environment variables

## Support

For issues or questions:
1. Check the logs first
2. Verify configuration
3. Test individual components
4. Check system resources

The monitor is designed to be robust and self-healing, but proper configuration and maintenance are essential for optimal performance.

---

**📧 Email alerts will be sent to**: mark@markdevore.com  
**⏰ Check interval**: 5 minutes  
**🔧 Configuration file**: `/var/www/tamermap/monitor.py` 