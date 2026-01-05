#!/bin/bash
# Lovense MCP Installation Script
# Quick deployment for Nate's consciousness substrate

set -e  # Exit on any error

echo "🎮 Lovense MCP Installation"
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

# Step 2: Get Game Mode configuration
echo ""
echo "📡 Lovense Remote Game Mode Configuration"
echo "----------------------------------------"
echo "Please enter your Lovense Remote Game Mode details:"
echo "(Find these in Lovense Remote → Settings → Game Mode)"
echo ""

read -p "Game Mode IP address (e.g., 192.168.1.100): " GAME_IP
read -p "Game Mode HTTPS port (default 30010): " GAME_PORT
GAME_PORT=${GAME_PORT:-30010}

echo ""
echo "Configuration:"
echo "  IP: $GAME_IP"
echo "  Port: $GAME_PORT"
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
pip install mcp>=1.8.1 requests>=2.31.0

# Step 5: Update service file with actual values
echo ""
echo "⚙️  Configuring systemd service..."
sed "s|GAME_MODE_IP=.*|GAME_MODE_IP=$GAME_IP\"|g" "$SCRIPT_DIR/lovense-mcp.service" | \
sed "s|GAME_MODE_PORT=.*|GAME_MODE_PORT=$GAME_PORT\"|g" > /tmp/lovense-mcp.service

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
echo "1. Verify service is running: sudo systemctl status lovense-mcp"
echo "2. View logs: sudo journalctl -u lovense-mcp -f"
echo "3. Test connectivity: python $INSTALL_DIR/test_lovense.py"
echo "4. Integrate with substrate (see LOVENSE_INTEGRATION_GUIDE.md)"
echo ""
echo "Service management:"
echo "  Start:   sudo systemctl start lovense-mcp"
echo "  Stop:    sudo systemctl stop lovense-mcp"
echo "  Restart: sudo systemctl restart lovense-mcp"
echo "  Status:  sudo systemctl status lovense-mcp"
echo ""
echo "🎮 Lovense MCP is ready for Nate's consciousness!"
