#!/usr/bin/env python3
"""
Sage STT + TTS Latency Benchmark
Tests Qwen TTS, Kokoro TTS, and Whisper STT using voice training data.
Runs engines on CUDA (no local LLM loaded = cloud-only brain mode).
"""

import json
import os
import sys
import time
import statistics
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

# Project root setup
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Paths
ARTIFACTS = PROJECT_ROOT / "artifacts" / "voice"
TRAINING_DATA = ARTIFACTS / "training_data"
MANIFEST = TRAINING_DATA / "manifest.jsonl"
PROCESSED_DIR = TRAINING_DATA / "processed"

KOKORO_MODEL = PROJECT_ROOT / "brain" / "voice" / "models" / "kokoro-v0_19.onnx"
KOKORO_VOICES = PROJECT_ROOT / "brain" / "voice" / "models" / "voices.bin"
QWEN_CHECKPOINT = ARTIFACTS / "training" / "checkpoints" / "qwen3-tts-sheng-1.7b" / "final"
QWEN_REF_AUDIO = PROJECT_ROOT / "brain" / "voice" / "qwen_reference.wav"

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
NUM_WARMUP = 3
NUM_BENCH = 10  # after-warmup runs

# Test sentences - mix of short/medium/long
TEST_SENTENCES = [
    "Hey, what's good?",
    "Can you check the logs and see what caused the error?",
    "The batch size needs to be reduced to fit in memory.",
    "That thing you told me about, niliskia ni legit.",
    "She called me jana and was like, dude come through.",
    "Turn off the lights in the living room and set the bedroom to twenty percent.",
    "I need you to remind me about the meeting tomorrow at ten AM, and also check if there are any updates on the deployment.",
    "OK",
    "How's the day been? Ama umekuwa busy?",
    "Not yet.",
    "My number is oh seven two one, five six seven, eight nine oh.",
    "Relax.",
    "This is so boring, can we do something else?",
]


def load_manifest():
    """Load training manifest and fix paths to use artifacts dir."""
    entries = []
    with open(MANIFEST) as f:
        for line in f:
            entry = json.loads(line)
            # Fix paths: manifest has brain/voice/... but actual files in artifacts/voice/...
            file_id = entry["file_id"]
            stt_wav = PROCESSED_DIR / f"{file_id}_16k.wav"
            tts_wav = PROCESSED_DIR / f"{file_id}_24k.wav"
            if stt_wav.exists():
                entry["stt_path"] = str(stt_wav)
            if tts_wav.exists():
                entry["tts_path"] = str(tts_wav)
            entries.append(entry)
    return entries


def vram_mb():
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / 1024 / 1024
    return 0


def fmt_stats(times_ms):
    if not times_ms:
        return "no data"
    return (
        f"avg={statistics.mean(times_ms):.0f}ms  "
        f"med={statistics.median(times_ms):.0f}ms  "
        f"min={min(times_ms):.0f}ms  "
        f"max={max(times_ms):.0f}ms  "
        f"std={statistics.stdev(times_ms):.0f}ms" if len(times_ms) > 1
        else f"avg={statistics.mean(times_ms):.0f}ms"
    )


def bench_stt(entries):
    """Benchmark Whisper STT on training audio files."""
    from faster_whisper import WhisperModel

    print("\n" + "=" * 60)
    print("  STT BENCHMARK (faster-whisper medium.en)")
    print("=" * 60)

    # Pick audio files for test
    stt_files = [(e["stt_path"], e["text"]) for e in entries if "stt_path" in e and os.path.exists(e.get("stt_path", ""))]
    if not stt_files:
        print("  ERROR: No STT audio files found!")
        return

    test_files = stt_files[:NUM_WARMUP + NUM_BENCH]
    print(f"  Device: {DEVICE} | Files: {len(test_files)} ({NUM_WARMUP} warmup + {NUM_BENCH} bench)")

    # Load model
    print(f"  Loading Whisper model...")
    load_start = time.time()
    model = WhisperModel("medium.en", device=DEVICE, compute_type="float16")
    load_ms = (time.time() - load_start) * 1000
    print(f"  Model loaded in {load_ms:.0f}ms | VRAM: {vram_mb():.0f}MB")

    warmup_times = []
    bench_times = []
    rtf_values = []  # real-time factor

    for i, (audio_path, expected_text) in enumerate(test_files):
        audio, sr = sf.read(audio_path)
        audio = audio.astype(np.float32)
        audio_duration = len(audio) / sr

        t0 = time.time()
        segments, info = model.transcribe(
            audio,
            beam_size=1,
            best_of=1,
            vad_filter=True,
            condition_on_previous_text=False,
            temperature=0.0,
        )
        text = "".join(s.text for s in segments).strip()
        elapsed_ms = (time.time() - t0) * 1000
        rtf = (elapsed_ms / 1000) / audio_duration if audio_duration > 0 else 0

        phase = "WARMUP" if i < NUM_WARMUP else "BENCH"
        if i < NUM_WARMUP:
            warmup_times.append(elapsed_ms)
        else:
            bench_times.append(elapsed_ms)
            rtf_values.append(rtf)

        print(f"  [{phase} {i+1:2d}] {elapsed_ms:6.0f}ms | {audio_duration:.1f}s audio | RTF={rtf:.2f} | \"{text[:50]}\"")

    print(f"\n  --- STT Results (after warmup) ---")
    print(f"  Latency:  {fmt_stats(bench_times)}")
    print(f"  RTF:      avg={statistics.mean(rtf_values):.3f}  (< 1.0 = faster than realtime)")
    print(f"  Warmup:   {fmt_stats(warmup_times)}")

    # Cleanup
    del model
    if DEVICE == "cuda":
        torch.cuda.empty_cache()

    return {"warmup": warmup_times, "bench": bench_times, "rtf": rtf_values}


