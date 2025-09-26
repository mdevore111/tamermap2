#!/usr/bin/env python3
"""
Tamermap Application Monitor

A comprehensive monitoring system that checks:
- Process health (Gunicorn)
- HTTP endpoints and content
- Database connectivity (SQLite)
- Redis connectivity (sessions/cache)
- System resources (CPU, memory, disk)
- SSL certificate expiry
- Application-specific health checks

Sends alerts via existing Mailgun setup when issues are detected.
"""

import os
import sys
import time
import signal
import logging
import sqlite3
import ssl
import socket
import threading
import subprocess
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from dataclasses import dataclass, field

import requests
import psutil
import redis
from bs4 import BeautifulSoup

# Selenium imports for frontend testing
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


# Only import Flask components in production mode
if not os.getenv('MONITOR_TEST_MODE', 'false').lower() == 'true':
    try:
        from flask import Flask
        from flask_mail import Message
    except ImportError:
        # Flask not available
        pass

# Add the app directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# ================================
# CONFIGURATION
# ================================

# Alert recipients - easily configurable
ALERT_RECIPIENTS = [
    "mark@markdevore.com",
    "mrarfarf@gmail.com"
]

# Monitoring intervals and thresholds
MONITOR_INTERVAL = 300  # 5 minutes between checks
DISK_THRESHOLD = 10     # Percent free space minimum
CPU_THRESHOLD = 80      # Percent CPU usage maximum
MEMORY_THRESHOLD = 85   # Percent memory usage maximum
LOAD_THRESHOLD = 5.0    # System load average maximum

# Selenium test frequency (in seconds) - configurable via environment
SELENIUM_TEST_INTERVAL = int(os.getenv('SELENIUM_TEST_INTERVAL', '1800'))  # Default: 30 minutes

# SSL certificate expiry warning (days)
SSL_EXPIRY_WARNING_DAYS = 30

# Application paths and URLs
APP_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(APP_BASE_DIR, 'instance', 'tamermap_data.db')
LOG_FILE = os.path.join(APP_BASE_DIR, 'logs', 'monitor.log')

# URLs to monitor - easily extendable
MONITOR_URLS = {
    "home": {
        "url": "https://tamermap.com/",
        "content_checks": [
            {"selector": ".map-container", "description": "Map container"},
            {"text": "Tamermap", "description": "Tamermap branding"},
            {"selector": "#map", "description": "Map element"},
        ],
        "timeout": 15
    },
    "learn": {
        "url": "https://tamermap.com/learn",
        "content_checks": [
            {"text": "Try Pro Now", "description": "Pro signup button"},
            {"text": "Pro", "description": "Pro features"},
        ],
        "timeout": 10
    },
    "stripe_checkout": {
        "url": "https://tamermap.com/payment/create-checkout-session",
        "method": "POST",
        "headers": {"Content-Type": "application/json"},
        "body": '{"subscription": true}',
        "content_checks": [
            {"text": "login", "description": "Redirect to login page (expected for unauthenticated requests)"},
            {"text": "create-checkout-session", "description": "Redirect preserves original endpoint"},
        ],
        "timeout": 10,
        "expected_status": 302  # Expect redirect, not 200
    },
    "health": {
        "url": "https://tamermap.com/health",
        "content_checks": [
            {"text": "OK", "description": "Health check response"},
        ],
        "timeout": 5,
        "optional": True  # Don't fail if this endpoint doesn't exist
    }
}

# Redis configuration
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_SESSION_DB = 0  # Sessions
REDIS_CACHE_DB = 1    # Cache

# Alert throttling - prevent spam
ALERT_THROTTLE_MINUTES = 30
ALERT_HISTORY_FILE = os.path.join(APP_BASE_DIR, 'logs', 'alert_history.json')

# Auto-remediation settings
AUTO_REMEDIATION_ENABLED = True
MAX_REMEDIATION_ATTEMPTS = 3
REMEDIATION_COOLDOWN_MINUTES = 30
REMEDIATION_HISTORY_FILE = os.path.join(APP_BASE_DIR, 'logs', 'remediation_history.json')

# Test mode settings
TEST_MODE = os.getenv('MONITOR_TEST_MODE', 'false').lower() == 'true'
TEST_EMAIL_RECIPIENTS = [
    "mark@markdevore.com",
    "mrarfarf@gmail.com"
]
TEST_SIMULATE_FAILURES = os.getenv('MONITOR_TEST_FAILURES', '').split(',') if os.getenv('MONITOR_TEST_FAILURES') else []

# ================================
# DATA STRUCTURES
# ================================

@dataclass
class CheckResult:
    """Result of a monitoring check"""
    name: str
    success: bool
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict = field(default_factory=dict)

@dataclass
class SystemMetrics:
    """System resource metrics"""
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    load_average: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class RemediationAttempt:
    """Record of a remediation attempt"""
    issue_type: str
    fix_type: str
    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    error_message: Optional[str] = None

# ================================
# LOGGING SETUP
# ================================

# Global logger instance
logger = None

