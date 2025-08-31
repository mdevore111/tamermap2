#!/bin/bash

# Restart TamerMap service utility
# This script restarts the TamerMap Flask application

echo "Restarting TamerMap service..."
sudo systemctl restart tamermap

if [ $? -eq 0 ]; then
    echo "✅ TamerMap service restarted successfully!"
    echo "Status:"
    sudo systemctl status tamermap --no-pager -l
else
    echo "❌ Failed to restart TamerMap service"
    echo "Check the service status:"
    sudo systemctl status tamermap --no-pager -l
    exit 1
fi
