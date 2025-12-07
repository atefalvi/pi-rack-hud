#!/bin/bash
set -e

echo "==============================================="
echo ">>> Pi Rack HUD Installer"
echo ">>> User: $USER"
echo "==============================================="

# --------------------------------------------------
# Install Nerd Font (0xProto Nerd Font Mono)
# --------------------------------------------------
echo ">>> Installing Nerd Font (0xProto Nerd Font Mono)..."

FONT_DIR="/home/$USER/.fonts"
mkdir -p "$FONT_DIR"

cd /tmp
wget -q https://github.com/ryanoasis/nerd-fonts/releases/latest/download/0xProto.zip -O 0xProto.zip
unzip -o 0xProto.zip "*.ttf" -d "$FONT_DIR" > /dev/null

echo ">>> Updating font cache..."
fc-cache -f -v > /dev/null

echo ">>> Nerd Font installed successfully."
echo

# --------------------------------------------------
# Clone or Update GitHub Repository
# --------------------------------------------------
REPO_URL="https://github.com/atefalvi/pi-rack-hud.git"
INSTALL_PATH="/home/$USER/pi-rack-hud"
SERVICE_NAME="pi-rack-hud.service"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME"

echo ">>> Installing Pi Rack HUD for user: $USER"

if [ ! -d "$INSTALL_PATH" ]; then
    echo ">>> Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_PATH"
else
    echo ">>> Repository exists. Pulling latest updates..."
    cd "$INSTALL_PATH"
    git pull
fi
echo

# --------------------------------------------------
# Install Python Dependencies
# --------------------------------------------------
echo ">>> Installing Python dependencies..."
pip3 install --break-system-packages -r "$INSTALL_PATH/requirements.txt"
echo

# --------------------------------------------------
# Create systemd Service
# --------------------------------------------------
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

echo ">>> Starting service..."
sudo systemctl restart "$SERVICE_NAME"
echo

# --------------------------------------------------
# Final Status
# --------------------------------------------------
echo "==============================================="
echo ">>> Installation complete!"
echo ">>> Service status:"
echo "==============================================="
sudo systemctl status "$SERVICE_NAME" --no-pager