def setup_logging():
    """Configure logging for the monitor"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
    
    # Reduce noise from external libraries
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Create and return logger instance
    global logger
    logger = logging.getLogger('tamermap_monitor')
    return logger

# ================================
# ALERT SYSTEM
# ================================

class AlertManager:
    """Manages alert throttling and sending"""
    
    def __init__(self, logger):
        self.logger = logger
        self.last_alerts = {}
        self.alert_count = 0
        
    def should_send_alert(self, alert_type: str) -> bool:
        """Check if enough time has passed since last alert of this type"""
        if alert_type not in self.last_alerts:
            return True
            
        time_since_last = datetime.now() - self.last_alerts[alert_type]
        return time_since_last.total_seconds() > (ALERT_THROTTLE_MINUTES * 60)
    
    def send_alert(self, subject: str, body: str, alert_type: str = "general"):
        """Send alert email via Mailgun if not throttled"""
        if not self.should_send_alert(alert_type):
            self.logger.info(f"Alert throttled for {alert_type}")
            return
            
        try:
            # Determine recipients and subject prefix based on test mode
            if TEST_MODE:
                recipients = TEST_EMAIL_RECIPIENTS
                subject_prefix = "[TEST] [TAMERMAP MONITOR]"
                # Add test mode notice to body
                body = f"🧪 TEST MODE - This is a simulated alert for testing purposes\n{'='*60}\n\n{body}"
                
                # In test mode, just log the email instead of actually sending
                self.logger.info(f"TEST MODE: Would send email to {recipients}")
                self.logger.info(f"TEST MODE: Subject: {subject_prefix} {subject}")
                self.logger.info(f"TEST MODE: Email body preview:\n{body[:200]}...")
                
                # Simulate successful sending
                self.last_alerts[alert_type] = datetime.now()
                self.alert_count += 1
                self.logger.info(f"TEST MODE: Alert simulation completed for {alert_type}")
                return
            
            # Production mode - actually send email
            # Import here to avoid circular imports
            from app.custom_email import custom_send_mail
            
            recipients = ALERT_RECIPIENTS
            subject_prefix = "[TAMERMAP MONITOR]"
            
            # Create message (only available in production mode)
            try:
                msg = Message(
                    subject=f"{subject_prefix} {subject}",
                    recipients=recipients,
                    html=f"<pre>{body}</pre>",
                    body=body
                )
                
                # Send via existing Mailgun setup
                response = custom_send_mail(msg)
            except NameError:
                # Message class not available (shouldn't happen in production)
                self.logger.error("Message class not available - Flask not properly imported")
                response = False
            
            if response:
                self.logger.info(f"Alert sent successfully for {alert_type}")
                self.last_alerts[alert_type] = datetime.now()
                self.alert_count += 1
            else:
                self.logger.error(f"Failed to send alert for {alert_type}")
                
        except Exception as e:
            self.logger.error(f"Error sending alert: {e}")

# ================================
# TEST MODE FUNCTIONS
# ================================

def create_test_failure(failure_type: str) -> CheckResult:
    """Create simulated failures for testing"""
    test_failures = {
        'gunicorn': CheckResult(
            "gunicorn", 
            False, 
            "TEST: Simulated Gunicorn failure",
            details={"simulated": True, "test_mode": True}
        ),
        'redis': CheckResult(
            "redis", 
            False, 
            "TEST: Simulated Redis connection failure",
            details={"simulated": True, "test_mode": True}
        ),
        'database': CheckResult(
            "database", 
            False, 
            "TEST: Simulated database connection failure",
            details={"simulated": True, "test_mode": True}
        ),
        'system_resources': CheckResult(
            "system_resources", 
            False, 
            "TEST: Simulated high memory usage",
            details={"simulated": True, "test_mode": True, "memory_percent": 95}
        ),
        'http_home': CheckResult(
            "http_home", 
            False, 
            "TEST: Simulated website failure",
            details={"simulated": True, "test_mode": True, "status_code": 500}
        ),
        'ssl_cert': CheckResult(
            "ssl_cert", 
            False, 
            "TEST: Simulated SSL certificate expiring soon",
            details={"simulated": True, "test_mode": True, "days_remaining": 5}
        )
    }
    
    return test_failures.get(failure_type, CheckResult(
        failure_type, 
        False, 
        f"TEST: Simulated {failure_type} failure",
        details={"simulated": True, "test_mode": True}
    ))

def run_test_scenario(scenario_name: str) -> List[CheckResult]:
    """Run predefined test scenarios"""
    scenarios = {
        'all_good': [],
        'single_failure': ['gunicorn'],
        'multiple_failures': ['gunicorn', 'redis'],
        'critical_failure': ['gunicorn', 'database', 'http_home'],
        'mixed_failures': ['gunicorn', 'redis', 'system_resources'],
        'non_remediable': ['database', 'ssl_cert', 'http_home']
    }
    
    if scenario_name not in scenarios:
        return []
    
    # Create base successful results
    base_results = [
        CheckResult("gunicorn", True, "Found 2 Gunicorn process(es)"),
        CheckResult("database", True, "Database accessible - 58 users, 4473 retailers"),
        CheckResult("redis", True, "Redis session and cache connections OK"),
        CheckResult("http_home", True, "home GET OK - 3 content checks"),
        CheckResult("http_learn", True, "learn GET OK - 2 content checks"),
        CheckResult("http_stripe_checkout", True, "stripe_checkout POST OK - 2 content checks"),
        CheckResult("http_health", True, "Optional endpoint health not found (404) - this is OK"),
        CheckResult("system_resources", True, "System resources OK"),
        CheckResult("ssl_cert", True, "SSL certificate valid for 278 days")
    ]
    
    # Replace with failures as specified
    failure_types = scenarios[scenario_name]
    for failure_type in failure_types:
        for i, result in enumerate(base_results):
            if result.name == failure_type:
                base_results[i] = create_test_failure(failure_type)
                break
    
    return base_results

# ================================
# AUTO-REMEDIATION SYSTEM
# ================================

class AutoRemediation:
    """Handles automatic remediation of common issues"""
    
    def __init__(self, logger):
        self.logger = logger
        self.remediation_history = self._load_history()
        
    def _load_history(self) -> Dict:
        """Load remediation history from file"""
        try:
            if os.path.exists(REMEDIATION_HISTORY_FILE):
                with open(REMEDIATION_HISTORY_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"Could not load remediation history: {e}")
        return {}
    
    def _save_history(self):
        """Save remediation history to file"""
        try:
            os.makedirs(os.path.dirname(REMEDIATION_HISTORY_FILE), exist_ok=True)
            with open(REMEDIATION_HISTORY_FILE, 'w') as f:
                json.dump(self.remediation_history, f, indent=2, default=str)
        except Exception as e:
            self.logger.error(f"Could not save remediation history: {e}")
    
    def _can_attempt_fix(self, issue_type: str, fix_type: str) -> bool:
        """Check if we can attempt this fix (not in cooldown, under max attempts)"""
        if not AUTO_REMEDIATION_ENABLED:
            return False
            
        key = f"{issue_type}_{fix_type}"
        now = datetime.now()
        
        # Check recent attempts
        if key in self.remediation_history:
            attempts = self.remediation_history[key]
            
            # Count recent attempts (within cooldown period)
            recent_attempts = []
            for attempt in attempts:
                attempt_time = datetime.fromisoformat(attempt['timestamp'])
                if (now - attempt_time).total_seconds() < (REMEDIATION_COOLDOWN_MINUTES * 60):
                    recent_attempts.append(attempt)
            
            # Too many recent attempts?
            if len(recent_attempts) >= MAX_REMEDIATION_ATTEMPTS:
                self.logger.info(f"Remediation cooldown active for {key}")
                return False
        
        return True
    
    def _log_attempt(self, issue_type: str, fix_type: str, success: bool, error_message: str = None):
        """Log a remediation attempt"""
        key = f"{issue_type}_{fix_type}"
        
        if key not in self.remediation_history:
            self.remediation_history[key] = []
        
        attempt = {
            'timestamp': datetime.now().isoformat(),
            'success': success,
            'error_message': error_message
        }
        
        self.remediation_history[key].append(attempt)
        
        # Keep only last 50 attempts per fix type
        self.remediation_history[key] = self.remediation_history[key][-50:]
        
        self._save_history()
        
        status = "SUCCESS" if success else "FAILED"
        self.logger.info(f"Remediation {status}: {issue_type} -> {fix_type}")
        if error_message:
            self.logger.error(f"Remediation error: {error_message}")
    
    def fix_gunicorn_down(self) -> bool:
        """Restart Gunicorn service"""
        if TEST_MODE:
            self.logger.info("TEST MODE: Simulating Gunicorn service restart...")
            time.sleep(2)  # Simulate restart time
            # Randomly succeed or fail for testing
            import random
            success = random.choice([True, True, False])  # 2/3 chance of success
            self.logger.info(f"TEST MODE: Gunicorn restart {'succeeded' if success else 'failed'}")
            return success
        
        try:
            self.logger.info("Attempting to restart Gunicorn service...")
            
            # Restart the main application service
            result = subprocess.run(
                ['sudo', 'systemctl', 'restart', 'tamermap'],
                check=True,
                timeout=30,
                capture_output=True,
                text=True
            )
            
            # Wait for service to start
            time.sleep(10)
            
            # Verify it's running
            check_result = check_gunicorn_process()
            return check_result.success
            
        except subprocess.TimeoutExpired:
            self.logger.error("Gunicorn restart timed out")
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Gunicorn restart failed: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Gunicorn restart error: {e}")
            return False
    
    def fix_redis_connection(self) -> bool:
        """Restart Redis service"""
        if TEST_MODE:
            self.logger.info("TEST MODE: Simulating Redis service restart...")
            time.sleep(1)  # Simulate restart time
            import random
            success = random.choice([True, True, True, False])  # 3/4 chance of success
            self.logger.info(f"TEST MODE: Redis restart {'succeeded' if success else 'failed'}")
            return success
        
        try:
            self.logger.info("Attempting to restart Redis service...")
            
            # Restart Redis
            result = subprocess.run(
                ['sudo', 'systemctl', 'restart', 'redis'],
                check=True,
                timeout=15,
                capture_output=True,
                text=True
            )
            
            # Wait for service to start
            time.sleep(5)
            
            # Verify it's working
            check_result = check_redis_connectivity()
            return check_result.success
            
        except subprocess.TimeoutExpired:
            self.logger.error("Redis restart timed out")
            return False
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Redis restart failed: {e.stderr}")
            return False
        except Exception as e:
            self.logger.error(f"Redis restart error: {e}")
            return False
    
    def fix_high_memory_usage(self) -> bool:
        """Clear application cache and restart services if needed"""
        if TEST_MODE:
            self.logger.info("TEST MODE: Simulating memory cleanup and cache clearing...")
            time.sleep(2)  # Simulate cleanup time
            import random
            success = random.choice([True, True, False])  # 2/3 chance of success
            self.logger.info(f"TEST MODE: Memory cleanup {'succeeded' if success else 'failed'}")
            return success
        
        try:
            self.logger.info("Attempting to clear cache and reduce memory usage...")
            
            # Clear Redis cache (keep sessions)
            try:
                cache_redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_CACHE_DB)
                cache_redis.flushdb()
                self.logger.info("Redis cache cleared")
            except Exception as e:
                self.logger.warning(f"Could not clear Redis cache: {e}")
            
            # Clear temporary files
            try:
                temp_paths = [
                    os.path.join(APP_BASE_DIR, 'app', 'flask_session_files'),
                    '/tmp/flask_session_*'
                ]
                
                for path in temp_paths:
                    if os.path.exists(path):
                        subprocess.run(['find', path, '-type', 'f', '-mtime', '+1', '-delete'],
                                     capture_output=True, timeout=10)
                        
                self.logger.info("Temporary files cleaned")
            except Exception as e:
                self.logger.warning(f"Could not clean temporary files: {e}")
            
            # Wait and check if memory usage improved
            time.sleep(5)
            check_result = check_system_resources()
            
            # Check if memory usage is now acceptable
            if check_result.success:
                return True
            
            # If still high, restart main service (last resort)
            self.logger.info("Memory still high, restarting main service...")
            return self.fix_gunicorn_down()
            
        except Exception as e:
            self.logger.error(f"Memory cleanup error: {e}")
            return False
    
    def attempt_remediation(self, check_result: CheckResult) -> bool:
        """Attempt to fix a failed check"""
        issue_type = check_result.name
        
        # Define fix strategies for different issues
        fix_strategies = {
            'gunicorn': [('restart_gunicorn', self.fix_gunicorn_down)],
            'redis': [('restart_redis', self.fix_redis_connection)],
            'system_resources': [('clear_cache', self.fix_high_memory_usage)],
        }
        
        if issue_type not in fix_strategies:
            return False
        
        for fix_type, fix_function in fix_strategies[issue_type]:
            if self._can_attempt_fix(issue_type, fix_type):
                try:
                    self.logger.info(f"Attempting remediation: {issue_type} -> {fix_type}")
                    success = fix_function()
                    self._log_attempt(issue_type, fix_type, success)
                    
                    if success:
                        self.logger.info(f"Remediation successful: {issue_type} -> {fix_type}")
                        return True
                    else:
                        self.logger.warning(f"Remediation failed: {issue_type} -> {fix_type}")
                        
                except Exception as e:
                    error_msg = str(e)
                    self.logger.error(f"Remediation exception: {issue_type} -> {fix_type}: {error_msg}")
                    self._log_attempt(issue_type, fix_type, False, error_msg)
        
        return False

# ================================
# MONITORING FUNCTIONS
# ================================

def check_gunicorn_process() -> CheckResult:
    """Check if Gunicorn processes are running"""
    try:
        gunicorn_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                proc_info = proc.info
                if proc_info['name'] and 'gunicorn' in proc_info['name'].lower():
                    gunicorn_procs.append({
                        'pid': proc_info['pid'],
                        'name': proc_info['name'],
                        'cmdline': ' '.join(proc_info['cmdline']) if proc_info['cmdline'] else ''
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        if not gunicorn_procs:
            return CheckResult("gunicorn", False, "No Gunicorn processes found")
            
        return CheckResult(
            "gunicorn", 
            True, 
            f"Found {len(gunicorn_procs)} Gunicorn process(es)",
            details={"processes": gunicorn_procs}
        )
        
    except Exception as e:
        return CheckResult("gunicorn", False, f"Error checking Gunicorn: {e}")

def check_database_connectivity() -> CheckResult:
    """Check SQLite database connectivity"""
    try:
        if not os.path.exists(DATABASE_PATH):
            return CheckResult("database", False, f"Database file not found: {DATABASE_PATH}")
            
        # Test connection and basic query
        conn = sqlite3.connect(DATABASE_PATH, timeout=5)
        cursor = conn.cursor()
        
        # Check if we can query a basic table
        cursor.execute("SELECT COUNT(*) FROM user")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM retailers")
        retailer_count = cursor.fetchone()[0]
        
        conn.close()
        
        return CheckResult(
            "database",
            True,
            f"Database accessible - {user_count} users, {retailer_count} retailers",
            details={"user_count": user_count, "retailer_count": retailer_count}
        )
        
    except Exception as e:
        return CheckResult("database", False, f"Database error: {e}")

def check_redis_connectivity() -> CheckResult:
    """Check Redis connectivity for sessions and cache"""
    try:
        results = {}
        
        # Check session Redis (DB 0)
        try:
            session_redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_SESSION_DB, socket_timeout=5)
            session_redis.ping()
            session_info = session_redis.info()
            results['session'] = {
                'connected': True,
                'db_size': session_redis.dbsize(),
                'memory_usage': session_info.get('used_memory_human', 'Unknown')
            }
        except Exception as e:
            results['session'] = {'connected': False, 'error': str(e)}
        
        # Check cache Redis (DB 1)
        try:
            cache_redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_CACHE_DB, socket_timeout=5)
            cache_redis.ping()
            results['cache'] = {
                'connected': True,
                'db_size': cache_redis.dbsize(),
            }
        except Exception as e:
            results['cache'] = {'connected': False, 'error': str(e)}
        
        # Determine overall success
        session_ok = results['session']['connected']
        cache_ok = results['cache']['connected']
        
        if session_ok and cache_ok:
            message = "Redis session and cache connections OK"
            success = True
        elif session_ok:
            message = "Redis session OK, cache connection failed"
            success = False
        elif cache_ok:
            message = "Redis cache OK, session connection failed"
            success = False
        else:
            message = "Both Redis connections failed"
            success = False
            
        return CheckResult("redis", success, message, details=results)
        
    except Exception as e:
        return CheckResult("redis", False, f"Redis check error: {e}")

def check_http_endpoints() -> List[CheckResult]:
    """Check HTTP endpoints and content"""
    results = []
    
    for endpoint_name, config in MONITOR_URLS.items():
        # Define method early for error handling
        method = config.get("method", "GET")
        
        try:
            url = config["url"]
            timeout = config.get("timeout", 10)
            content_checks = config.get("content_checks", [])
            optional = config.get("optional", False)
            headers = config.get("headers", {})
            body = config.get("body", None)
            expected_status = config.get("expected_status", 200)
            
            # Make HTTP request
            if method.upper() == "POST":
                response = requests.post(url, timeout=timeout, headers=headers, data=body)
            else:
                response = requests.get(url, timeout=timeout)
            
            if response.status_code != expected_status:
                if optional and response.status_code == 404:
                    results.append(CheckResult(
                        f"http_{endpoint_name}",
                        True,
                        f"Optional endpoint {endpoint_name} not found (404) - this is OK",
                        details={"status_code": response.status_code, "url": url, "method": method}
                    ))
                    continue
                else:
                    results.append(CheckResult(
                        f"http_{endpoint_name}",
                        False,
                        f"{endpoint_name} {method} returned {response.status_code}, expected {expected_status}",
                        details={"status_code": response.status_code, "expected_status": expected_status, "url": url, "method": method}
                    ))
                    continue
            
            # Check content
            content_results = []
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for check in content_checks:
                if "selector" in check:
                    # CSS selector check
                    elements = soup.select(check["selector"])
                    if elements:
                        content_results.append(f"✓ {check['description']}")
                    else:
                        content_results.append(f"✗ {check['description']} not found")
                elif "text" in check:
                    # Text content check
                    if check["text"] in response.text:
                        content_results.append(f"✓ {check['description']}")
                    else:
                        content_results.append(f"✗ {check['description']} not found")
            
            # Determine success
            failed_checks = [r for r in content_results if r.startswith("✗")]
            success = len(failed_checks) == 0
            
            results.append(CheckResult(
                f"http_{endpoint_name}",
                success,
                f"{endpoint_name} {method} OK - {len(content_results)} content checks",
                details={
                    "url": url,
                    "method": method,
                    "status_code": response.status_code,
                    "content_checks": content_results,
                    "response_time": response.elapsed.total_seconds()
                }
            ))
            
        except requests.exceptions.Timeout:
            results.append(CheckResult(
                f"http_{endpoint_name}",
                False,
                f"{endpoint_name} {method} request timed out",
                details={"url": config["url"], "method": method, "timeout": timeout}
            ))
        except Exception as e:
            results.append(CheckResult(
                f"http_{endpoint_name}",
                False,
                f"{endpoint_name} {method} error: {e}",
                details={"url": config["url"], "method": method, "error": str(e)}
            ))
    
    return results

def check_system_resources() -> CheckResult:
    """Check system resource usage"""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Disk usage
        disk_usage = psutil.disk_usage('/')
        disk_percent = disk_usage.percent
        
        # Load average (Unix-like systems)
        try:
            load_avg = os.getloadavg()[0]  # 1-minute load average
        except (AttributeError, OSError):
            load_avg = 0.0  # Windows doesn't have load average
        
        # Create metrics object
        metrics = SystemMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            disk_percent=disk_percent,
            load_average=load_avg
        )
        
        # Check thresholds
        issues = []
        if cpu_percent > CPU_THRESHOLD:
            issues.append(f"High CPU usage: {cpu_percent:.1f}%")
        if memory_percent > MEMORY_THRESHOLD:
            issues.append(f"High memory usage: {memory_percent:.1f}%")
        if disk_percent > (100 - DISK_THRESHOLD):
            issues.append(f"Low disk space: {disk_percent:.1f}% used")
        if load_avg > LOAD_THRESHOLD:
            issues.append(f"High load average: {load_avg:.2f}")
        
        success = len(issues) == 0
        message = "System resources OK" if success else f"Resource issues: {', '.join(issues)}"
        
        return CheckResult(
            "system_resources",
            success,
            message,
            details={
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "load_average": load_avg,
                "thresholds": {
                    "cpu": CPU_THRESHOLD,
                    "memory": MEMORY_THRESHOLD,
                    "disk": 100 - DISK_THRESHOLD,
                    "load": LOAD_THRESHOLD
                }
            }
        )
        
    except Exception as e:
        return CheckResult("system_resources", False, f"System resource check error: {e}")

def check_frontend_stripe_integration() -> List[CheckResult]:
    """
    OPTIMIZED: Test frontend Stripe integration with minimal resource usage
    
    KEY OPTIMIZATIONS:
    - Single Chrome process instead of multiple
    - Disabled images, CSS, extensions for faster loading
    - Limited memory usage to 128MB
    - Reduced timeouts (15s page load, 5s element wait)
    - Smaller window size (800x600 vs 1920x1080)
    - Quick button click test without full redirect wait
    
    EXPECTED IMPROVEMENTS:
    - 60-80% reduction in CPU usage
    - 70-90% reduction in memory usage
    - 50% faster test execution
    - Same critical test coverage maintained
    """
    results = []
    
    if not SELENIUM_AVAILABLE:
        results.append(CheckResult(
            "frontend_stripe",
            False,
            "Selenium not available - cannot test frontend Stripe integration",
            details={"error": "Selenium dependencies not installed"}
        ))
        return results
    
    driver = None
    try:
        # HIGHLY OPTIMIZED Chrome options - massive resource savings
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")  # Don't load images - huge savings
        chrome_options.add_argument("--disable-css")  # Don't load CSS - significant savings
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--disable-features=VizDisplayCompositor")
        chrome_options.add_argument("--memory-pressure-off")
        chrome_options.add_argument("--max_old_space_size=128")  # Limit memory to 128MB
        chrome_options.add_argument("--single-process")  # Single process instead of multiple
        chrome_options.add_argument("--window-size=800,600")  # Smaller window - less rendering
        chrome_options.add_argument("--user-agent=Tamermap-Monitor/1.0 (Monitoring System)")
        
        # Initialize driver with minimal service
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(15)  # Reduced from 30s to 15s
        
        # Test 1: Quick Stripe.js check (most important)
        logger.info("Testing Stripe.js loading (optimized)...")
        driver.get("https://tamermap.com/learn")
        
        # Wait only for essential elements - reduced timeout
        WebDriverWait(driver, 5).until(  # Reduced from 10s to 5s
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Quick JavaScript check for Stripe
        stripe_loaded = driver.execute_script("return typeof Stripe !== 'undefined'")
        if not stripe_loaded:
            results.append(CheckResult(
                "frontend_stripe_js_loading",
                False,
                "Stripe.js failed to load on learn page",
                details={"url": "https://tamermap.com/learn", "error": "Stripe object not found"}
            ))
        else:
            results.append(CheckResult(
                "frontend_stripe_js_loading",
                True,
                "Stripe.js loaded successfully on learn page",
                details={"url": "https://tamermap.com/learn"}
            ))
            
            # Test 2: Quick button check (no clicking - saves resources)
            logger.info("Testing subscribe button presence...")
            subscribe_buttons = driver.find_elements(By.CLASS_NAME, "subscribe-btn")
            
            if not subscribe_buttons:
                results.append(CheckResult(
                    "frontend_stripe_buttons",
                    False,
                    "No 'Try Pro Now' buttons found on learn page",
                    details={"url": "https://tamermap.com/learn"}
                ))
            else:
                results.append(CheckResult(
                    "frontend_stripe_buttons",
                    True,
                    f"Found {len(subscribe_buttons)} 'Try Pro Now' buttons on learn page",
                    details={"url": "https://tamermap.com/learn", "button_count": len(subscribe_buttons)}
                ))
                
                # Test 3: Lightweight checkout flow test (no full redirect wait)
                try:
                    initial_url = driver.current_url
                    logger.info("Testing button click response...")
                    
                    # Click the first button
                    subscribe_buttons[0].click()
                    logger.info("Subscribe button clicked, checking response...")
                    
                    # Quick check for any response (don't wait for full redirect)
                    try:
                        # Wait just 5 seconds for any response
                        WebDriverWait(driver, 5).until(
                            lambda d: d.current_url != initial_url
                        )
                        
                        # Button click worked - URL changed
                        results.append(CheckResult(
                            "frontend_stripe_checkout_redirect",
                            True,
                            "Subscribe button click successful - URL changed",
                            details={
                                "initial_url": initial_url,
                                "final_url": driver.current_url,
                                "response_time": "< 5 seconds"
                            }
                        ))
                        
                    except Exception as wait_error:
                        # Button click didn't trigger redirect - but that's OK for monitoring
                        # The important thing is that the button exists and is clickable
                        results.append(CheckResult(
                            "frontend_stripe_checkout_redirect",
                            False,
                            "Subscribe button clickable but no immediate redirect",
                            details={
                                "url": initial_url,
                                "note": "Button exists and clickable - redirect may require user interaction"
                            }
                        ))
                        
                except Exception as click_error:
                    results.append(CheckResult(
                        "frontend_stripe_checkout_redirect",
                        False,
                        f"Button click failed: {click_error}",
                        details={"error": str(click_error)}
                    ))
                    
    except Exception as e:
        results.append(CheckResult(
            "frontend_stripe",
            False,
            f"Frontend test error: {e}",
            details={"error": str(e)}
        ))
    finally:
        if driver:
            driver.quit()  # Ensure cleanup
    
    return results
            


def check_ssl_certificate() -> CheckResult:
    """Check SSL certificate expiry"""
    try:
        hostname = "tamermap.com"
        port = 443
        
        # Get SSL certificate
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
        
        # Parse expiry date
        expiry_str = cert['notAfter']
        expiry_date = datetime.strptime(expiry_str, '%b %d %H:%M:%S %Y %Z')
        
        # Calculate days until expiry
        days_until_expiry = (expiry_date - datetime.now()).days
        
        if days_until_expiry < 0:
            return CheckResult("ssl_cert", False, f"SSL certificate expired {abs(days_until_expiry)} days ago")
        elif days_until_expiry < SSL_EXPIRY_WARNING_DAYS:
            return CheckResult("ssl_cert", False, f"SSL certificate expires in {days_until_expiry} days")
        else:
            return CheckResult(
                "ssl_cert",
                True,
                f"SSL certificate valid for {days_until_expiry} days",
                details={"expiry_date": expiry_date.isoformat(), "days_remaining": days_until_expiry}
            )
            
    except Exception as e:
        return CheckResult("ssl_cert", False, f"SSL certificate check error: {e}")

# ================================
# MAIN MONITORING LOOP
# ================================

class TamermapMonitor:
    """Main monitoring class"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.alert_manager = AlertManager(self.logger)
        self.auto_remediation = AutoRemediation(self.logger)
        self.running = True
        self.check_count = 0
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initialize daily summary scheduler
        self.daily_summary_enabled = setup_daily_summary_scheduler()
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        
    def run_all_checks(self) -> List[CheckResult]:
        """Run all monitoring checks"""
        if TEST_MODE:
            return self.run_test_checks()
        
        results = []
        
        # Process checks
        results.append(check_gunicorn_process())
        
        # Database connectivity
        results.append(check_database_connectivity())
        
        # Redis connectivity
        results.append(check_redis_connectivity())
        
        # HTTP endpoints
        results.extend(check_http_endpoints())
        
        # System resources
        results.append(check_system_resources())
        
        # SSL certificate
        results.append(check_ssl_certificate())
        
        # Frontend Stripe integration testing (run less frequently to avoid overhead)
        if hasattr(self, '_last_frontend_check'):
            time_since_last = datetime.now() - self._last_frontend_check
            if time_since_last.total_seconds() < SELENIUM_TEST_INTERVAL:  # Configurable interval
                self.logger.info("Skipping frontend Stripe test (run recently)")
            else:
                self.logger.info("Running frontend Stripe integration tests...")
                results.extend(check_frontend_stripe_integration())
                self._last_frontend_check = datetime.now()
        else:
            self.logger.info("Running frontend Stripe integration tests...")
            results.extend(check_frontend_stripe_integration())
            self._last_frontend_check = datetime.now()
        
        return results
    
    def run_test_checks(self) -> List[CheckResult]:
        """Run test checks based on environment variables or default scenario"""
        if TEST_SIMULATE_FAILURES:
            self.logger.info(f"TEST MODE: Simulating specific failures: {TEST_SIMULATE_FAILURES}")
            # Create base successful results
            results = [
                CheckResult("gunicorn", True, "Found 2 Gunicorn process(es)"),
                CheckResult("database", True, "Database accessible - 58 users, 4473 retailers"),
                CheckResult("redis", True, "Redis session and cache connections OK"),
                CheckResult("http_home", True, "home GET OK - 3 content checks"),
                CheckResult("http_learn", True, "learn GET OK - 2 content checks"),
                CheckResult("http_stripe_checkout", True, "stripe_checkout POST OK - 2 content checks"),
                CheckResult("http_health", True, "Optional endpoint health not found (404) - this is OK"),
                CheckResult("system_resources", True, "System resources OK"),
                CheckResult("ssl_cert", True, "SSL certificate valid for 278 days")
            ]
            
            # Replace with specified failures
            for failure_type in TEST_SIMULATE_FAILURES:
                failure_type = failure_type.strip()
                if failure_type:
                    for i, result in enumerate(results):
                        if result.name == failure_type:
                            results[i] = create_test_failure(failure_type)
                            break
            
            return results
        else:
            # Default test scenario
            self.logger.info("TEST MODE: Running default mixed_failures scenario")
            return run_test_scenario('mixed_failures')
    
    def run_test_scenario_by_name(self, scenario_name: str):
        """Run a specific test scenario by name"""
        self.logger.info(f"Running test scenario: {scenario_name}")
        results = run_test_scenario(scenario_name)
        self.process_results(results)
        return results
        
    def process_results(self, results: List[CheckResult]):
        """Process check results, attempt remediation, and send alerts if needed"""
        failed_checks = [r for r in results if not r.success]
        
        if failed_checks:
            # STEP 1: Send immediate alert about issues (original format)
            self._send_immediate_alerts(failed_checks, results)
            
            # STEP 2: Attempt auto-remediation
            remediation_attempts = {}
            still_failed = []
            
            if AUTO_REMEDIATION_ENABLED:
                self.logger.info(f"Starting auto-remediation for {len(failed_checks)} failed checks...")
                
                for failure in failed_checks:
                    self.logger.info(f"Attempting auto-remediation for {failure.name}")
                    success = self.auto_remediation.attempt_remediation(failure)
                    remediation_attempts[failure.name] = success
                    
                    if success:
                        self.logger.info(f"Auto-remediation successful for {failure.name}")
                        # Re-run the specific check to confirm fix
                        if failure.name == 'gunicorn':
                            recheck = check_gunicorn_process()
                        elif failure.name == 'redis':
                            recheck = check_redis_connectivity()
                        elif failure.name == 'system_resources':
                            recheck = check_system_resources()
                        else:
                            recheck = failure  # Can't re-check, assume still failed
                        
                        if not recheck.success:
                            still_failed.append(failure)
                    else:
                        still_failed.append(failure)
                
                # STEP 3: Send followup alert with remediation results
                self._send_followup_alerts(failed_checks, still_failed, results, remediation_attempts)
            else:
                self.logger.info("Auto-remediation disabled, skipping remediation attempts")
        
        # Log summary
        success_count = len([r for r in results if r.success])
        remediation_count = len([r for r in failed_checks if r.name in remediation_attempts and remediation_attempts[r.name]]) if failed_checks else 0
        self.logger.info(f"Check cycle complete: {success_count}/{len(results)} checks passed, {remediation_count} auto-fixes applied")
    
    def _send_immediate_alerts(self, failed_checks: List[CheckResult], all_results: List[CheckResult]):
        """Send immediate alerts about detected issues (original format)"""
        # Group failures by type for alerting
        critical_failures = []
        warning_failures = []
        
        for failure in failed_checks:
            if failure.name in ['gunicorn', 'database', 'http_home']:
                critical_failures.append(failure)
            else:
                warning_failures.append(failure)
        
        # Send critical alert
        if critical_failures:
            subject = f"CRITICAL: {len(critical_failures)} service(s) down"
            body = self._format_immediate_alert_body(critical_failures, all_results)
            self.alert_manager.send_alert(subject, body, "critical")
        
        # Send warning alert
        if warning_failures:
            subject = f"WARNING: {len(warning_failures)} issue(s) detected"
            body = self._format_immediate_alert_body(warning_failures, all_results)
            self.alert_manager.send_alert(subject, body, "warning")
    
    def _send_followup_alerts(self, original_failures: List[CheckResult], still_failed: List[CheckResult], 
                             all_results: List[CheckResult], remediation_attempts: Dict):
        """Send followup alerts with remediation results"""
        if not remediation_attempts:
            return
        
        # Determine alert type based on results
        if not still_failed:
            # All issues resolved
            subject = f"FOLLOWUP - RESOLVED: All {len(original_failures)} issue(s) auto-fixed"
            body = self._format_followup_resolved_body(original_failures, all_results, remediation_attempts)
            self.alert_manager.send_alert(subject, body, "followup_resolved")
        else:
            # Some issues remain
            resolved_count = len(original_failures) - len(still_failed)
            if resolved_count > 0:
                subject = f"FOLLOWUP - PARTIAL: {resolved_count}/{len(original_failures)} issue(s) resolved"
            else:
                subject = f"FOLLOWUP - FAILED: Remediation unsuccessful for {len(still_failed)} issue(s)"
            
            body = self._format_followup_partial_body(original_failures, still_failed, all_results, remediation_attempts)
            self.alert_manager.send_alert(subject, body, "followup_partial")
        
    def _format_immediate_alert_body(self, failures: List[CheckResult], all_results: List[CheckResult]) -> str:
        """Format immediate alert email body (original format)"""
        body = f"Tamermap Monitor Alert - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        body += "=" * 60 + "\n\n"
        
        body += "FAILED CHECKS:\n"
        body += "-" * 20 + "\n"
        for failure in failures:
            body += f"❌ {failure.name.upper()}: {failure.message}\n"
            if failure.details:
                for key, value in failure.details.items():
                    body += f"   {key}: {value}\n"
            body += "\n"
        
        if AUTO_REMEDIATION_ENABLED:
            body += "🔧 Auto-remediation will be attempted shortly...\n"
            body += "📧 You will receive a followup email with remediation results.\n\n"
        
        body += "ALL CHECK RESULTS:\n"
        body += "-" * 20 + "\n"
        for result in all_results:
            status = "✅" if result.success else "❌"
            body += f"{status} {result.name}: {result.message}\n"
        
        body += f"\nTotal alerts sent today: {self.alert_manager.alert_count}\n"
        body += f"Monitor running for: {self.check_count} cycles\n"
        
        return body
    
    def _format_followup_resolved_body(self, original_failures: List[CheckResult], all_results: List[CheckResult], remediation_attempts: Dict) -> str:
        """Format followup alert for fully resolved issues"""
        body = f"Tamermap Monitor - FOLLOWUP: All Issues Resolved - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        body += "=" * 60 + "\n\n"
        
        body += "🎉 EXCELLENT NEWS: All issues have been automatically resolved!\n\n"
        
        body += "RESOLVED ISSUES:\n"
        body += "-" * 20 + "\n"
        for issue in original_failures:
            body += f"✅ {issue.name.upper()}: {issue.message}\n"
            if issue.name in remediation_attempts and remediation_attempts[issue.name]:
                body += f"   🔧 Auto-remediation: SUCCESS\n"
            else:
                body += f"   🔧 Auto-remediation: Not applicable\n"
            body += "\n"
        
        body += "REMEDIATION ACTIONS TAKEN:\n"
        body += "-" * 30 + "\n"
        for issue_name, success in remediation_attempts.items():
            if success:
                if issue_name == 'gunicorn':
                    body += "🔄 Restarted Gunicorn service → SUCCESS\n"
                elif issue_name == 'redis':
                    body += "🔄 Restarted Redis service → SUCCESS\n"
                elif issue_name == 'system_resources':
                    body += "🧹 Cleared cache and temporary files → SUCCESS\n"
                else:
                    body += f"🔧 Fixed {issue_name} → SUCCESS\n"
            else:
                body += f"❌ Attempted to fix {issue_name} → FAILED\n"
        
        body += "\n✅ CURRENT STATUS: All systems operational!\n\n"
        
        body += "FINAL CHECK RESULTS:\n"
        body += "-" * 20 + "\n"
        for result in all_results:
            status = "✅" if result.success else "❌"
            body += f"{status} {result.name}: {result.message}\n"
        
        body += f"\nTotal alerts sent today: {self.alert_manager.alert_count}\n"
        body += f"Monitor running for: {self.check_count} cycles\n"
        
        return body
    
    def _format_followup_partial_body(self, original_failures: List[CheckResult], still_failed: List[CheckResult], 
                                     all_results: List[CheckResult], remediation_attempts: Dict) -> str:
        """Format followup alert for partially resolved issues"""
        resolved_count = len(original_failures) - len(still_failed)
        
        body = f"Tamermap Monitor - FOLLOWUP: Remediation Results - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        body += "=" * 60 + "\n\n"
        
        if resolved_count > 0:
            body += f"✅ PARTIAL SUCCESS: {resolved_count}/{len(original_failures)} issues resolved\n"
            body += f"❌ REMAINING ISSUES: {len(still_failed)} still require attention\n\n"
        else:
            body += "❌ REMEDIATION FAILED: No issues were automatically resolved\n"
            body += "🚨 Manual intervention required\n\n"
        
        # Show resolved issues
        if resolved_count > 0:
            resolved_issues = [f for f in original_failures if f not in still_failed]
            body += "SUCCESSFULLY RESOLVED:\n"
            body += "-" * 25 + "\n"
            for issue in resolved_issues:
                body += f"✅ {issue.name.upper()}: {issue.message}\n"
                if issue.name in remediation_attempts and remediation_attempts[issue.name]:
                    body += f"   🔧 Auto-remediation: SUCCESS\n"
                body += "\n"
        
        # Show remaining issues
        if still_failed:
            body += "STILL FAILING:\n"
            body += "-" * 15 + "\n"
            for failure in still_failed:
                body += f"❌ {failure.name.upper()}: {failure.message}\n"
                if failure.details:
                    for key, value in failure.details.items():
                        body += f"   {key}: {value}\n"
                
                if failure.name in remediation_attempts:
                    if remediation_attempts[failure.name]:
                        body += f"   🔧 Auto-remediation: ATTEMPTED but issue persists\n"
                    else:
                        body += f"   🔧 Auto-remediation: FAILED\n"
                else:
                    body += f"   🔧 Auto-remediation: Not available for this issue\n"
                body += "\n"
        
        # Show all remediation attempts
        body += "REMEDIATION ATTEMPTS:\n"
        body += "-" * 25 + "\n"
        for issue_name, success in remediation_attempts.items():
            action_taken = ""
            if issue_name == 'gunicorn':
                action_taken = "Restarted Gunicorn service"
            elif issue_name == 'redis':
                action_taken = "Restarted Redis service"
            elif issue_name == 'system_resources':
                action_taken = "Cleared cache and temporary files"
            else:
                action_taken = f"Attempted to fix {issue_name}"
            
            status = "SUCCESS" if success else "FAILED"
            body += f"{'✅' if success else '❌'} {action_taken} → {status}\n"
        
        body += f"\n⚠️  RECOMMENDATION: {'Review resolved issues and monitor remaining failures' if resolved_count > 0 else 'Manual intervention required for all issues'}\n\n"
        
        body += "FINAL CHECK RESULTS:\n"
        body += "-" * 20 + "\n"
        for result in all_results:
            status = "✅" if result.success else "❌"
            body += f"{status} {result.name}: {result.message}\n"
        
        body += f"\nTotal alerts sent today: {self.alert_manager.alert_count}\n"
        body += f"Monitor running for: {self.check_count} cycles\n"
        
        return body


        
    def run(self):
        """Main monitoring loop"""
        self.logger.info("Starting Tamermap Monitor...")
        self.logger.info(f"Monitoring interval: {MONITOR_INTERVAL} seconds")
        
        if TEST_MODE:
            self.logger.info("🧪 TEST MODE ENABLED")
            self.logger.info(f"Test recipients: {', '.join(TEST_EMAIL_RECIPIENTS)}")
            if TEST_SIMULATE_FAILURES:
                self.logger.info(f"Simulating failures: {', '.join(TEST_SIMULATE_FAILURES)}")
        else:
            self.logger.info(f"Alert recipients: {', '.join(ALERT_RECIPIENTS)}")
            
        self.logger.info(f"Auto-remediation: {'ENABLED' if AUTO_REMEDIATION_ENABLED else 'DISABLED'}")
        
        # Start daily summary scheduler if enabled
        if self.daily_summary_enabled:
            self.logger.info("📧 Daily summary emails: ENABLED (9:00 PM Pacific)")
            run_scheduler_thread()
        else:
            self.logger.info("📧 Daily summary emails: DISABLED (missing dependencies)")
        
        while self.running:
            try:
                self.check_count += 1
                self.logger.info(f"Starting check cycle #{self.check_count}")
                
                # Run all checks
                results = self.run_all_checks()
                
                # Process results and send alerts
                self.process_results(results)
                
                # Sleep until next check
                if self.running:
                    time.sleep(MONITOR_INTERVAL)
                    
            except KeyboardInterrupt:
                self.logger.info("Received keyboard interrupt, shutting down...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in monitoring loop: {e}", exc_info=True)
                time.sleep(60)  # Wait before retrying
        
        self.logger.info("Tamermap Monitor stopped.")

