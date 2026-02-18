#!/usr/bin/env python3
"""
Full pipeline streaming test through the actual Sage Brain.

Requires: Brain running (./sage brain or ./sage pwa)
Tests: Fake STT transcript → Brain (intent/router/LLM) → TTS chunks via MQTT

Subscribes to sage/voice/response and sage/tts/metrics to capture
what the Speaker service would receive.
"""

import json
import os
import sys
import time
import threading
from pathlib import Path

import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

# Test utterances
TEST_TRANSCRIPT = "Tell me about the best places to eat in Nairobi"

events = []
pipeline_start = None
first_chunk_time = None
all_done = threading.Event()
chunk_count = 0
chunks_received = []


def log_event(event_type, detail=""):
    elapsed = (time.time() - pipeline_start) * 1000 if pipeline_start else 0
    events.append((elapsed, event_type, detail))
    print(f"  [{elapsed:7.0f}ms] {event_type}: {detail}")


def on_connect(client, userdata, flags, rc):
    if rc != 0:
        print(f"  ERROR: MQTT connect failed rc={rc}")
        return
    # Subscribe to everything relevant
    client.subscribe("sage/voice/response")
    client.subscribe("sage/voice/streaming")
    client.subscribe("sage/tts/metrics")
    client.subscribe("sage/tts/status")
    client.subscribe("sage/stt/metrics")
    print("  MQTT subscribed")


def on_message(client, userdata, msg):
    global first_chunk_time, chunk_count

    topic = msg.topic
    try:
        payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError:
        payload = {"raw": msg.payload.decode()}

    if topic == "sage/voice/streaming":
        # Token-level streaming from brain
        if first_chunk_time is None:
            first_chunk_time = time.time()
            log_event("FIRST_STREAM_TOKEN", repr(payload.get("text", "")[:30]))
        return

    if topic == "sage/voice/response":
        text = payload.get("text", "")
        is_stream = payload.get("stream", False)
        no_tts = payload.get("no_tts", False)
        chunk_idx = payload.get("chunk_index", "?")
        source = payload.get("source", "")

        if no_tts:
            log_event("FINAL_UI_PUBLISH", f"no_tts=True, {len(text)} chars, src={source}")
            # This is the last event — give speaker a moment then signal done
            threading.Timer(1.0, all_done.set).start()
            return

        if is_stream:
            chunk_count += 1
            chunks_received.append({"text": text, "ts": time.time()})
            log_event("TTS_CHUNK", f"[{chunk_idx}] \"{text[:60]}\"")
        else:
            # Non-streaming full response
            chunks_received.append({"text": text, "ts": time.time()})
            log_event("TTS_FULL_RESPONSE", f"\"{text[:80]}\" src={source}")
            threading.Timer(1.0, all_done.set).start()

    if topic == "sage/tts/status":
        status = payload.get("status", "")
        if status in ("speaking", "done"):
            log_event(f"TTS_{status.upper()}", payload.get("engine", ""))


def main():
    global pipeline_start

    print("=" * 60)
    print("  FULL PIPELINE STREAMING TEST")
    print(f"  Transcript: \"{TEST_TRANSCRIPT}\"")
    print("=" * 60)

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
    except Exception as e:
        print(f"  ERROR: Cannot connect to MQTT at {MQTT_HOST}:{MQTT_PORT}: {e}")
        print("  Make sure mosquitto is running.")
        sys.exit(1)

    client.loop_start()
    time.sleep(0.5)  # Let subscriptions settle

    # Clear any pending TTS
    client.publish("sage/tts/clear", json.dumps({"reason": "test"}))
    time.sleep(0.2)

    # Send fake transcript
    print(f"\n  Sending transcript to sage/voice/transcript...\n")
    pipeline_start = time.time()
    log_event("TRANSCRIPT_SENT", TEST_TRANSCRIPT)
    client.publish("sage/voice/transcript", TEST_TRANSCRIPT)

    # Wait for response (timeout 30s)
    got_response = all_done.wait(timeout=30.0)

    elapsed = (time.time() - pipeline_start) * 1000

    client.loop_stop()
    client.disconnect()

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  RESULTS")
    print(f"{'=' * 60}")

    if not got_response:
        print("  TIMEOUT: No response received in 30s.")
        print("  Is the Brain service running? (./sage brain or ./sage pwa)")
        return

    print(f"  Total chunks: {chunk_count}")
    print(f"  Total events: {len(events)}")
    print(f"  Pipeline time: {elapsed:.0f}ms")

    # Key timings
    first_stream = next((e for e in events if e[1] == "FIRST_STREAM_TOKEN"), None)
    first_tts = next((e for e in events if e[1] == "TTS_CHUNK"), None)
    final_pub = next((e for e in events if e[1] == "FINAL_UI_PUBLISH"), None)
    first_full = next((e for e in events if e[1] == "TTS_FULL_RESPONSE"), None)

    print(f"\n  TIMELINE:")
    if first_stream:
        print(f"    First stream token:   {first_stream[0]:>7.0f}ms")
    if first_tts:
        print(f"    First TTS chunk:      {first_tts[0]:>7.0f}ms")
    elif first_full:
        print(f"    Full TTS response:    {first_full[0]:>7.0f}ms  (NOT streamed)")
    if final_pub:
        print(f"    Final UI publish:     {final_pub[0]:>7.0f}ms")

    if first_tts and final_pub:
        head_start = final_pub[0] - first_tts[0]
        print(f"\n  Streaming saved: {head_start:.0f}ms (TTS started before final response)")
    elif first_full:
        print(f"\n  NOT STREAMING — response arrived as single block")

    if chunk_count > 1:
        print(f"  STREAMING CONFIRMED: {chunk_count} sentence chunks to TTS")
    elif chunk_count == 1:
        print(f"  PARTIAL: Only 1 chunk (response may be too short)")
    else:
        print(f"  NO STREAMING: 0 streamed chunks")

    print()


if __name__ == "__main__":
    main()
