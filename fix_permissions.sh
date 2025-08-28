#!/bin/bash

# Define paths
APP_DIR="/var/www/tamermap"
STATIC_DIR="$APP_DIR/static"
LOG_DIR="$APP_DIR/logs"
INSTANCE_DIR="$APP_DIR/instance"
ENV_FILE="$APP_DIR/.env"

echo "Fixing ownership and permissions for Tamermap app..."

# 1. Set ownership of the whole app folder to tamermap
echo "Setting ownership..."
sudo chown -R tamermap:tamermap "$APP_DIR"

# 2. Make sure Nginx (www-data) can read static files
echo "Adjusting static file permissions..."
sudo chown -R tamermap:www-data "$STATIC_DIR"
sudo find "$STATIC_DIR" -type d -exec chmod 755 {} \;
sudo find "$STATIC_DIR" -type f -exec chmod 644 {} \;

# 3. Directories: readable/traversable
echo "Fixing directory permissions..."
sudo find "$APP_DIR" -type d -exec chmod 750 {} \;

# 4. Python and shell scripts: executable
echo "Making Python and shell scripts executable..."
sudo find "$APP_DIR" -type f \( -iname "*.py" -o -iname "*.sh" \) -exec chmod 750 {} \;

# 5. Logs: private to tamermap
echo "Securing logs..."
sudo mkdir -p "$LOG_DIR"
sudo chown -R tamermap:tamermap "$LOG_DIR"
sudo chmod -R 750 "$LOG_DIR"

# 6. Instance directory: accessible to tamermap
echo "Setting instance directory permissions..."
sudo mkdir -p "$INSTANCE_DIR"
sudo chown -R tamermap:tamermap "$INSTANCE_DIR"
sudo chmod -R 750 "$INSTANCE_DIR"

# 7. SQLite DB files: read/write for tamermap only
echo "Securing database files..."
sudo find "$APP_DIR" -type f -name "*.db" -exec chmod 600 {} \;
sudo find "$APP_DIR" -type f -name "*.sqlite" -exec chmod 600 {} \;

# 8. Environment file: readable by tamermap
echo "Setting .env file permissions..."
if [ -f "$ENV_FILE" ]; then
    sudo chown tamermap:tamermap "$ENV_FILE"
    sudo chmod 600 "$ENV_FILE"
    echo ".env file permissions set"
else
    echo "WARNING: .env file not found at $ENV_FILE"
fi

echo "All permissions updated successfully."