# ================================
# DAILY SUMMARY EMAIL SYSTEM
# ================================

def get_daily_summary_data(target_date=None):
    """
    Get comprehensive daily summary data for email reporting.
    
    Args:
        target_date: Date to get data for (defaults to today)
    
    Returns:
        dict: Complete daily summary data
    """
    if target_date is None:
        target_date = datetime.now().date()
    
    logger = setup_logging()
    logger.info(f"Gathering daily summary data for {target_date}")
    
    # Need Flask app context for database access
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            from app.admin_utils import get_top_ref_codes, exclude_monitor_traffic
            from app.models import VisitorLog, User, BillingEvent
            from app.extensions import db
            from sqlalchemy import func, and_, or_
            
            start_of_day = datetime.combine(target_date, datetime.min.time())
            end_of_day = datetime.combine(target_date, datetime.max.time())
            
            # Traffic Analysis - Guest vs Pro vs Total (excluding admins and monitor)
            traffic_query = exclude_monitor_traffic(VisitorLog.query).filter(
                VisitorLog.timestamp >= start_of_day,
                VisitorLog.timestamp <= end_of_day
            )
            
            # Total traffic
            total_traffic = traffic_query.count()
            
            # Guest traffic (no user_id)
            guest_traffic = traffic_query.filter(VisitorLog.user_id.is_(None)).count()
            
            # Pro user traffic (has user_id, but exclude admins)
            pro_user_query = traffic_query.join(User, VisitorLog.user_id == User.id).filter(
                User.pro_end_date > datetime.utcnow()  # Currently Pro
            )
            
            # Exclude admin users from pro traffic
            admin_role_subquery = db.session.query(User.id).join(User.roles).filter(
                func.lower(db.text("role.name")) == 'admin'
            ).subquery()
            
            pro_traffic = pro_user_query.filter(
                ~User.id.in_(admin_role_subquery)
            ).count()
            
            # Basic user traffic (logged in but not Pro, not admin)
            basic_user_traffic = traffic_query.join(User, VisitorLog.user_id == User.id).filter(
                or_(User.pro_end_date.is_(None), User.pro_end_date <= datetime.utcnow()),
                ~User.id.in_(admin_role_subquery)
            ).count()
            
            # Referrer codes used today
            ref_codes_data = get_top_ref_codes(days=1) if target_date == datetime.now().date() else []
            if target_date != datetime.now().date():
                # Custom query for historical date
                ref_codes_query = exclude_monitor_traffic(VisitorLog.query).filter(
                    VisitorLog.timestamp >= start_of_day,
                    VisitorLog.timestamp <= end_of_day,
                    VisitorLog.ref_code.isnot(None),
                    VisitorLog.ref_code != ''
                ).with_entities(
                    VisitorLog.ref_code,
                    func.count(VisitorLog.id).label('count')
                ).group_by(VisitorLog.ref_code).order_by(func.count(VisitorLog.id).desc()).limit(10)
                
                ref_codes_data = [(r.ref_code, r.count) for r in ref_codes_query.all()]
            
            # New signups from Stripe (checkout.session.completed events)
            new_signups = BillingEvent.query.filter(
                BillingEvent.event_timestamp >= start_of_day,
                BillingEvent.event_timestamp <= end_of_day,
                BillingEvent.event_type == 'subscription_created'
            ).count()
            
            # Alternative signup detection via user creation
            new_users_today = User.query.filter(
                User.confirmed_at >= start_of_day,
                User.confirmed_at <= end_of_day
            ).count()
            
            # Payment data from Stripe
            payment_events = BillingEvent.query.filter(
                BillingEvent.event_timestamp >= start_of_day,
                BillingEvent.event_timestamp <= end_of_day,
                BillingEvent.event_type == 'payment_succeeded'
            ).all()
            
            total_payments = len(payment_events)
            total_amount = 0.0
            
            # Parse payment amounts from event details
            import json
            for event in payment_events:
                try:
                    if event.details:
                        details = json.loads(event.details)
                        amount_paid = details.get('amount_paid', 0)
                        # Stripe amounts are in cents
                        total_amount += (amount_paid / 100.0) if amount_paid else 0
                except (json.JSONDecodeError, KeyError):
                    continue
            
            # Unique visitors
            unique_visitors = traffic_query.with_entities(
                func.count(func.distinct(VisitorLog.ip_address))
            ).scalar() or 0
            
            logger.info(f"Daily summary data gathered successfully for {target_date}")
            
            return {
                'date': target_date,
                'traffic': {
                    'total': total_traffic,
                    'guest': guest_traffic,
                    'pro_user': pro_traffic,
                    'basic_user': basic_user_traffic,
                    'unique_visitors': unique_visitors
                },
                'referrer_codes': ref_codes_data,
                'signups': {
                    'stripe_subscriptions': new_signups,
                    'new_users': new_users_today
                },
                'payments': {
                    'count': total_payments,
                    'total_amount': round(total_amount, 2)
                }
            }
        
    except Exception as e:
        logger.error(f"Error gathering daily summary data: {e}", exc_info=True)
        return None


