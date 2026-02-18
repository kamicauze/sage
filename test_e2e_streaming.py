#!/usr/bin/env python3
"""
End-to-end streaming test: Local LLM → TTSStreamer → Kokoro TTS
Proves that TTS starts speaking BEFORE the LLM finishes generating.

No MQTT needed — simulates the full pipeline locally.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# Project setup
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "brain-runtime"))
sys.path.insert(0, str(PROJECT_ROOT / "brain" / "voice"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "apps" / "brain-runtime" / ".env")

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = "gemma3:latest"  # 3.3GB, fast

KOKORO_MODEL = PROJECT_ROOT / "brain" / "voice" / "models" / "kokoro-v0_19.onnx"
KOKORO_VOICES = PROJECT_ROOT / "brain" / "voice" / "models" / "voices.bin"


async def main():
    from ai.ollama_client import ollama_chat_stream
    from streamer import TTSStreamer
    from kokoro_onnx import Kokoro
    import sounddevice as sd

    print("=" * 60)
    print("  E2E STREAMING TEST: Ollama → TTSStreamer → Kokoro")
    print(f"  Model: {MODEL}")
    print("=" * 60)

    # Load Kokoro
    print("\n  Loading Kokoro TTS...")
    t0 = time.time()
    kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    print(f"  Kokoro loaded in {(time.time()-t0)*1000:.0f}ms")

    # Warmup Kokoro
    kokoro.create("OK", voice="af_bella", speed=0.85, lang="en-us")
    print("  Kokoro warmed up")

    # Track everything
    events = []  # (timestamp, event_type, detail)
    tts_queue = asyncio.Queue()
    pipeline_start = None

    def log_event(event_type, detail=""):
        elapsed = (time.time() - pipeline_start) * 1000 if pipeline_start else 0
        events.append((elapsed, event_type, detail))
        print(f"  [{elapsed:7.0f}ms] {event_type}: {detail}")

    # Mock MQTT that captures publishes and queues for TTS
    class MockMQTT:
        def publish(self, topic, payload):
            data = json.loads(payload)
            text = data.get("text", "")
            if text and data.get("stream"):
                log_event("TTS_CHUNK_QUEUED", f"[{data.get('chunk_index')}] \"{text[:55]}\"")
                tts_queue.put_nowait(text)

    streamer = TTSStreamer(MockMQTT())

    # TTS synthesis worker — processes sentences as they arrive
    tts_done = asyncio.Event()
    synth_count = 0

    async def tts_worker():
        nonlocal synth_count
        while True:
            try:
                text = await asyncio.wait_for(tts_queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                break

            synth_start = time.time()
            # Run Kokoro in thread pool (it's CPU-bound)
            wav, sr = await asyncio.get_event_loop().run_in_executor(
                None, lambda: kokoro.create(text, voice="af_bella", speed=0.85, lang="en-us")
            )
            synth_ms = (time.time() - synth_start) * 1000
            audio_dur = len(wav) / sr

            synth_count += 1
            log_event("TTS_SYNTH_DONE", f"#{synth_count} {synth_ms:.0f}ms gen, {audio_dur:.1f}s audio")

            # Play audio (blocking in executor)
            log_event("TTS_PLAY_START", f"#{synth_count}")
            await asyncio.get_event_loop().run_in_executor(
                None, lambda: (sd.play(wav, samplerate=sr), sd.wait())
            )
            log_event("TTS_PLAY_DONE", f"#{synth_count}")

        tts_done.set()

    # Token callback — feeds streamer
    token_count = 0

    async def on_token(token):
        nonlocal token_count
        token_count += 1
        if token_count == 1:
            log_event("FIRST_TOKEN", repr(token))
        await streamer.feed(token)

    # Start TTS worker
    tts_task = asyncio.create_task(tts_worker())

    # Start LLM
    prompt = "Tell me about the history and culture of Nairobi, the food scene, and what makes it special compared to other African cities."
    messages = [
        {"role": "system", "content": "You are Sage, a Nairobi voice assistant. Respond in 4-6 sentences with natural Sheng-English mix."},
        {"role": "user", "content": prompt},
    ]

    print(f"\n  Prompt: \"{prompt}\"")
    print(f"  Starting pipeline...\n")

    pipeline_start = time.time()
    log_event("LLM_START", f"model={MODEL}")

    response = await ollama_chat_stream(
        base_url=OLLAMA_HOST,
        model=MODEL,
        messages=messages,
        on_token=on_token,
    )

    log_event("LLM_DONE", f"{token_count} tokens, {len(response.split())} words")

    # Flush remaining buffer
    await streamer.flush()
    if streamer.buffer.strip() if hasattr(streamer, 'buffer') else False:
        pass  # flush already handled it

    # Check if flush produced a final chunk
    remaining = streamer.sent_chunks[-1] if streamer.sent_chunks else ""
    log_event("STREAMER_FLUSH", f"total chunks={len(streamer.sent_chunks)}")

    # Wait for TTS to finish playing
    log_event("WAITING_TTS", "waiting for all audio to finish...")
    await tts_done.wait()

    total_ms = (time.time() - pipeline_start) * 1000

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  RESULTS")
    print(f"{'=' * 60}")
    print(f"  Full response: {response[:120]}...")
    print(f"  LLM tokens: {token_count}")
    print(f"  TTS chunks: {len(streamer.sent_chunks)}")
    print(f"  TTS synths: {synth_count}")
    print()

    # Extract key timings
    first_token = next((e for e in events if e[1] == "FIRST_TOKEN"), None)
    first_queued = next((e for e in events if e[1] == "TTS_CHUNK_QUEUED"), None)
    first_synth = next((e for e in events if e[1] == "TTS_SYNTH_DONE"), None)
    first_play = next((e for e in events if e[1] == "TTS_PLAY_START"), None)
    llm_done = next((e for e in events if e[1] == "LLM_DONE"), None)

    print(f"  TIMELINE:")
    if first_token:
        print(f"    First LLM token:      {first_token[0]:>7.0f}ms")
    if first_queued:
        print(f"    First TTS chunk:      {first_queued[0]:>7.0f}ms")
    if first_synth:
        print(f"    First synth done:     {first_synth[0]:>7.0f}ms")
    if first_play:
        print(f"    First audio playing:  {first_play[0]:>7.0f}ms")
    if llm_done:
        print(f"    LLM finished:         {llm_done[0]:>7.0f}ms")
    print(f"    Total pipeline:       {total_ms:>7.0f}ms")

    if first_play and llm_done and first_play[0] < llm_done[0]:
        saved = llm_done[0] - first_play[0]
        print(f"\n  STREAMING WORKS! Audio started {saved:.0f}ms BEFORE LLM finished.")
    elif first_play and llm_done:
        print(f"\n  Audio started AFTER LLM finished — streaming didn't help.")
    print()


if __name__ == "__main__":
    asyncio.run(main())
