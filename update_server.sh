#!/bin/bash
# update_server.sh - Pull latest code and restart Tamermap service.

# Exit immediately if a command exits with a non-zero status
set -e

# Define project directory and systemd service name
PROJECT_DIR="/home/tamermap/app"
SERVICE_NAME="tamermap.service"

echo "Navigating to project directory: $PROJECT_DIR"
cd "$PROJECT_DIR" || { echo "Error: Project directory $PROJECT_DIR not found."; exit 1; }

# Check that the virtual environment exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Error: Virtual environment 'venv' not found."
    exit 1
fi

# Pull the latest code
echo "Pulling latest code from Git repository..."
git pull

# Restart the Gunicorn systemd service
echo "Restarting Gunicorn service: $SERVICE_NAME..."
sudo systemctl restart "$SERVICE_NAME"

echo "Update complete."