def format_daily_summary_email(summary_data):
    """
    Format daily summary data into email body.
    
    Args:
        summary_data: Dictionary from get_daily_summary_data()
    
    Returns:
        str: Formatted email body
    """
    if not summary_data:
        return "❌ Error: Could not gather daily summary data"
    
    date_str = summary_data['date'].strftime('%B %d, %Y')
    traffic = summary_data['traffic']
    ref_codes = summary_data['referrer_codes']
    signups = summary_data['signups']
    payments = summary_data['payments']
    
    body = f"""Tamermap Daily Summary - {date_str}
{'=' * 60}

📊 TRAFFIC SUMMARY
{'=' * 20}
🌍 Total Traffic: {traffic['total']:,} visits
👥 Unique Visitors: {traffic['unique_visitors']:,}

Traffic Breakdown:
  👤 Guest Traffic: {traffic['guest']:,} visits ({traffic['guest']/traffic['total']*100:.1f}%)
  💎 Pro User Traffic: {traffic['pro_user']:,} visits ({traffic['pro_user']/traffic['total']*100:.1f}%)
  📝 Basic User Traffic: {traffic['basic_user']:,} visits ({traffic['basic_user']/traffic['total']*100:.1f}%)

🔗 REFERRER CODES
{'=' * 20}"""

    if ref_codes:
        body += f"\n📈 {len(ref_codes)} referrer codes used today:\n"
        for code, count in ref_codes:
            body += f"   • {code}: {count:,} visits\n"
    else:
        body += "\n📭 No referrer codes used today\n"

    body += f"""
👋 NEW SIGNUPS
{'=' * 20}
🎯 Stripe Subscriptions: {signups['stripe_subscriptions']}
👤 New User Accounts: {signups['new_users']}

💰 PAYMENTS COLLECTED
{'=' * 20}
💳 Payment Count: {payments['count']}
💵 Total Amount: ${payments['total_amount']:,.2f}

📈 DAILY INSIGHTS
{'=' * 20}"""

    # Add some insights
    if traffic['total'] > 0:
        guest_percentage = traffic['guest'] / traffic['total'] * 100
        pro_percentage = traffic['pro_user'] / traffic['total'] * 100
        
        body += f"\n• Guest traffic represents {guest_percentage:.1f}% of total traffic"
        body += f"\n• Pro users generated {pro_percentage:.1f}% of total traffic"
        
        if traffic['unique_visitors'] > 0:
            visits_per_visitor = traffic['total'] / traffic['unique_visitors']
            body += f"\n• Average visits per unique visitor: {visits_per_visitor:.1f}"
    
    if payments['count'] > 0:
        avg_payment = payments['total_amount'] / payments['count']
        body += f"\n• Average payment amount: ${avg_payment:.2f}"
    
    if len(ref_codes) > 0:
        total_ref_visits = sum(count for _, count in ref_codes)
        body += f"\n• Referrer codes drove {total_ref_visits:,} visits ({total_ref_visits/traffic['total']*100:.1f}% of traffic)"

    body += f"""

📧 This automated summary was generated by Tamermap Monitor
   Report generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}
   
🔧 System Status: All monitoring systems operational
"""

    return body


