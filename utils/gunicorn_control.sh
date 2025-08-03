#!/bin/bash

# Name of the systemd service for Gunicorn (adjust if necessary)
SERVICE="tamermap.service"

case "$1" in
    start)
        echo "Starting $SERVICE..."
        sudo systemctl start $SERVICE
        ;;
    stop)
        echo "Stopping $SERVICE..."
        sudo systemctl stop $SERVICE
        ;;
    restart)
        echo "Restarting $SERVICE..."
        sudo systemctl restart $SERVICE
        ;;
    status)
        echo "Checking status of $SERVICE..."
        sudo systemctl status $SERVICE
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}"
        ;;
esac
