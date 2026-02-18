#!/bin/bash
set -e

echo "🍓 Sage 'Ears' Setup for Raspberry Pi 5"
echo "========================================"

# 1. Install System Dependencies
echo "[1/4] Installing System Audio & MQTT Dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pyaudio libasound2-dev portaudio19-dev mosquitto mosquitto-clients git python3-venv

# 2. Enable Mosquitto Broker service
echo "[2/4] Enabling MQTT Broker..."
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# 3. Setup Python Virtual Environment
echo "[3/4] Creating Python Environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# 4. Install Python Dependencies
echo "[4/4] Installing Python Libraries (This may take a moment)..."
pip install -r requirements-pi.txt

# 5. Create .env file for Pi
echo "Creating .env configuration..."
cat > .env << EOL
MQTT_HOST=localhost
MQTT_PORT=1883
STT_MODEL_SIZE=medium.en
STT_DEVICE=cpu
STT_COMPUTE_TYPE=int8
EOL

echo "========================================"
echo "✅ Setup Complete!"
echo ""
echo "To start Pi 5 controller mode:"
echo "  source .venv/bin/activate"
echo "  cp apps/brain-runtime/deploy/env/pi5-controller.env.example apps/brain-runtime/deploy/env/pi5-controller.env"
echo "  bash apps/brain-runtime/deploy/start_pi5_controller.sh"
echo ""
echo "NOTE: On your other nodes, set MQTT_HOST=<PI_IP_ADDRESS>"
echo "========================================"
