#!/bin/bash
# Slomix Discord Bot - Service Installer
# This script installs and enables the systemd service

echo "🤖 Installing Slomix Discord Bot as a systemd service..."

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run as root (use: sudo ./install_service.sh)"
    exit 1
fi

# Copy service file to systemd directory
echo "📋 Copying service file to /etc/systemd/system/..."
cp slomix.service /etc/systemd/system/

# Reload systemd
echo "🔄 Reloading systemd daemon..."
systemctl daemon-reload

# Enable service to start on boot
echo "✅ Enabling service to start on boot..."
systemctl enable slomix.service

# Ask if user wants to start now
read -p "🚀 Start the service now? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    systemctl start slomix.service
    echo ""
    echo "✅ Service started!"
    sleep 2
    systemctl status slomix.service
else
    echo "ℹ️  Service installed but not started. Start it with: sudo systemctl start slomix"
fi

echo ""
echo "📚 Useful commands:"
echo "  Start:   sudo systemctl start slomix"
echo "  Stop:    sudo systemctl stop slomix"
echo "  Restart: sudo systemctl restart slomix"
echo "  Status:  sudo systemctl status slomix"
echo "  Logs:    sudo journalctl -u slomix -f"
echo "  Disable: sudo systemctl disable slomix"
