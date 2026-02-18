#!/usr/bin/env python3
"""
Integration test for the latency optimizations:
1. Cloud SSE streaming (chat_stream)
2. TTSStreamer sentence splitting
3. Full pipeline simulation (cloud stream → sentence split → TTS queue)
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

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "apps" / "brain-runtime" / ".env")


async def test_cloud_streaming():
    """Test 1: Cloud SSE streaming with Grok."""
    from ai.cloud_client import cloud_brain

    print("=" * 60)
    print("  TEST 1: Cloud SSE Streaming (Grok)")
    print("=" * 60)

    tokens_received = []
    first_token_time = [None]
    test_start = time.time()

    async def on_token(token):
        if first_token_time[0] is None:
            first_token_time[0] = time.time()
        tokens_received.append(token)

    messages = [
        {"role": "system", "content": "You are a helpful assistant. Keep responses to 2-3 sentences."},
        {"role": "user", "content": "What's the capital of Kenya?"},
    ]

    try:
        response = await cloud_brain.chat_stream("grok", messages, on_token=on_token)
        elapsed = time.time() - test_start
        ttft = first_token_time[0] - test_start if first_token_time[0] else elapsed

        print(f"\n  Response: {response[:120]}...")
        print(f"  Tokens received: {len(tokens_received)}")
        print(f"  TTFT: {ttft*1000:.0f}ms")
        print(f"  Total: {elapsed*1000:.0f}ms")
        print(f"  PASS" if len(tokens_received) > 5 else f"  FAIL: Expected >5 tokens, got {len(tokens_received)}")
        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        return False


async def test_tts_streamer():
    """Test 2: TTSStreamer sentence boundary detection."""
    print("\n" + "=" * 60)
    print("  TEST 2: TTSStreamer Sentence Splitting")
    print("=" * 60)

    # Mock MQTT client
    class MockMQTT:
        def __init__(self):
            self.published = []
        def publish(self, topic, payload):
            data = json.loads(payload)
            self.published.append(data)
            print(f"  → TTS chunk [{data.get('chunk_index')}]: \"{data['text'][:60]}\"")

    mock = MockMQTT()

    # Import TTSStreamer
    sys.path.insert(0, str(PROJECT_ROOT / "brain" / "voice"))
    from streamer import TTSStreamer

    streamer = TTSStreamer(mock)

    # Simulate streaming tokens like an LLM would produce
    test_response = (
        "The capital of Kenya is Nairobi. "
        "It's the largest city in East Africa. "
        "Nairobi is known as the Green City in the Sun."
    )

    # Feed character by character (simulating token stream)
    t0 = time.time()
    words = test_response.split(" ")
    for i, word in enumerate(words):
        token = word + " " if i < len(words) - 1 else word
        await streamer.feed(token)

    await streamer.flush()
    elapsed = (time.time() - t0) * 1000

    print(f"\n  Chunks published: {len(mock.published)}")
    print(f"  Processing time: {elapsed:.1f}ms")

    success = len(mock.published) >= 2  # Should split into at least 2-3 sentences
    print(f"  {'PASS' if success else 'FAIL'}: Expected >=2 chunks, got {len(mock.published)}")
    return success


async def test_cloud_to_tts_pipeline():
    """Test 3: Full pipeline - cloud stream → TTSStreamer → sentence chunks."""
    from ai.cloud_client import cloud_brain

    print("\n" + "=" * 60)
    print("  TEST 3: Cloud → TTSStreamer Pipeline")
    print("=" * 60)

    # Mock MQTT
    class MockMQTT:
        def __init__(self):
            self.published = []
            self.timestamps = []
        def publish(self, topic, payload):
            data = json.loads(payload)
            self.published.append(data)
            self.timestamps.append(time.time())
            print(f"  → TTS [{data.get('chunk_index')}] at {(time.time()-pipeline_start)*1000:.0f}ms: \"{data['text'][:55]}\"")

    mock = MockMQTT()

    sys.path.insert(0, str(PROJECT_ROOT / "brain" / "voice"))
    from streamer import TTSStreamer

    streamer = TTSStreamer(mock)

    pipeline_start = time.time()
    first_chunk_time = [None]

    original_send = streamer._send_to_tts
    async def tracked_send(text):
        if first_chunk_time[0] is None:
            first_chunk_time[0] = time.time()
        await original_send(text)
    streamer._send_to_tts = tracked_send

    async def on_token(token):
        await streamer.feed(token)

    messages = [
        {"role": "system", "content": "You are a Kenyan voice assistant named Sage. Respond naturally in 3-4 sentences."},
        {"role": "user", "content": "Tell me something interesting about Nairobi."},
    ]

    try:
        response = await cloud_brain.chat_stream("grok", messages, on_token=on_token)
        await streamer.flush()

        elapsed = time.time() - pipeline_start
        ttfc = (first_chunk_time[0] - pipeline_start) if first_chunk_time[0] else elapsed

        print(f"\n  Full response: {response[:150]}...")
        print(f"  TTS chunks: {len(mock.published)}")
        print(f"  Time to first TTS chunk: {ttfc*1000:.0f}ms")
        print(f"  Total pipeline: {elapsed*1000:.0f}ms")

        if len(mock.published) >= 2 and mock.timestamps:
            gap = (mock.timestamps[-1] - mock.timestamps[0]) * 1000
            print(f"  Chunk spread: {gap:.0f}ms (first→last)")
            print(f"  Latency saved: ~{elapsed*1000 - ttfc*1000:.0f}ms (TTS starts before full response)")

        success = len(mock.published) >= 2 and ttfc < elapsed * 0.7
        print(f"  {'PASS' if success else 'FAIL'}")
        return success
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback; traceback.print_exc()
        return False


async def test_silence_duration():
    """Test 4: Verify silence duration was lowered."""
    print("\n" + "=" * 60)
    print("  TEST 4: STT Silence Duration Check")
    print("=" * 60)

    # Read the actual default from the transcriber module
    sys.path.insert(0, str(PROJECT_ROOT / "brain" / "voice"))

    # Don't import the full module (needs pyaudio), just check the file
    import re
    transcriber_path = PROJECT_ROOT / "brain" / "voice" / "transcriber.py"
    content = transcriber_path.read_text()

    match = re.search(r'STT_SILENCE_DURATION.*?"([\d.]+)"', content)
    if match:
        val = float(match.group(1))
        print(f"  Default silence duration: {val}s")
        success = val <= 0.5
        print(f"  {'PASS' if success else 'FAIL'}: Expected <= 0.5s, got {val}s")
        return success
    else:
        print("  FAIL: Could not parse silence duration from transcriber.py")
        return False


async def test_stream_tts_default():
    """Test 5: Verify STREAM_TTS defaults to true."""
    print("\n" + "=" * 60)
    print("  TEST 5: STREAM_TTS Default Check")
    print("=" * 60)

    main_path = PROJECT_ROOT / "apps" / "brain-runtime" / "main.py"
    content = main_path.read_text()

    import re
    match = re.search(r'SAGE_STREAM_TTS.*?"(\w+)"', content)
    if match:
        val = match.group(1)
        print(f"  Default SAGE_STREAM_TTS: \"{val}\"")
        success = val == "true"
        print(f"  {'PASS' if success else 'FAIL'}")
        return success
    else:
        print("  FAIL: Could not parse STREAM_TTS default")
        return False


async def main():
    print("=" * 60)
    print("  SAGE STREAMING LATENCY INTEGRATION TESTS")
    print("=" * 60)

    results = {}

    # Config checks (fast, no API calls)
    results["silence_duration"] = await test_silence_duration()
    results["stream_tts_default"] = await test_stream_tts_default()

    # Sentence splitting (no API)
    results["tts_streamer"] = await test_tts_streamer()

    # Cloud streaming (requires API key)
    results["cloud_streaming"] = await test_cloud_streaming()

    # Full pipeline (cloud → TTSStreamer)
    results["cloud_to_tts"] = await test_cloud_to_tts_pipeline()

    # Summary
    print("\n" + "=" * 60)
    print("  RESULTS")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  {status}  {name}")

    total = sum(results.values())
    print(f"\n  {total}/{len(results)} tests passed")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
