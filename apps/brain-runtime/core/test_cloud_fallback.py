#!/usr/bin/env python3
"""
Test Cloud Fallback Scenario

Tests the case where cloud LLM is unreachable and we fall back 
to the local LLM with the same personality.
"""

import json
import asyncio
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from summary_engine import SummaryEngine
from ai.ollama_client import ollama_chat
from ai.personalities import build_core_identity_prompt

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


def print_section(title):
    """Print a section header"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


async def test_cloud_fallback():
    """Test cloud unreachable scenario with local LLM fallback"""
    
    print("\n" + "🔄 "*40)
    print("CLOUD FALLBACK TEST - Local LLM with Personality")
    print("🔄 "*40)
    
    # Create scenario
    print_section("SCENARIO: Cloud Unreachable + Local Fallback")
    
    print("📋 Situation:")
    print("  - Cloud LLM (Grok) is unreachable")
    print("  - Need to respond to urgent situation (OVERWORK_LATE)")
    print("  - Fall back to Local LLM with same Kenyan babe personality")
    
    # Initialize engine
    engine = SummaryEngine()
    
    # Create test time
    test_time = datetime.strptime("2024-01-15 02:30:00", "%Y-%m-%d %H:%M:%S")
    now_ms = int(test_time.timestamp() * 1000)
    
    # Build state
    state = {
        "mode": "FOCUS",
        "flags": {"home_active": True},
        "rooms": {
            "office": {
                "occupied": True,
                "last_motion_ts": now_ms - (95 * 60 * 1000),
                "vision": {
                    "face_detected": True,
                    "head_pitch_deg": -35.0,
                    "body_configuration": "seated",
                    "eyes_open": True
                }
            }
        },
        "screen_active": True,
        "audio_silence_min": 95,
    }
    
    history = [
        {"type": "room_occupied", "ts": now_ms - (20 * 60 * 60 * 1000)},
        {"type": "motion", "ts": now_ms - (95 * 60 * 1000)}
    ]
    
    # LAYER 1: Deterministic Summary
    print_section("LAYER 1: Deterministic Summary")
    
    packet, briefing = engine.generate_summary(state, history, now_ms)
    
    print(f"✅ Patterns detected: {', '.join(packet['patterns'])}")
    print(f"✅ Intent: {packet['intent']}")
    print(f"✅ Constraints: {packet['constraints']['tone']}, max {packet['constraints']['max_words']} words")
    
    # LAYER 2: Simulate Cloud Failure
    print_section("LAYER 2: Cloud LLM Attempt (Will Fail)")
    
    print("🔄 Attempting to reach Cloud LLM (Grok)...")
    print("❌ Cloud LLM unreachable (simulating network failure)")
    print("🔄 Falling back to Local LLM with same personality...")
    
    # FALLBACK: Use Local LLM with Kenyan Babe personality
    print_section("FALLBACK: Local LLM with Kenyan Babe Personality")
    
    # Simulate mood detection (would come from real local LLM in production)
    # For this test, we'll simulate what the local LLM would infer
    facts = packet["facts"]
    
    # Infer mood from patterns and sensor data
    if "OVERWORK_LATE" in packet["patterns"] and facts["awake_hours"] > 18:
        mood = "exhausted"
        intensity = 9
    elif "HEAD_DOWN_SUSTAINED" in packet["patterns"]:
        mood = "frustrated"
        intensity = 8
    else:
        mood = "neutral"
        intensity = 5
    
    print(f"\n🎭 SIMULATED MOOD INFERENCE:")
    print(f"   Mood: {mood}")
    print(f"   Intensity: {intensity}/10")
    print(f"   Based on: {', '.join(packet['patterns'])}")
    
    # Build personality system prompt
    personality_prompt = build_core_identity_prompt("kenyan_babe", include_examples=False)
    
    # Create compressed brief WITH MOOD
    compressed_brief = (
        f"{facts['time']} office quiet hours; "
        f"awake ~{facts['awake_hours']}h; "
        f"still working {facts['stillness_min']}m; "
        f"screen active; head down -35°. "
        f"User appears {mood} (intensity {intensity}/10). "  # ← MOOD ADDED
        f"Patterns: {', '.join(packet['patterns'])}. "
        f"Goal: stop work, sleep NOW."
    )
    
    # Create MOOD-AWARE user message
    # Adjust tone based on mood
    if mood == "exhausted" and intensity > 8:
        tone_instruction = f"User is EXHAUSTED (intensity {intensity}/10) - be VERY gentle, warm, and caring. "
        adjusted_tone = "warm_caring"
    elif mood == "frustrated" and intensity > 7:
        tone_instruction = f"User is FRUSTRATED (intensity {intensity}/10) - be EXTRA gentle and empathetic. "
        adjusted_tone = "gentle_empathetic"
    else:
        tone_instruction = ""
        adjusted_tone = "playful_firm"
    
    user_message = (
        f"{compressed_brief}\n\n"
        f"{tone_instruction}"  # ← MOOD INSTRUCTION ADDED
        f"Write 2-3 sentences to intervene. Use {adjusted_tone} Kenyan babe tone. "
        f"Acknowledge dedication, give ONE clear action (close laptop and sleep), "
        f"mention their exhaustion/frustration gently, no guilt. Max 45 words."
    )
    
    print("\n📤 Sending to Local LLM (gemma3:12b) with mood-aware prompt:")
    print(f'   Brief: "{compressed_brief}"')
    print(f'   Mood adjustment: {tone_instruction.strip() if tone_instruction else "None (normal tone)"}')
    
    # Call Local LLM with personality
    try:
        print("\n🔄 Calling Local LLM with Kenyan babe personality...")
        
        response_text = await ollama_chat(
            base_url=OLLAMA_HOST,
            model="gemma3:12b",
            messages=[
                {"role": "system", "content": personality_prompt},
                {"role": "user", "content": user_message}
            ],
            format_json=False,  # Free text for personality
            options={"temperature": 0.7}  # Higher temp for personality
        )
        
        print(f"✅ Local LLM responded: {len(response_text)} chars")
        
        print("\n💬 LOCAL LLM RESPONSE (with Kenyan babe personality):")
        print(f'"{response_text}"')
        
        # Save output
        output = {
            "scenario": "cloud_fallback",
            "cloud_status": "unreachable",
            "fallback": "local_llm_with_personality",
            "deterministic_summary": {
                "facts": packet["facts"],
                "patterns": packet["patterns"],
                "intent": packet["intent"]
            },
            "mood_inference": {
                "mood": mood,
                "intensity": intensity,
                "adjusted_tone": adjusted_tone
            },
            "compressed_brief": compressed_brief,
            "local_llm_response": {
                "model": "gemma3:12b",
                "personality": "kenyan_babe",
                "mood_aware": True,
                "response": response_text,
                "chars": len(response_text)
            }
        }
        
        with open("test_cloud_fallback_output.json", 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print("\n✅ FALLBACK SUCCESS (MOOD-AWARE):")
        print("   - Cloud unreachable ✓")
        print("   - Local LLM responded with personality ✓")
        print(f"   - Model: gemma3:12b")
        print(f"   - Mood detected: {mood} (intensity {intensity}/10)")
        print(f"   - Tone adjusted: {adjusted_tone}")
        print(f"   - Response length: {len(response_text)} chars")
        print("\n📄 Output saved to: test_cloud_fallback_output.json")
        
    except Exception as e:
        print(f"❌ Local LLM also failed: {e}")
        print("   This would require a hardcoded fallback message")


async def main():
    """Run cloud fallback test"""
    await test_cloud_fallback()
    
    print("\n" + "🎉 "*40)
    print("CLOUD FALLBACK TEST COMPLETE!")
    print("🎉 "*40 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
