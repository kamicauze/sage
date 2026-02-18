#!/bin/bash
# Fix Mosquitto port conflict
# Run this script to stop the system Mosquitto service

echo "🔧 Fixing Mosquitto Port Conflict..."
echo ""

# Check if system mosquitto is running
if systemctl is-active --quiet mosquitto; then
    echo "Found system Mosquitto service running on default ports."
    echo "This conflicts with Sage's custom configuration."
    echo ""
    echo "Stopping system Mosquitto..."
    sudo systemctl stop mosquitto

    echo "Disabling system Mosquitto from auto-starting..."
    sudo systemctl disable mosquitto

    echo ""
    echo "✅ System Mosquitto stopped and disabled."
    echo ""
    echo "Now you can run: ./sage pwa"
else
    echo "System Mosquitto is not running."

    # Check if mosquitto process exists
    if pgrep -f "mosquitto.*etc.*mosquitto.conf" > /dev/null; then
        echo "Found mosquitto process running with system config."
        echo "Killing it..."
        sudo pkill -f "mosquitto.*etc.*mosquitto.conf"
        echo "✅ Process killed."
    else
        echo "No conflicting Mosquitto found."
    fi
fi

echo ""
echo "Testing if ports are free..."
if netstat -tuln | grep -q ":1883 "; then
    echo "⚠️  Port 1883 still in use!"
    echo "Check what's using it:"
    echo "  sudo netstat -tulnp | grep 1883"
else
    echo "✅ Port 1883 is free"
fi

if netstat -tuln | grep -q ":9001 "; then
    echo "⚠️  Port 9001 still in use!"
    echo "Check what's using it:"
    echo "  sudo netstat -tulnp | grep 9001"
else
    echo "✅ Port 9001 is free"
fi

echo ""
echo "Ready to start Sage PWA!"
echo "Run: ./sage pwa"
