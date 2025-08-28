#!/bin/bash

# Define paths
APP_DIR="/home/tamermap/app"
STATIC_DIR="$APP_DIR/static"
LOG_DIR="/home/tamermap/var/logs"
INSTANCE_DIR="/home/tamermap/var/instance"
CONFIG_DIR="/home/tamermap/config"
ENV_PATTERN="/home/tamermap/config/.env*"

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

# 5. External directories: accessible to tamermap
echo "Setting external directory permissions..."
sudo mkdir -p "$LOG_DIR"
sudo mkdir -p "$INSTANCE_DIR"
sudo mkdir -p "$CONFIG_DIR"
sudo chown -R tamermap:tamermap "$LOG_DIR"
sudo chown -R tamermap:tamermap "$INSTANCE_DIR"
sudo chown -R tamermap:tamermap "$CONFIG_DIR"
sudo chmod -R 750 "$LOG_DIR"
sudo chmod -R 750 "$INSTANCE_DIR"
sudo chmod -R 750 "$CONFIG_DIR"

# 7. SQLite DB files: read/write for tamermap only
echo "Securing database files..."
sudo find "$INSTANCE_DIR" -type f -name "*.db" -exec chmod 600 {} \;
sudo find "$INSTANCE_DIR" -type f -name "*.sqlite" -exec chmod 600 {} \;

# 8. Symlinks: ensure they point to correct locations
echo "Verifying symlinks..."
if [ -L "$APP_DIR/.env" ]; then
    echo "✓ .env symlink exists"
else
    echo "⚠️  .env symlink missing - create with: sudo ln -s $CONFIG_DIR/.env $APP_DIR/.env"
fi

if [ -L "$APP_DIR/instance" ]; then
    echo "✓ instance symlink exists"
else
    echo "⚠️  instance symlink missing - create with: sudo ln -s $INSTANCE_DIR $APP_DIR/instance"
fi

if [ -L "$APP_DIR/logs" ]; then
    echo "✓ logs symlink exists"
else
    echo "⚠️  logs symlink missing - create with: sudo ln -s $LOG_DIR $APP_DIR/logs"
fi

# 9. Environment files: readable by tamermap
echo "Setting .env file permissions..."
for env_file in $ENV_PATTERN; do
    if [ -f "$env_file" ]; then
        sudo chown tamermap:tamermap "$env_file"
        sudo chmod 600 "$env_file"
        echo "Permissions set for: $env_file"
    fi
done

# Check if any .env files were found
if ! ls $ENV_PATTERN 1> /dev/null 2>&1; then
    echo "WARNING: No .env files found in $CONFIG_DIR"
fi

echo "All permissions updated successfully."