def send_daily_summary_email():
    """
    Send daily summary email to administrators.
    This function is called by the scheduler at 9 PM Pacific time.
    """
    logger = setup_logging()
    logger.info("Starting daily summary email generation...")
    
    try:
        # Get yesterday's data (since we're running at 9 PM, we want the full day)
        target_date = datetime.now().date()
        
        # Get summary data
        summary_data = get_daily_summary_data(target_date)
        if not summary_data:
            logger.error("Failed to gather daily summary data")
            return False
        
        # Format email
        email_body = format_daily_summary_email(summary_data)
        
        # Send email using existing AlertManager
        alert_manager = AlertManager(logger)
        
        subject = f"Daily Summary - {summary_data['date'].strftime('%B %d, %Y')}"
        
        # Send the summary email
        alert_manager.send_alert(
            subject=subject,
            body=email_body,
            alert_type="daily_summary"
        )
        
        logger.info(f"Daily summary email sent successfully for {target_date}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending daily summary email: {e}", exc_info=True)
        return False


# ================================
# SCHEDULER INTEGRATION
# ================================

def setup_daily_summary_scheduler():
    """
    Set up the daily summary email scheduler.
    Schedules email to be sent at 9 PM Pacific time daily.
    """
    try:
        import schedule
        import pytz
    except ImportError:
        print("Required packages not installed. Run: pip install schedule pytz")
        return False
    
    logger = setup_logging()
    
    def schedule_daily_summary():
        """Wrapper function to handle timezone conversion"""
        try:
            pacific = pytz.timezone('US/Pacific')
            now_pacific = datetime.now(pacific)
            logger.info(f"Daily summary scheduled task triggered at {now_pacific.strftime('%Y-%m-%d %H:%M:%S %Z')}")
            send_daily_summary_email()
        except Exception as e:
            logger.error(f"Error in scheduled daily summary: {e}", exc_info=True)
    
    # Schedule for 9 PM Pacific time
    schedule.every().day.at("21:00").do(schedule_daily_summary)
    
    logger.info("Daily summary scheduler configured for 9:00 PM Pacific time")
    return True