def bench_tts_qwen():
    """Benchmark Qwen3-TTS."""
    print("\n" + "=" * 60)
    print("  TTS BENCHMARK: Qwen3-TTS 1.7B (fine-tuned Sheng)")
    print("=" * 60)

    if not QWEN_CHECKPOINT.exists():
        print(f"  SKIP: Qwen checkpoint not found at {QWEN_CHECKPOINT}")
        return None

    try:
        from qwen_tts import Qwen3TTSModel
    except ImportError as e:
        print(f"  SKIP: qwen_tts not importable: {e}")
        return None

    # Load model
    print(f"  Device: {DEVICE} | Checkpoint: {QWEN_CHECKPOINT.name}")
    print(f"  Loading Qwen3-TTS...")
    load_start = time.time()
    dtype = torch.bfloat16 if DEVICE == "cuda" else torch.float32
    tts = Qwen3TTSModel.from_pretrained(
        str(QWEN_CHECKPOINT),
        torch_dtype=dtype,
        attn_implementation="sdpa",
    )
    tts.model = tts.model.to(DEVICE)
    tts.device = torch.device(DEVICE)
    load_ms = (time.time() - load_start) * 1000
    print(f"  Model loaded in {load_ms:.0f}ms | VRAM: {vram_mb():.0f}MB")

    model_type = getattr(tts.model, "tts_model_type", "base")
    print(f"  Model type: {model_type}")

    # Determine synthesis method
    def synthesize(text):
        kwargs = {
            "max_new_tokens": max(128, min(640, 64 + len(text.split()) * 12)),
            "repetition_penalty": 1.08,
            "temperature": 0.9,
        }
        if model_type == "custom_voice":
            wavs, sr = tts.generate_custom_voice(
                text=text, speaker="sage_sheng", language="Auto", **kwargs
            )
        else:
            if not QWEN_REF_AUDIO.exists():
                print(f"  ERROR: Qwen ref audio missing: {QWEN_REF_AUDIO}")
                return None, None
            wavs, sr = tts.generate_voice_clone(
                text=text, language="Auto", ref_audio=str(QWEN_REF_AUDIO),
                x_vector_only_mode=True, **kwargs
            )
        return (wavs[0] if wavs else None), sr

    sentences = TEST_SENTENCES[:NUM_WARMUP + NUM_BENCH]
    warmup_times = []
    bench_times = []
    audio_durations = []

    for i, text in enumerate(sentences):
        t0 = time.time()
        wav, sr = synthesize(text)
        elapsed_ms = (time.time() - t0) * 1000

        audio_dur = len(wav) / sr if wav is not None else 0
        phase = "WARMUP" if i < NUM_WARMUP else "BENCH"

        if i < NUM_WARMUP:
            warmup_times.append(elapsed_ms)
        else:
            bench_times.append(elapsed_ms)
            audio_durations.append(audio_dur)

        status = f"{audio_dur:.1f}s audio" if wav is not None else "FAILED"
        print(f"  [{phase} {i+1:2d}] {elapsed_ms:6.0f}ms | {status} | \"{text[:45]}\"")

    print(f"\n  --- Qwen TTS Results (after warmup) ---")
    print(f"  Latency:      {fmt_stats(bench_times)}")
    if audio_durations:
        print(f"  Audio output: avg={statistics.mean(audio_durations):.2f}s")
    print(f"  Warmup:       {fmt_stats(warmup_times)}")
    print(f"  Model load:   {load_ms:.0f}ms")

    # Cleanup
    del tts
    if DEVICE == "cuda":
        torch.cuda.empty_cache()
    time.sleep(1)  # let VRAM settle

    return {"warmup": warmup_times, "bench": bench_times, "load_ms": load_ms, "audio_durations": audio_durations}


