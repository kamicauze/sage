import sounddevice as sd
import soundfile as sf
import numpy as np
import time
import os

DURATION = 25  # seconds
SAMPLE_RATE = 24000 # F5-TTS prefers 24khz usually, or 44.1k. 24k is standard for many vocoders.
OUTPUT_FILE = "brain/voice/reference.wav"

def record_audio():
    print(f"\n🎙️  Recording {DURATION} seconds for voice cloning...")
    print("   Please read a sentence clearly and naturally.")
    print("   (e.g., 'The quick brown fox jumps over the lazy dog. I am Sage, your assistant.')\n")
    
    print("3...")
    time.sleep(1)
    print("2...")
    time.sleep(1)
    print("1... GO!")
    
    # Record
    audio = sd.rec(int(DURATION * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1)
    sd.wait()
    
    print("\n✅ Recording complete.")
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # Save
    sf.write(OUTPUT_FILE, audio, SAMPLE_RATE)
    print(f"💾 Saved to {OUTPUT_FILE}")
    print("\nNow run: ./sage mouth")

if __name__ == "__main__":
    try:
        record_audio()
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure 'sounddevice' and 'soundfile' are installed: pip install -r requirements.txt")
