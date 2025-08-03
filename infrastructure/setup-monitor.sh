#!/bin/bash

# Tamermap Monitor Setup Script
# This script installs and configures the Tamermap application monitor

set -e

echo "🔧 Setting up Tamermap Monitor..."

# Configuration
SERVICE_NAME="tamermap-monitor"
APP_DIR="/home/tamermap/app"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
MONITOR_USER="tamermap"
MONITOR_GROUP="tamermap"

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script must be run as root (use sudo)"
    exit 1
fi

# Check if app directory exists
if [ ! -d "$APP_DIR" ]; then
    echo "❌ Application directory $APP_DIR not found"
    echo "Please adjust APP_DIR in this script to match your installation"
    exit 1
fi

# Check if user exists
if ! id "$MONITOR_USER" &>/dev/null; then
    echo "❌ User $MONITOR_USER not found"
    echo "Please create the user or adjust MONITOR_USER in this script"
    exit 1
fi

echo "📦 Installing monitor dependencies..."

# Install Python dependencies
cd "$APP_DIR"
if [ -f "venv/bin/activate" ]; then
    echo "Using virtual environment..."
    source venv/bin/activate
    pip install -r requirements.txt
else
    echo "Installing globally..."
    pip3 install -r requirements.txt
fi

echo "📁 Creating necessary directories..."

# Create logs directory if it doesn't exist
mkdir -p "$APP_DIR/logs"
chown "$MONITOR_USER:$MONITOR_GROUP" "$APP_DIR/logs"

# Create instance directory if it doesn't exist
mkdir -p "$APP_DIR/instance"
chown "$MONITOR_USER:$MONITOR_GROUP" "$APP_DIR/instance"

echo "🔐 Setting up permissions..."

# Make monitor.py executable
chmod +x "$APP_DIR/monitor.py"
chown "$MONITOR_USER:$MONITOR_GROUP" "$APP_DIR/monitor.py"

echo "⚙️ Installing systemd service..."

# Copy service file
cp "$APP_DIR/tamermap-monitor.service" "$SERVICE_FILE"

# Reload systemd
systemctl daemon-reload

# Enable service (but don't start yet)
systemctl enable "$SERVICE_NAME"

echo "🔍 Performing pre-flight checks..."

# Check if Redis is running
if systemctl is-active --quiet redis; then
    echo "✅ Redis is running"
else
    echo "⚠️  Redis is not running. Starting Redis..."
    systemctl start redis
    systemctl enable redis
fi

# Check if database exists
if [ -f "$APP_DIR/instance/tamermap_data.db" ]; then
    echo "✅ Database found"
else
    echo "⚠️  Database not found at $APP_DIR/instance/tamermap_data.db"
    echo "Please ensure your database is properly set up"
fi

# Test monitor (dry run)
echo "🧪 Testing monitor configuration..."
cd "$APP_DIR"
if [ -f "venv/bin/activate" ]; then
    echo "Testing with virtual environment..."
    sudo -u "$MONITOR_USER" bash -c "
    cd $APP_DIR
    source venv/bin/activate
    python -c \"
import sys
sys.path.insert(0, 'app')
try:
    from monitor import TamermapMonitor
    print('✅ Monitor imports successfully')
except Exception as e:
    print(f'❌ Monitor import failed: {e}')
    sys.exit(1)
\""
else
    echo "Testing with system Python..."
    sudo -u "$MONITOR_USER" python3 -c "
import sys
sys.path.insert(0, 'app')
try:
    from monitor import TamermapMonitor
    print('✅ Monitor imports successfully')
except Exception as e:
    print(f'❌ Monitor import failed: {e}')
    sys.exit(1)
"
fi

echo "🚀 Setup complete! To start the monitor:"
echo
echo "  # Start the service"
echo "  sudo systemctl start $SERVICE_NAME"
echo
echo "  # Check service status"
echo "  sudo systemctl status $SERVICE_NAME"
echo
echo "  # View logs"
echo "  sudo journalctl -u $SERVICE_NAME -f"
echo
echo "  # View monitor logs"
echo "  tail -f $APP_DIR/logs/monitor.log"
echo
echo "📧 Monitor will send alerts to: mark@markdevore.com"
echo "📊 Monitor interval: 5 minutes"
echo "🔧 To customize settings, edit: $APP_DIR/monitor.py"
echo
echo "⚠️  Important: Make sure your .env file contains the Mailgun credentials:"
echo "   MAILGUN_API_KEY=your-api-key"
echo "   MAILGUN_DOMAIN=your-domain"
echo
echo "🎉 Ready to monitor your Tamermap application!" 