# Guide to Update Tamermap Service Configuration

This guide provides instructions to update the systemd service configuration for the Tamermap application after changing the user and path from `/var/www/tamermap` (user: webadmin) to `/home/tamermap/app` (user: tamermap).

## 1. Locate and Edit the Systemd Service File

```bash
# Edit the systemd service file
sudo nano /etc/systemd/system/tamermap.service
```

## 2. Update the Following Fields in the Service File

Look for and update these fields in the service file:

- Update the `User` field from `webadmin` to `tamermap`
- Update all instances of `/var/www/tamermap` to `/home/tamermap/app`
- Ensure the `WorkingDirectory` points to `/home/tamermap/app`
- Check that the `ExecStart` path correctly points to `/home/tamermap/app/venv/bin/gunicorn` (or similar)

Example service file (adjust as needed):

```
[Unit]
Description=Gunicorn instance to serve Tamermap
After=network.target

[Service]
User=tamermap
Group=tamermap
WorkingDirectory=/home/tamermap/app
Environment="PATH=/home/tamermap/app/venv/bin"
ExecStart=/home/tamermap/app/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 run:create_app()
Restart=always

[Install]
WantedBy=multi-user.target
```

## 3. Reload Systemd and Restart the Service

```bash
# Reload systemd to apply changes
sudo systemctl daemon-reload

# Restart the service
sudo systemctl restart tamermap.service

# Check status to verify it's working
sudo systemctl status tamermap.service
```

## 4. Check Permissions and Ownership

Ensure the application directory has the correct ownership:

```bash
# Change ownership of the app directory to the tamermap user
sudo chown -R tamermap:tamermap /home/tamermap/app
```

## 5. Check Nginx Configuration (if applicable)

If you're using Nginx as a reverse proxy, check its configuration:

```bash
# Edit the Nginx site configuration
sudo nano /etc/nginx/sites-available/tamermap

# Look for any references to the old path and update them
# After editing, test the configuration
sudo nginx -t

# Reload Nginx if the test passes
sudo systemctl reload nginx
```

## Troubleshooting

If the service fails to start, check the logs:

```bash
# View service logs
sudo journalctl -u tamermap.service -n 50 --no-pager
```

Common issues:
- Incorrect file permissions
- Missing dependencies
- Python path issues
- Virtual environment not activated correctly 