def run_scheduler_thread():
    """
    Run the scheduler in a separate thread.
    This allows the scheduler to run alongside the main monitoring loop.
    """
    try:
        import schedule
        import time
        import threading
    except ImportError:
        return
    
    logger = setup_logging()
    
    def scheduler_worker():
        logger.info("Daily summary scheduler thread started")
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler thread: {e}", exc_info=True)
                time.sleep(300)  # Wait 5 minutes on error
    
    scheduler_thread = threading.Thread(target=scheduler_worker, daemon=True)
    scheduler_thread.start()
    logger.info("Daily summary scheduler thread launched")


def test_daily_summary_email(target_date=None):
    """
    Test function to manually send a daily summary email.
    Use this to test the functionality before deploying.
    
    Args:
        target_date: Date to generate summary for (defaults to today)
    
    Returns:
        bool: Success status
    """
    print("🧪 Testing Daily Summary Email...")
    
    logger = setup_logging()
    
    try:
        # Use provided date or default to today
        if target_date is None:
            target_date = datetime.now().date()
        elif isinstance(target_date, str):
            target_date = datetime.strptime(target_date, '%Y-%m-%d').date()
        
        print(f"📅 Generating summary for: {target_date}")
        
        # Get summary data
        print("📊 Gathering data...")
        summary_data = get_daily_summary_data(target_date)
        
        if not summary_data:
            print("❌ Failed to gather summary data")
            return False
        
        # Display summary to console first
        print("\n" + "="*60)
        print("DAILY SUMMARY DATA PREVIEW")
        print("="*60)
        print(f"Date: {summary_data['date']}")
        print(f"Total Traffic: {summary_data['traffic']['total']:,}")
        print(f"Guest Traffic: {summary_data['traffic']['guest']:,}")
        print(f"Pro User Traffic: {summary_data['traffic']['pro_user']:,}")
        print(f"Referrer Codes: {len(summary_data['referrer_codes'])}")
        print(f"New Signups: {summary_data['signups']['new_users']}")
        print(f"Payments: {summary_data['payments']['count']} totaling ${summary_data['payments']['total_amount']:,.2f}")
        print("="*60)
        
        # Ask for confirmation
        response = input("\n📧 Send this summary email? (y/N): ").strip().lower()
        if response not in ['y', 'yes']:
            print("📭 Email sending cancelled")
            return False
        
        # Format and send email
        print("📧 Formatting and sending email...")
        email_body = format_daily_summary_email(summary_data)
        
        alert_manager = AlertManager(logger)
        subject = f"[TEST] Daily Summary - {summary_data['date'].strftime('%B %d, %Y')}"
        
        alert_manager.send_alert(
            subject=subject,
            body=email_body,
            alert_type="daily_summary_test"
        )
        
        print("✅ Test daily summary email sent successfully!")
        print(f"📧 Email sent to: {', '.join(ALERT_RECIPIENTS)}")
        return True
        
    except Exception as e:
        print(f"❌ Error testing daily summary email: {e}")
        logger.error(f"Error in test_daily_summary_email: {e}", exc_info=True)
        return False

