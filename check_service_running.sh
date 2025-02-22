#!/bin/bash

# Load environment variables from the .env file
export $(grep -v '^#' /opt/teleg_service/.env | xargs)

# Variables
SERVICE_NAME="bot.py"  # Change this to your script name
SCRIPT_PATH="/opt/teleg_service/$SERVICE_NAME"
VENV_PATH="/opt/teleg_service/venv"
LOG_FILE="/var/log/teleg_service.log"

# Check if the service is running
if pgrep -f "$SERVICE_NAME" > /dev/null
then
    echo "✅ $SERVICE_NAME is running."
else
    echo "❌ $SERVICE_NAME is NOT running. Restarting..."
    
    # Restart the Python script with the virtual environment
    nohup "$VENV_PATH/bin/python3" "$SCRIPT_PATH" > "$LOG_FILE" 2>&1 &
    
    echo "✅ $SERVICE_NAME restarted!"
fi