def bench_tts_kokoro():
    """Benchmark Kokoro TTS (ONNX)."""
    print("\n" + "=" * 60)
    print("  TTS BENCHMARK: Kokoro (ONNX)")
    print("=" * 60)

    if not KOKORO_MODEL.exists():
        print(f"  SKIP: Kokoro model not found at {KOKORO_MODEL}")
        return None

    from kokoro_onnx import Kokoro

    print(f"  Model: {KOKORO_MODEL.name}")
    print(f"  Loading Kokoro...")
    load_start = time.time()
    tts = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    load_ms = (time.time() - load_start) * 1000
    print(f"  Model loaded in {load_ms:.0f}ms | VRAM: {vram_mb():.0f}MB (ONNX = mostly CPU)")

    sentences = TEST_SENTENCES[:NUM_WARMUP + NUM_BENCH]
    warmup_times = []
    bench_times = []
    audio_durations = []

    for i, text in enumerate(sentences):
        t0 = time.time()
        wav, sr = tts.create(text, voice="af_bella", speed=0.85, lang="en-us")
        elapsed_ms = (time.time() - t0) * 1000

        audio_dur = len(wav) / sr if wav is not None else 0
        phase = "WARMUP" if i < NUM_WARMUP else "BENCH"

        if i < NUM_WARMUP:
            warmup_times.append(elapsed_ms)
        else:
            bench_times.append(elapsed_ms)
            audio_durations.append(audio_dur)

        print(f"  [{phase} {i+1:2d}] {elapsed_ms:6.0f}ms | {audio_dur:.1f}s audio | \"{text[:45]}\"")

    print(f"\n  --- Kokoro TTS Results (after warmup) ---")
    print(f"  Latency:      {fmt_stats(bench_times)}")
    if audio_durations:
        print(f"  Audio output: avg={statistics.mean(audio_durations):.2f}s")
    print(f"  Warmup:       {fmt_stats(warmup_times)}")
    print(f"  Model load:   {load_ms:.0f}ms")

    del tts
    return {"warmup": warmup_times, "bench": bench_times, "load_ms": load_ms, "audio_durations": audio_durations}


def main():
    print("=" * 60)
    print("  SAGE LATENCY BENCHMARK")
    print(f"  GPU: {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only'}")
    print(f"  VRAM free: {torch.cuda.mem_get_info()[0] / 1024**2:.0f}MB" if torch.cuda.is_available() else "")
    print(f"  Training samples: {sum(1 for _ in open(MANIFEST))}")
    print(f"  Warmup runs: {NUM_WARMUP} | Bench runs: {NUM_BENCH}")
    print("=" * 60)

    entries = load_manifest()

    # 1. Qwen TTS first (uses more VRAM)
    qwen_results = bench_tts_qwen()

    # 2. Kokoro TTS (ONNX, lighter)
    kokoro_results = bench_tts_kokoro()

    # 3. STT benchmark
    stt_results = bench_stt(entries)

    # Summary
    print("\n" + "=" * 60)
    print("  SUMMARY (after-warmup averages)")
    print("=" * 60)

    if qwen_results and qwen_results["bench"]:
        avg_q = statistics.mean(qwen_results["bench"])
        med_q = statistics.median(qwen_results["bench"])
        print(f"  Qwen TTS:   avg={avg_q:.0f}ms  med={med_q:.0f}ms  load={qwen_results['load_ms']:.0f}ms")

    if kokoro_results and kokoro_results["bench"]:
        avg_k = statistics.mean(kokoro_results["bench"])
        med_k = statistics.median(kokoro_results["bench"])
        print(f"  Kokoro TTS: avg={avg_k:.0f}ms  med={med_k:.0f}ms  load={kokoro_results['load_ms']:.0f}ms")

    if stt_results and stt_results["bench"]:
        avg_s = statistics.mean(stt_results["bench"])
        med_s = statistics.median(stt_results["bench"])
        avg_rtf = statistics.mean(stt_results["rtf"])
        print(f"  Whisper STT: avg={avg_s:.0f}ms  med={med_s:.0f}ms  RTF={avg_rtf:.3f}")

    if qwen_results and kokoro_results and qwen_results["bench"] and kokoro_results["bench"]:
        speedup = statistics.mean(qwen_results["bench"]) / statistics.mean(kokoro_results["bench"])
        print(f"\n  Kokoro is {speedup:.1f}x faster than Qwen TTS (generation time)")

    print()


if __name__ == "__main__":
    main()
