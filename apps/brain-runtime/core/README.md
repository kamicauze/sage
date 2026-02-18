# 🧠 Sage Summary Engine

**Three-layer architecture for privacy-protected, mood-aware AI interactions**

---

## Quick Start

```bash
# Test full three-layer flow (real LLMs)
python3 test_three_layer_scenario.py

# Test cloud fallback
python3 test_cloud_fallback.py
```

---

## Architecture

### Layer 1: Deterministic Summary Engine
- **Facts:** 27 sensor measurements (geometry, duration, frequency)
- **Patterns:** 17 rule-based detections (all defendable)
- **Intent:** 7 priority levels (INTERVENE_SLEEP, SUGGEST_BREAK, etc.)

### Layer 2: Local LLM (Ollama gemma3:12b)
- **Mood inference:** Detects emotional state with confidence
- **Compression:** Reduces context for cloud (privacy)
- **Prompt generation:** Mood-aware instructions for cloud

### Layer 3: Cloud LLM (Grok-4)
- **Input:** Compressed brief only (177 chars)
- **Personality:** Authentic Kenyan babe
- **Fallback:** Local LLM with same personality

---

## 17 Patterns Implemented

**Critical:** OVERWORK_LATE, SLEEP_DEPRIVATION_PATTERN, MISSED_COMMITMENT_IMMINENT, FATIGUE_COMPOSITE  
**High:** BREAK_OVERDUE, SCREEN_HYPERFOCUS, EYES_CLOSED_EXTENDED, HEAD_DOWN_SUSTAINED  
**Medium:** LONG_FOCUS_BLOCK, EXTENDED_STILLNESS, SEDENTARY_PATTERN, EXTENDED_RECLINED_POSTURE  
**Low:** PROLONGED_SILENCE, SOCIAL_ISOLATION_MULTI_DAY, NIGHT_AUDIO_ACTIVITY, ERRATIC_SLEEP_SCHEDULE  
**Special:** MEETING_IN_PROGRESS (do not disturb)

---

## Mood-Aware System

The Local LLM detects mood (frustrated, exhausted, calm, etc.) and adjusts the tone:

**Example:**
- Mood: exhausted (9/10)
- Tone adjusted: playful_firm → warm_caring
- Response: "Aaaai, my love… I see you. look at you – head down, eyes tired..."

---

## Privacy Protection

Cloud receives ONLY compressed brief (177 chars):
```
"02:30 office quiet hours; awake ~20h; still working 95m; 
User appears exhausted (9/10). Goal: stop work, sleep NOW."
```

Cloud NEVER sees:
- ❌ Raw sensor timestamps
- ❌ Vision geometry details
- ❌ Audio specifics
- ❌ Full event history

---

## Files

**Core:**
- `summary_engine.py` - Main engine (558 lines)
- `test_three_layer_scenario.py` - Full test with real LLMs
- `test_cloud_fallback.py` - Fallback test

**Documentation:**
- `README.md` - This file
- `ARCHITECTURE.md` - Complete technical spec

---

## Usage

```python
from core.summary_engine import SummaryEngine

engine = SummaryEngine()
packet, briefing = engine.generate_summary(state, history)

# Output
{
    "facts": {...},           # 27 measurements
    "patterns": [...],        # Detected patterns
    "intent": "...",          # Derived intent
    "constraints": {...}      # For LLM behavior
}
```

---

## Prompt Architecture

The brain uses layered prompts to reduce per-turn token cost:
- **CORE_IDENTITY_PROMPT**: long persona + shared rules (sent once per session or on refresh).
- **MODE_PROMPT**: tiny per-turn activation (supportive/technical/quiet/homebuddy).
- **TASK/USER**: the user utterance + minimal context payload.

**Toggles:**
- **Personality**: set `DEFAULT_PERSONALITY` in `brain/.env` (`sage`, `kenyan_babe`, `martin`).
- **Mode**: auto-selected in `brain/ai/personalities.py:select_mode`, or force by passing `mode` in `meta`/`context`.
- **Examples (debug)**: set `SAGE_INCLUDE_EXAMPLES=true` to include examples; default is off.
- **Minimal prompts**: set `SAGE_PROMPT_MINIMAL=true` to send only core identity (no mode/schema).
- **Drift reset**: pass `force_persona_refresh=True` in `meta` or call `ConversationHistory.request_core_prompt_refresh()` to resend the core prompt.

---

**Status:** ✅ Production ready with real LLM integration
