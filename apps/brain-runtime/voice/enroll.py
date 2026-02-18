"""
Voice Enrollment for Speaker Verification (Multi-Sample)
Records your voice and creates voiceprints for Sage to recognize you.

Supports multiple voice samples for better recognition across:
- Different times of day (morning voice vs evening)
- Different moods/energy levels
- Different speaking volumes
- Different mic distances

Usage:
    python -m brain.voice.enroll              # Add a new voice sample
    python -m brain.voice.enroll --fresh      # Clear all and start fresh
    python -m brain.voice.enroll --test       # Test current voiceprint
    python -m brain.voice.enroll --status     # Show enrollment status
"""

import os
import sys
import time
import argparse
import numpy as np
import pyaudio
from pathlib import Path

# Audio settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_SECONDS = 10  # Shorter samples, but multiple of them

# Paths
VOICE_DIR = Path(__file__).parent
OWNER_EMBEDDINGS_DIR = VOICE_DIR / "owner_embeddings"
OWNER_EMBEDDING_PATH = VOICE_DIR / "owner_voice.npy"  # Legacy path


def record_audio(duration: int = RECORD_SECONDS, label: str = "your voice") -> np.ndarray:
    """Record audio from microphone."""
    p = pyaudio.PyAudio()
    
    print(f"\n🎤 Recording {label} in 3 seconds...")
    print("   Speak naturally - describe your day, count, or read something.\n")
    
    for i in range(3, 0, -1):
        print(f"   {i}...")
        time.sleep(1)
    
    print(f"\n🔴 RECORDING ({duration}s) - Speak now!")
    
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    
    frames = []
    start_time = time.time()
    
    while time.time() - start_time < duration:
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        
        # Show progress
        elapsed = int(time.time() - start_time)
        remaining = duration - elapsed
        bar = "█" * elapsed + "░" * remaining
        print(f"\r   [{bar}] {remaining}s remaining", end="", flush=True)
    
    print("\n\n✅ Recording complete!")
    
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Convert to numpy array
    audio_data = b''.join(frames)
    audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
    
    return audio_np


def create_embedding(audio: np.ndarray) -> np.ndarray:
    """Create speaker embedding from audio."""
    print("\n⚙️  Creating voiceprint...")
    
    from resemblyzer import VoiceEncoder, preprocess_wav
    
    encoder = VoiceEncoder()
    
    # Preprocess and create embedding
    processed = preprocess_wav(audio, source_sr=RATE)
    embedding = encoder.embed_utterance(processed)
    
    print(f"   Embedding shape: {embedding.shape}")
    return embedding


def verify_embedding(embedding: np.ndarray) -> bool:
    """Quick verification that the embedding looks valid."""
    if embedding is None or len(embedding) == 0:
        return False
    if np.isnan(embedding).any():
        return False
    # Resemblyzer embeddings are 256-dim normalized vectors
    if len(embedding) != 256:
        return False
    return True


def get_enrollment_status():
    """Get current enrollment status."""
    from brain.voice.speaker_verify import get_verifier
    
    verifier = get_verifier()
    stats = verifier.get_stats()
    
    return stats


def show_status():
    """Display current enrollment status."""
    stats = get_enrollment_status()
    
    print("\n" + "=" * 50)
    print("📊 ENROLLMENT STATUS")
    print("=" * 50)
    
    if not stats["enabled"]:
        print("\n❌ No voiceprints enrolled")
        print("   Run './sage enroll' to enroll your voice")
        return
    
    print(f"\n✅ Voice verification ENABLED")
    print(f"   Voiceprints: {stats['num_embeddings']}")
    print(f"   Threshold: {stats['threshold']}")
    
    if stats['labels']:
        print(f"\n   Samples:")
        for i, label in enumerate(stats['labels']):
            print(f"     {i+1}. {label}")
    
    if stats['recent_scores']:
        print(f"\n   Recent verification scores:")
        print(f"     Last 5: {[f'{s:.2f}' for s in stats['recent_scores'][-5:]]}")
        print(f"     Average: {stats['avg_recent_score']:.3f}")
    
    print()


def test_voiceprint():
    """Test current voiceprint with a new recording."""
    from brain.voice.speaker_verify import get_verifier
    
    verifier = get_verifier()
    
    if not verifier.enabled:
        print("\n❌ No voiceprint enrolled. Run './sage enroll' first.")
        return
    
    print("\n" + "=" * 50)
    print("🧪 TESTING VOICEPRINT")
    print("=" * 50)
    
    # Record test audio
    audio = record_audio(duration=5, label="test sample")
    
    if len(audio) < RATE * 2:
        print("❌ Recording too short")
        return
    
    # Get all similarities
    all_sims = verifier.get_all_similarities(audio, RATE)
    best_score, best_idx = verifier.get_best_similarity(audio, RATE)
    is_owner = best_score >= verifier.threshold
    
    print(f"\n📊 Results:")
    print(f"   Best match: {best_score:.3f}")
    print(f"   Threshold: {verifier.threshold}")
    print(f"   Verdict: {'✅ OWNER VERIFIED' if is_owner else '❌ NOT RECOGNIZED'}")
    
    if all_sims:
        print(f"\n   All sample scores:")
        for label, sim in all_sims:
            marker = "←" if sim == best_score else ""
            print(f"     {label}: {sim:.3f} {marker}")
    
    # Advice
    if not is_owner:
        print(f"\n💡 Tip: Your score ({best_score:.3f}) is below threshold ({verifier.threshold})")
        print("   Try one of these:")
        print("   1. Add more voice samples: ./sage enroll")
        print("   2. Lower threshold: export SPEAKER_THRESHOLD=0.50")
        print("   3. Re-enroll in current conditions: ./sage enroll --fresh")
    
    print()


