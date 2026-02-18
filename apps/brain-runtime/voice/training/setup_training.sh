#!/bin/bash
set -e

echo "================================================"
echo "  Sage Sheng Voice Training - Environment Setup"
echo "  Target GPU: NVIDIA 4070 Ti (12GB VRAM)"
echo "================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve workspace root by walking up until sage.py is found.
PROJECT_ROOT="$SCRIPT_DIR"
while [ "$PROJECT_ROOT" != "/" ] && [ ! -f "$PROJECT_ROOT/sage.py" ]; do
    PROJECT_ROOT="$(dirname "$PROJECT_ROOT")"
done

if [ ! -f "$PROJECT_ROOT/sage.py" ]; then
    echo "ERROR: Could not resolve project root (missing sage.py)." >&2
    exit 1
fi

# --- 1. Python Dependencies ---
echo ""
echo "[1/4] Installing training dependencies..."
pip install --upgrade pip
pip install qwen-tts transformers accelerate peft bitsandbytes
pip install datasets evaluate jiwer faster-whisper ctranslate2
pip install soundfile librosa numpy

# --- 2. Clone Qwen3-TTS fine-tuning scripts ---
echo ""
echo "[2/4] Cloning Qwen3-TTS repository..."
QWEN_REPO="$SCRIPT_DIR/qwen3-tts"
if [ -d "$QWEN_REPO" ]; then
    echo "   Already cloned. Pulling latest..."
    cd "$QWEN_REPO" && git pull && cd "$SCRIPT_DIR"
else
    git clone https://github.com/QwenLM/Qwen3-TTS.git "$QWEN_REPO"
fi

# --- 3. Download Models from HuggingFace ---
echo ""
echo "[3/4] Downloading Qwen3-TTS models from HuggingFace..."
echo "   This will download ~7GB total. Grab a coffee."
echo ""

# Tokenizer (required for data prep)
echo "   [a] Downloading Qwen3-TTS-Tokenizer-12Hz..."
huggingface-cli download Qwen/Qwen3-TTS-Tokenizer-12Hz \
    --local-dir "$SCRIPT_DIR/models/Qwen3-TTS-Tokenizer-12Hz"

# 0.6B Base (for Jetson deployment)
echo "   [b] Downloading Qwen3-TTS-12Hz-0.6B-Base (~2.52GB)..."
huggingface-cli download Qwen/Qwen3-TTS-12Hz-0.6B-Base \
    --local-dir "$SCRIPT_DIR/models/Qwen3-TTS-12Hz-0.6B-Base"

# 1.7B Base (for desktop)
echo "   [c] Downloading Qwen3-TTS-12Hz-1.7B-Base (~4.54GB)..."
huggingface-cli download Qwen/Qwen3-TTS-12Hz-1.7B-Base \
    --local-dir "$SCRIPT_DIR/models/Qwen3-TTS-12Hz-1.7B-Base"

# --- 4. Create checkpoint directories ---
echo ""
echo "[4/4] Creating checkpoint directories..."
mkdir -p "$SCRIPT_DIR/checkpoints/qwen3-tts-sheng-0.6b"
mkdir -p "$SCRIPT_DIR/checkpoints/qwen3-tts-sheng-1.7b"
mkdir -p "$SCRIPT_DIR/checkpoints/whisper-sheng"
mkdir -p "$PROJECT_ROOT/brain/voice/models/whisper-sheng-ct2"
mkdir -p "$PROJECT_ROOT/brain/voice/training_data"

# --- Verify GPU ---
echo ""
echo "================================================"
echo "  Verifying GPU..."
echo "================================================"
python3 -c "
import torch
if torch.cuda.is_available():
    gpu = torch.cuda.get_device_name(0)
    vram = torch.cuda.get_device_properties(0).total_memory / 1e9
    print(f'  GPU: {gpu}')
    print(f'  VRAM: {vram:.1f} GB')
    print(f'  CUDA: {torch.version.cuda}')
    print(f'  PyTorch: {torch.__version__}')
else:
    print('  WARNING: No CUDA GPU detected!')
    print('  Training will be very slow on CPU.')
"

echo ""
echo "================================================"
echo "  Setup Complete!"
echo "================================================"
echo ""
echo "  Next steps:"
echo "  1. Record training data:  ./sage collect"
echo "  2. Prepare TTS data:      python brain/voice/training/prepare_tts_data.py"
echo "  3. Fine-tune TTS:         python brain/voice/training/finetune_tts.py --size 0.6b"
echo "  4. Prepare STT data:      python brain/voice/training/prepare_stt_data.py"
echo "  5. Fine-tune STT:         python brain/voice/training/finetune_stt.py"
echo "  6. Export for Jetson:      bash brain/voice/training/export_for_jetson.sh"
echo ""
