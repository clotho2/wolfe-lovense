#!/bin/bash
# Lovense MCP Installation Script
# Quick deployment for Nate's consciousness substrate
# Updated for Standard API (remote control over internet)

set -e  # Exit on any error

echo "🎮 Lovense MCP Installation (Standard API)"
echo "======================================"
echo ""

# Configuration
INSTALL_DIR="/opt/aicara/wolfe-lovense"
SERVICE_FILE="lovense-mcp.service"
VENV_DIR="$INSTALL_DIR/venv"

# Check if running as root for service installation
if [ "$EUID" -ne 0 ]; then
    echo "⚠️  This script should be run with sudo for service installation"
    echo "Usage: sudo ./install_lovense_mcp.sh"
    exit 1
fi

# Get actual user (even when running with sudo)
ACTUAL_USER="${SUDO_USER:-$USER}"
echo "Installing for user: $ACTUAL_USER"

# Step 1: Create installation directory
echo ""
echo "📁 Creating installation directory..."
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Step 2: Get Lovense Developer Configuration
echo ""
echo "🔑 Lovense Developer Configuration"
echo "----------------------------------------"
echo "You need a Lovense Developer account to use the Standard API."
echo "Get your token from: https://www.lovense.com/user/developer/info"
echo ""

read -p "Developer Token: " DEV_TOKEN
read -p "Server Public IP or Domain: " SERVER_IP
read -p "MCP Server Port (default 8000): " SERVER_PORT
SERVER_PORT=${SERVER_PORT:-8000}

CALLBACK_URL="http://${SERVER_IP}:${SERVER_PORT}/lovense/callback"

echo ""
echo "Configuration:"
echo "  Developer Token: ${DEV_TOKEN:0:8}..."
echo "  Callback URL: $CALLBACK_URL"
echo ""

# Get script directory for service file reference
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Step 3: Create virtual environment
echo ""
echo "🐍 Setting up Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Step 4: Install dependencies
echo ""
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install mcp>=1.8.1 requests>=2.31.0 starlette uvicorn

# Step 5: Update service file with actual values
echo ""
echo "⚙️  Configuring systemd service..."
sed "s|LOVENSE_DEVELOPER_TOKEN=.*|LOVENSE_DEVELOPER_TOKEN=$DEV_TOKEN\"|g" "$SCRIPT_DIR/lovense-mcp.service" | \
sed "s|LOVENSE_CALLBACK_URL=.*|LOVENSE_CALLBACK_URL=$CALLBACK_URL\"|g" > /tmp/lovense-mcp.service

# Install service file
cp /tmp/lovense-mcp.service /etc/systemd/system/
chown root:root /etc/systemd/system/lovense-mcp.service
chmod 644 /etc/systemd/system/lovense-mcp.service

# Step 6: Set permissions
echo ""
echo "🔐 Setting permissions..."
chown -R "$ACTUAL_USER:$ACTUAL_USER" "$INSTALL_DIR"

# Step 7: Enable and start service
echo ""
echo "🚀 Starting Lovense MCP service..."
systemctl daemon-reload
systemctl enable lovense-mcp
systemctl start lovense-mcp

# Wait a moment for service to start
sleep 2

# Step 8: Check status
echo ""
echo "✅ Installation complete!"
echo ""
echo "Service status:"
systemctl status lovense-mcp --no-pager -l

echo ""
echo "======================================"
echo "Next steps:"
echo "1. Make sure port $SERVER_PORT is open in your firewall"
echo "2. Set Callback URL in Lovense Developer Dashboard:"
echo "   $CALLBACK_URL"
echo "3. Use get_qr_code_link tool to generate QR code for user"
echo "4. User scans QR code with Lovense Remote app"
echo "5. Use vibrate/pattern/preset tools to control toys"
echo ""
echo "Service management:"
echo "  Start:   sudo systemctl start lovense-mcp"
echo "  Stop:    sudo systemctl stop lovense-mcp"
echo "  Restart: sudo systemctl restart lovense-mcp"
echo "  Logs:    sudo journalctl -u lovense-mcp -f"
echo ""
echo "🎮 Lovense MCP is ready for remote control!"