def enroll_sample(label: str = None, fresh: bool = False):
    """Enroll a new voice sample."""
    from brain.voice.speaker_verify import get_verifier, reload_verifier
    
    verifier = get_verifier()
    
    if fresh:
        print("\n🗑️  Clearing existing voiceprints...")
        verifier.clear_embeddings()
        verifier = reload_verifier()
    
    current_count = len(verifier.owner_embeddings)
    
    print("=" * 50)
    print("🎙️  SAGE VOICE ENROLLMENT")
    print("=" * 50)
    
    if current_count > 0:
        print(f"\n📦 You have {current_count} existing voiceprint(s)")
        print("   Adding another sample improves recognition accuracy.")
        print("   Use --fresh to start over, or --test to test current setup.")
    else:
        print("\nThis will create your voiceprint so Sage only responds to YOU.")
        print("For best results, enroll 2-3 samples in different conditions:")
        print("  - Normal speaking voice")
        print("  - Quieter/tired voice")
        print("  - Different mic distance")
    
    # Generate label if not provided
    if label is None:
        sample_num = current_count + 1
        time_of_day = "morning" if time.localtime().tm_hour < 12 else "afternoon" if time.localtime().tm_hour < 18 else "evening"
        label = f"sample_{sample_num}_{time_of_day}"
    
    print(f"\n📝 Sample label: {label}")
    
    # Record
    audio = record_audio(RECORD_SECONDS)
    
    if len(audio) < RATE * 3:  # Less than 3 seconds
        print("❌ Recording too short. Please try again.")
        return False
    
    # Create embedding
    try:
        embedding = create_embedding(audio)
    except Exception as e:
        print(f"❌ Failed to create embedding: {e}")
        return False
    
    # Verify embedding is valid
    if not verify_embedding(embedding):
        print("❌ Invalid embedding. Please try again with clearer audio.")
        return False
    
    # Check similarity to existing embeddings (shouldn't be too different)
    if verifier.enabled:
        from resemblyzer import preprocess_wav
        verifier._load_encoder()
        
        processed = preprocess_wav(audio, source_sr=RATE)
        test_emb = verifier.encoder.embed_utterance(processed)
        
        max_sim = 0
        for owner_emb in verifier.owner_embeddings:
            sim = float(np.dot(owner_emb, test_emb))
            max_sim = max(max_sim, sim)
        
        print(f"\n📊 Similarity to existing samples: {max_sim:.3f}")
        
        if max_sim < 0.4:
            print("⚠️  Warning: This sample seems quite different from existing ones.")
            print("   This could mean:")
            print("   - Different speaker (if so, don't add this)")
            print("   - Very different conditions (background noise, whisper, etc.)")
            response = input("\n   Add anyway? (y/N): ").strip().lower()
            if response != 'y':
                print("   Cancelled.")
                return False
    
    # Add to verifier
    success = verifier.add_embedding(embedding, label)
    
    if success:
        print("\n" + "=" * 50)
        print("✅ ENROLLMENT COMPLETE!")
        print("=" * 50)
        print(f"\n   Total voiceprints: {len(verifier.owner_embeddings)}")
        print(f"   Threshold: {verifier.threshold}")
        
        if len(verifier.owner_embeddings) == 1:
            print("\n💡 Tip: Enroll 1-2 more samples for better recognition")
            print("   Run './sage enroll' again in different conditions.")
        elif len(verifier.owner_embeddings) < 3:
            print("\n💡 Tip: One more sample recommended for robust recognition")
        else:
            print("\n   Good coverage! Use './sage enroll --test' to verify.")
        
        print()
        return True
    else:
        print("❌ Failed to save voiceprint")
        return False


def main():
    parser = argparse.ArgumentParser(description="Sage Voice Enrollment")
    parser.add_argument("--fresh", action="store_true", help="Clear all voiceprints and start fresh")
    parser.add_argument("--test", action="store_true", help="Test current voiceprint")
    parser.add_argument("--status", action="store_true", help="Show enrollment status")
    parser.add_argument("--label", type=str, help="Custom label for this sample")
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
    elif args.test:
        test_voiceprint()
    else:
        enroll_sample(label=args.label, fresh=args.fresh)


if __name__ == "__main__":
    main()
