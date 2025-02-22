#!/bin/bash

# Set variables
ZIP_URL="https://github.com/george-ka/teleg/archive/refs/heads/main.zip"
DOWNLOAD_PATH="/tmp/teleg.zip"
EXTRACT_PATH="/opt/teleg_service"  # Service directory
SERVICE_NAME="teleg_service"  # Systemd service name
PYTHON_SCRIPT="bot.py"
LOG_FILE="/var/log/$SERVICE_NAME.log"
VENV_PATH="$EXTRACT_PATH/venv"  # Virtual environment path
ENV_FILE="$EXTRACT_PATH/.env"
AUTH_USERS_FILE="$EXTRACT_PATH/authorized_users.json"
CHECK_SERVICE_SCRIPT="./check_service_running.sh"  # Path to the check_service_running.sh script

# Ask for API keys
echo "Enter your OpenAI API Key:"
read -s OPENAI_API_KEY  # Read input silently

echo "Enter your Telegram Bot Token:"
read -s TELEGRAM_BOT_TOKEN  # Read input silently

# Ask if user wants to skip venv installation
read -p "Do you want to skip virtual environment reinstallation? (y/n): " SKIP_VENV_INSTALL

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

# Skip virtual environment creation if the user opts to
if [ "$SKIP_VENV_INSTALL" != "y" ]; then
    # Create a virtual environment if it doesn't exist
    if [ ! -d "$VENV_PATH" ]; then
        echo "Creating virtual environment..."
        python3 -m venv "$VENV_PATH"
    else
        echo "✅ Virtual environment already exists, skipping reinstallation."
    fi
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

# Store environment variables in .env file
echo "Saving API keys..."
cat > "$ENV_FILE" <<EOL
OPENAI_API_KEY=$OPENAI_API_KEY
TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN
EOL
chmod 600 "$ENV_FILE"  # Restrict access to the file

# Create authorized_users.json if it doesn't exist
if [ ! -f "$AUTH_USERS_FILE" ]; then
    echo "Creating authorized_users.json..."
    echo "[]" > "$AUTH_USERS_FILE"
    chmod 600 "$AUTH_USERS_FILE"  # Restrict access to the file
fi

# Stop the running Python script
echo "Stopping existing Python script..."
pkill -f "$PYTHON_SCRIPT"

# Ensure log file exists and is writable
sudo touch "$LOG_FILE"
sudo chmod 666 "$LOG_FILE"

# Run the service check script
echo "Running service check script..."
$CHECK_SERVICE_SCRIPT

# Clean up
rm "$DOWNLOAD_PATH"
rm -rf /tmp/temp_extract

echo "✅ Installation complete!"
echo "🔹 Your API keys have been saved in $ENV_FILE"
echo "🔹 To add authorized users, edit $AUTH_USERS_FILE"
