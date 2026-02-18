#!/bin/bash
set -e

echo "🚀 Sage Setup for Jetson Orin Nano (STT + TTS)"
echo "================================================="

CONTROLLER_HOST=${1:-"192.168.1.50"}

# 1. Install System Audio & MQTT Dependencies
echo "[1/5] Installing System Audio & MQTT Dependencies..."
sudo apt-get update
sudo apt-get install -y python3-pyaudio libasound2-dev portaudio19-dev mosquitto mosquitto-clients git python3-venv

# 2. (Optional) Enable local Mosquitto broker for standalone mode
echo "[2/5] Preparing optional local MQTT broker..."
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# 3. Setup Python Virtual Environment
echo "[3/5] Creating Python Environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

# 4. Install Python Dependencies
echo "[4/5] Installing Python Libraries..."
pip install -r requirements-pi.txt

# 5. Install Qwen3-TTS
echo "[5/5] Installing Qwen3-TTS..."
pip install qwen-tts

# 6. Create .env file for Jetson (CUDA Enabled)
echo "Creating .env configuration..."
cat > .env << EOL
MQTT_HOST=${CONTROLLER_HOST}
MQTT_PORT=1883

# STT - Use small model with INT8 to fit in 8GB alongside TTS
# Uncomment STT_MODEL_PATH to use fine-tuned Sheng model
STT_MODEL_SIZE=small
STT_DEVICE=cuda
STT_COMPUTE_TYPE=int8_float16
# STT_MODEL_PATH=brain/voice/models/whisper-sheng-ct2
# STT_LANGUAGE=sw

# TTS - Qwen3-TTS (uncomment QWEN_TTS_MODEL after deploying fine-tuned model)
TTS_ENGINE=kokoro
# QWEN_TTS_MODEL=brain/voice/models/qwen3-tts-sheng-0.6b
TTS_PREWARM=false
TTS_IDLE_TIMEOUT=90
EOL

echo "================================================="
echo "✅ Jetson Setup Complete!"
echo "Architecture: GPU (CUDA) Enabled"
echo "Controller Host: ${CONTROLLER_HOST}"
echo ""
echo "VRAM Budget (8GB shared):"
echo "  System:    ~1.5 GB"
echo "  STT:       ~0.7 GB (whisper-small INT8/FP16)"
echo "  TTS:       ~2.5 GB (Qwen3-TTS 0.6B, on-demand)"
echo "  Available: ~3.3 GB headroom"
echo ""
echo "To deploy fine-tuned models:"
echo "  1. On training PC: bash brain/voice/training/export_for_jetson.sh"
echo "  2. scp sage-jetson-models.tar.gz to this Jetson"
echo "  3. tar xzf sage-jetson-models.tar.gz -C ."
echo "  4. Uncomment model paths in .env"
echo ""
echo "To start:"
echo "  source .venv/bin/activate"
echo "  cp apps/brain-runtime/deploy/env/orin-voice.env.example apps/brain-runtime/deploy/env/orin-voice.env"
echo "  # update MQTT_HOST in the env file if needed"
echo "  bash apps/brain-runtime/deploy/start_orin_voice.sh"
echo "================================================="
