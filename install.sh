#!/bin/bash
set -e

REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/pi-rack-hud.git"
INSTALL_PATH="/home/$USER/pi-rack-hud"
SERVICE_NAME="pi-rack-hud.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

echo ">>> Installing Pi Rack HUD for user: $USER"

# Clone or update repo
if [ ! -d "$INSTALL_PATH" ]; then
    echo ">>> Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_PATH"
else
    echo ">>> Repository exists, pulling latest..."
    cd "$INSTALL_PATH"
    git pull
fi

echo ">>> Installing Python dependencies..."
pip3 install -r "$INSTALL_PATH/requirements.txt"

echo ">>> Creating systemd service from template..."
SERVICE_TEMPLATE="$INSTALL_PATH/hud.service.template"

sed \
  -e "s#__USERNAME__#$USER#g" \
  -e "s#__INSTALL_PATH__#$INSTALL_PATH#g" \
  "$SERVICE_TEMPLATE" | sudo tee "$SERVICE_FILE" > /dev/null

echo ">>> Reloading systemd..."
sudo systemctl daemon-reload

echo ">>> Enabling service..."
sudo systemctl enable "$SERVICE_NAME"

echo ">>> Starting/restarting service..."
sudo systemctl restart "$SERVICE_NAME"

echo ">>> Installation complete. Service status:"
sudo systemctl status "$SERVICE_NAME" --no-pager
