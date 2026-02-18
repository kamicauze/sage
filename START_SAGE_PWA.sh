#!/bin/bash
# Quick start script for Sage PWA with real-time brain monitoring

echo "🧠 Starting Sage PWA System..."
echo ""

# Check if running in correct directory
if [ ! -f "mosquitto.conf" ]; then
    echo "❌ Error: Run this script from /home/kamicauze/sage directory"
    exit 1
fi

# Start Mosquitto
echo "1️⃣ Starting Mosquitto MQTT Broker..."
pkill mosquitto 2>/dev/null
mosquitto -c mosquitto.conf -d
sleep 1

if ! pgrep mosquitto > /dev/null; then
    echo "❌ Failed to start Mosquitto"
    exit 1
fi
echo "✅ Mosquitto running (ports 1883 + 9001)"

# Check if Python brain is running
echo ""
echo "2️⃣ Checking Brain status..."
if pgrep -f "brain/main.py" > /dev/null; then
    echo "✅ Brain already running"
else
    echo "⚠️ Brain not running"
    echo "   Start manually: python brain/main.py"
fi

# Start Next.js PWA
echo ""
echo "3️⃣ Starting PWA..."
cd architect/ui

if [ ! -f ".env.local" ]; then
    echo "Creating .env.local from example..."
    cp .env.local.example .env.local
fi

echo "Starting Next.js on port 3000..."
npm run dev:network &

sleep 3
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🎉 Sage PWA is ready!"
echo ""
echo "Access Points:"
echo "  Desktop:  http://localhost:3000/brain"
echo "  Network:  http://$(hostname -I | awk '{print $1}'):3000/brain"
echo ""
echo "Services:"
echo "  Mosquitto: ✅ Running (1883 + 9001)"
echo "  Next.js:   ✅ Running (3000)"
echo "  Brain:     Check manually"
echo ""
echo "To stop:"
echo "  Ctrl+C (stops Next.js)"
echo "  pkill mosquitto (stops broker)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

wait
