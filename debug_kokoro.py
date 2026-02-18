import os
import sys
import numpy as np
import json
from kokoro_onnx import Kokoro

KOKORO_MODEL = "brain/voice/models/kokoro-v0_19.onnx"
KOKORO_VOICES = "brain/voice/models/voices.bin"

print(f"Loading Kokoro from:\nModel: {KOKORO_MODEL}\nVoices: {KOKORO_VOICES}")

try:
    # Verify files exist
    if not os.path.exists(KOKORO_MODEL):
        print("❌ Model MISSING")
    if not os.path.exists(KOKORO_VOICES):
        print("❌ Voices MISSING")

    # Try loading JSON manually first
    with open(KOKORO_VOICES, 'r') as f:
        v = json.load(f)
    print(f"✅ JSON Load OK. Keys: {list(v.keys())[:3]}")

    # Init Kokoro
    t = Kokoro(KOKORO_MODEL, KOKORO_VOICES)
    print("✅ Kokoro Init OK")
    
    # Try creating audio
    wav, sr = t.create("Hello world", voice="af_bella", speed=1.0, lang="en-us")
    print(f"✅ Generation OK. SR={sr}, Shape={wav.shape}")

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
