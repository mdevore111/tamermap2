#!/bin/bash

# ─── Setup ────────────────────────────────────────────────
PROJECT_DIR="/home/tamermap/app"
VENV_PATH="$PROJECT_DIR/venv"
APP_ENTRY="run:app"
BIND_ADDRESS="127.0.0.1:8000"

# ─── Activate Virtualenv ─────────────────────────────────
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

# ─── Start Gunicorn in Foreground with Real-Time Logs ───
echo ""
echo "Starting Gunicorn with real-time terminal output..."
echo "→ Binding to $BIND_ADDRESS"
echo "→ App entry point: $APP_ENTRY"
echo ""

gunicorn -w 1 \
  -b "$BIND_ADDRESS" \
  "$APP_ENTRY" \
  --log-level debug \
  --access-logfile - \
  --error-logfile -
