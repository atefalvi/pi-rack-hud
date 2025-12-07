#!/bin/bash
set -e

INSTALL_PATH="/home/$USER/pi-rack-hud"
SERVICE_NAME="pi-rack-hud.service"

cd "$INSTALL_PATH"

echo ">>> Pulling latest changes from GitHub..."
git pull

echo ">>> Restarting service..."
sudo systemctl restart "$SERVICE_NAME"

echo ">>> Update complete."
