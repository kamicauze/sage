#!/bin/bash
set -e

echo "================================================="
echo "  Export Fine-tuned Models for Jetson Deployment"
echo "================================================="

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

EXPORT_DIR="$PROJECT_ROOT/jetson_export"

mkdir -p "$EXPORT_DIR"

# --- 1. Export TTS (Qwen3-TTS 0.6B fine-tuned) ---
TTS_CHECKPOINT="$SCRIPT_DIR/checkpoints/qwen3-tts-sheng-0.6b/final"
TTS_EXPORT="$EXPORT_DIR/brain/voice/models/qwen3-tts-sheng-0.6b"

if [ -d "$TTS_CHECKPOINT" ]; then
    echo "[1/3] Packaging Qwen3-TTS 0.6B fine-tuned model..."
    mkdir -p "$TTS_EXPORT"
    cp -r "$TTS_CHECKPOINT"/* "$TTS_EXPORT/"
    echo "  -> $TTS_EXPORT"
else
    echo "[1/3] SKIP: No TTS checkpoint found at $TTS_CHECKPOINT"
    echo "  Run: python brain/voice/training/finetune_tts.py --size 0.6b"
fi

# --- 2. Export STT (Whisper CTranslate2) ---
STT_MODEL="$PROJECT_ROOT/brain/voice/models/whisper-sheng-ct2"
STT_EXPORT="$EXPORT_DIR/brain/voice/models/whisper-sheng-ct2"

if [ -d "$STT_MODEL" ]; then
    echo "[2/3] Packaging Whisper Sheng CTranslate2 model..."
    mkdir -p "$STT_EXPORT"
    cp -r "$STT_MODEL"/* "$STT_EXPORT/"
    echo "  -> $STT_EXPORT"
else
    echo "[2/3] SKIP: No STT model found at $STT_MODEL"
    echo "  Run: python brain/voice/training/export_stt.py"
fi

# --- 3. Copy reference audio ---
REF_AUDIO="$PROJECT_ROOT/brain/voice/qwen_reference.wav"
REF_EXPORT="$EXPORT_DIR/brain/voice/qwen_reference.wav"

if [ -f "$REF_AUDIO" ]; then
    echo "[3/3] Copying Qwen reference audio..."
    mkdir -p "$(dirname "$REF_EXPORT")"
    cp "$REF_AUDIO" "$REF_EXPORT"
else
    echo "[3/3] SKIP: No reference audio at $REF_AUDIO"
fi

# --- Create tarball ---
echo ""
echo "Creating tarball..."
TARBALL="$PROJECT_ROOT/sage-jetson-models.tar.gz"
cd "$EXPORT_DIR"
tar czf "$TARBALL" .
cd "$PROJECT_ROOT"

# Cleanup
rm -rf "$EXPORT_DIR"

# Size report
SIZE=$(du -sh "$TARBALL" | cut -f1)
echo ""
echo "================================================="
echo "  Export Complete!"
echo "================================================="
echo ""
echo "  Tarball: $TARBALL ($SIZE)"
echo ""
echo "  Transfer to Jetson:"
echo "    scp $TARBALL jetson:/path/to/sage/"
echo ""
echo "  On Jetson:"
echo "    cd /path/to/sage"
echo "    tar xzf sage-jetson-models.tar.gz"
echo "    # Then uncomment model paths in .env:"
echo "    #   QWEN_TTS_MODEL=brain/voice/models/qwen3-tts-sheng-0.6b"
echo "    #   STT_MODEL_PATH=brain/voice/models/whisper-sheng-ct2"
echo "    #   STT_LANGUAGE=sw"
echo "    #   TTS_ENGINE=qwen"
echo ""
echo "================================================="