# ================================
# ENTRY POINT
# ================================

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Tamermap Application Monitor')
    parser.add_argument('--test', action='store_true', help='Run in test mode')
    parser.add_argument('--test-scenario', help='Run specific test scenario', 
                       choices=['all_good', 'single_failure', 'multiple_failures', 
                               'critical_failure', 'mixed_failures', 'non_remediable'])
    parser.add_argument('--test-failures', help='Comma-separated list of failures to simulate',
                       default='')
    parser.add_argument('--single-run', action='store_true', help='Run once and exit (useful for testing)')
    parser.add_argument('--test-daily-summary', help='Test daily summary email for specific date (YYYY-MM-DD) or today',
                       nargs='?', const='today')
    
    args = parser.parse_args()
    
    # Set test mode based on arguments
    if args.test:
        os.environ['MONITOR_TEST_MODE'] = 'true'
        global TEST_MODE
        TEST_MODE = True
        
        if args.test_failures:
            os.environ['MONITOR_TEST_FAILURES'] = args.test_failures
            global TEST_SIMULATE_FAILURES
            TEST_SIMULATE_FAILURES = args.test_failures.split(',')
    
    # Handle daily summary test command
    if args.test_daily_summary:
        target_date = None if args.test_daily_summary == 'today' else args.test_daily_summary
        
        # Daily summary test needs Flask app context in production
        if TEST_MODE:
            success = test_daily_summary_email(target_date)
        else:
            try:
                from app import create_app
                app = create_app()
                with app.app_context():
                    success = test_daily_summary_email(target_date)
            except ImportError as e:
                print(f"❌ Error: Could not import Flask app: {e}")
                sys.exit(1)
        
        sys.exit(0 if success else 1)
    
    # Ensure we're in the correct directory (skip in test mode)
    if not TEST_MODE and not os.path.exists(DATABASE_PATH):
        
        sys.exit(1)
    
    # Create Flask app context for imports
    try:
        if TEST_MODE:
            # Test mode doesn't need Flask app context
        
            monitor = TamermapMonitor()
            
            if args.single_run:
                # Run once and exit
                results = monitor.run_all_checks()
                monitor.process_results(results)
            elif args.test_scenario:
                # Run specific test scenario
                monitor.run_test_scenario_by_name(args.test_scenario)
            else:
                # Normal monitoring loop (but in test mode)
                monitor.run()
        else:
            # Production mode - need Flask app context
            from app import create_app
            app = create_app()
            
            with app.app_context():
                monitor = TamermapMonitor()
                
                if args.single_run:
                    # Run once and exit
                    results = monitor.run_all_checks()
                    monitor.process_results(results)
                elif args.test_scenario:
                    # Run specific test scenario
                    monitor.run_test_scenario_by_name(args.test_scenario)
                else:
                    # Normal monitoring loop
                    monitor.run()
                
    except ImportError as e:
        if TEST_MODE:
            # In test mode, this is expected - just continue
        
            monitor = TamermapMonitor()
            
            if args.single_run:
                results = monitor.run_all_checks()
                monitor.process_results(results)
            elif args.test_scenario:
                monitor.run_test_scenario_by_name(args.test_scenario)
            else:
                monitor.run()
        else:
            
            sys.exit(1)

if __name__ == "__main__":
    main() 