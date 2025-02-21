#!/bin/bash

# Set variables
ZIP_URL="https://github.com/george-ka/teleg/archive/refs/heads/main.zip"
DOWNLOAD_PATH="/tmp/teleg.zip"
EXTRACT_PATH="/opt/teleg_service"  # Service directory
SERVICE_NAME="teleg_service" 
PYTHON_SCRIPT="bot.py"
LOG_FILE="/var/log/$SERVICE_NAME.log"
VENV_PATH="$EXTRACT_PATH/venv"  # Virtual environment path

# Download the ZIP file
echo "Downloading update..."
curl -L -o "$DOWNLOAD_PATH" "$ZIP_URL"

# Ensure download was successful
if [ $? -ne 0 ]; then
    echo "❌ Download failed!"
    exit 1
fi

# Extract to a temporary directory, then move files
echo "Extracting files..."
sudo rm -rf /tmp/temp_extract
sudo rm -rf "$EXTRACT_PATH"

unzip -o "$DOWNLOAD_PATH" -d /tmp/temp_extract
sudo mv /tmp/temp_extract/* "$EXTRACT_PATH"

# Ensure the script is executable
chmod +x "$EXTRACT_PATH/$PYTHON_SCRIPT"

# Create a virtual environment if it doesn't exist
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
fi

# Activate the virtual environment and install dependencies
echo "Installing dependencies..."
source "$VENV_PATH/bin/activate"
pip install --upgrade pip
if [ -f "$EXTRACT_PATH/requirements.txt" ]; then
    pip install -r "$EXTRACT_PATH/requirements.txt"
else
    echo "⚠️ Warning: No requirements.txt found, skipping dependency installation."
fi
deactivate  # Exit virtual environment

# Stop the running Python script
echo "Stopping existing Python script..."
pkill -f "$PYTHON_SCRIPT"

# Ensure log file exists and has correct permissions
sudo touch "$LOG_FILE"
sudo chmod 666 "$LOG_FILE"

# Restart the Python script using the virtual environment
echo "Starting Python script..."
nohup "$VENV_PATH/bin/python3" "$EXTRACT_PATH/$PYTHON_SCRIPT" > "$LOG_FILE" 2>&1 &

# Clean up
rm "$DOWNLOAD_PATH"
rm -rf /tmp/temp_extract

echo "✅ Update complete!"
exit 0