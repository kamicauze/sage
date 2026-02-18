# Phase 3: Memory-Driven Personality System

## Overview

Phase 3 adds long-term memory to Sage's personality system. The brain now learns and remembers user preferences over time, adapting its personality to match what works best for each user.

## What Was Implemented

### 1. PersonalityMemory Class
**File:** [brain/memory/personality_prefs.py](brain/memory/personality_prefs.py)

Stores and recalls personality-related preferences:
- **Sheng level** - How much Nairobi slang to use (0=minimal, 1=heavy)
- **Roast tolerance** - Can we playfully tease? (0=none, 1=full roast)
- **Tender preference** - Soft vs direct responses (0=direct, 1=tender)
- **Emoji preference** - How many emojis (0=none, 1=lots)
- **Response length** - Brief vs detailed (0=brief, 1=detailed)
- **Directness** - Cushioned vs straight talk
- **Liked/disliked phrases** - Which phrases land well or poorly
- **Emotional patterns** - User's typical mood by time of day

### 2. PersonalityEngine Integration
**File:** [brain/ai/personality_engine.py](brain/ai/personality_engine.py)

New methods added:
- `_ensure_memory()` - Lazily loads PersonalityMemory
- `_apply_memory_preferences()` - Applies loaded prefs to state
- `learn_from_interaction()` - Learns from each exchange
- `detect_user_feedback()` - Detects explicit positive/negative signals
- `save_preferences()` - Persists preferences to memory

### 3. Advisor Integration
**File:** [brain/ai/advisor.py](brain/ai/advisor.py)

Learning happens automatically after each response:
- Detects explicit feedback ("thanks", "asante", "no", "wrong")
- Treats continued conversation as positive signal
- Tracks successful/failed phrases
- Updates preference strengths over time

### 4. Shutdown Hooks
**File:** [brain/main.py](brain/main.py)

Preferences are saved:
- On graceful shutdown (SIGINT/SIGTERM)
- On main loop exit
- Before brain stops

---

## How It Works

### Learning Flow

```
User Message → Advisor
      ↓
PersonalityEngine.process_user_message()
      ↓
Detect emotion, cultural context, conversation depth
      ↓
Generate response with personality injection
      ↓
PersonalityEngine.detect_user_feedback()
      ↓
If feedback detected → learn_from_interaction()
      ↓
PersonalityMemory.learn_from_response()
      ↓
Update preference strengths
```

### Preference Signals

| Signal | Type | Effect |
|--------|------|--------|
| "thanks", "asante", "poa" | explicit_positive | Strengthen current preferences |
| "no", "wrong", "hapana" | explicit_negative | Weaken current preferences |
| User keeps talking | continued_conversation | Slight positive reinforcement |
| User changes topic | changed_topic | Slight negative signal |

### Time-Based Patterns

The system tracks emotional patterns by time of day:
- **Morning** (5am-12pm)
- **Afternoon** (12pm-5pm)
- **Evening** (5pm-9pm)
- **Night** (9pm-5am)

Over time, it learns things like:
- "User is usually stressed in the evening"
- "User prefers tender responses at night"
- "User is playful in the morning"

---

## Configuration

No new environment variables required. Phase 3 uses the existing memory system.

---

## Testing

### Run the Test Script:
```bash
./test_phase3_memory.sh
```

### What to Watch For in Logs:

**On Startup:**
```
[PersonalityEngine] Loaded preferences from memory
```

**During Conversation:**
```
[PersonalityEngine] Learning from interaction: signal=continued_conversation
[PersonalityEngine] Learning from interaction: signal=explicit_positive
```

**On Shutdown:**
```
[Brain] Personality preferences saved
```

### Manual Testing:

1. **Train Sheng preference:**
   ```bash
   mosquitto_pub -t "sage/voice/transcript" -m "niaje fam, uko fiti?"
   mosquitto_pub -t "sage/voice/transcript" -m "poa sana, manze"
   ```

2. **Send positive feedback:**
   ```bash
   mosquitto_pub -t "sage/voice/transcript" -m "asante sana, you get me"
   ```

3. **Stop brain and restart:**
   ```bash
   # Press Ctrl+C in brain terminal
   # Look for: [Brain] Personality preferences saved

   # Restart
   ./sage brain
   # Look for: [PersonalityEngine] Loaded preferences from memory
   ```

4. **Verify preferences are applied:**
   ```bash
   mosquitto_pub -t "sage/voice/transcript" -m "how are you?"
   # Should respond with learned Sheng level
   ```

---

## Prompt Injection

The system injects memory-based guidance into the prompt:

```
[From memory] User prefers heavy Sheng - use lots of Nairobi slang.
User enjoys playful teasing and roasting.
At this time of day (evening), user typically feels stressed - prefer a calm tone.
```

---

## Files Changed

| File | Changes |
|------|---------|
| [brain/memory/personality_prefs.py](brain/memory/personality_prefs.py) | NEW - PersonalityMemory class |
| [brain/ai/personality_engine.py](brain/ai/personality_engine.py) | Added memory integration, learning |
| [brain/ai/advisor.py](brain/ai/advisor.py) | Added automatic learning after responses |
| [brain/main.py](brain/main.py) | Added shutdown hooks for saving |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Sage Brain                              │
│                                                              │
│  ┌──────────────┐     ┌──────────────────────┐              │
│  │   Advisor    │────▶│  PersonalityEngine   │              │
│  │  (advise())  │     │                      │              │
│  └──────────────┘     │  - process_user_msg  │              │
│                       │  - get_prompt_inject │              │
│                       │  - enrich_response   │              │
│                       │  - learn_from_inter  │              │
│                       │  - detect_feedback   │              │
│                       └──────────┬───────────┘              │
│                                  │                           │
│                                  ▼                           │
│                       ┌──────────────────────┐              │
│                       │  PersonalityMemory   │              │
│                       │                      │              │
│                       │  - preferences       │              │
│                       │  - emotional_patterns│              │
│                       │  - liked_phrases     │              │
│                       │  - disliked_phrases  │              │
│                       └──────────┬───────────┘              │
│                                  │                           │
│                                  ▼                           │
│                       ┌──────────────────────┐              │
│                       │    SageMemory        │              │
│                       │   (ChromaDB)         │              │
│                       └──────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

## Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Preferences loaded on restart | Yes | Check logs for load message |
| Learning signals detected | 80%+ | Count learning log messages |
| Preference influence | Visible | Compare responses before/after training |
| Shutdown save | Yes | Check logs on Ctrl+C |

---

## Known Limitations

1. **Cold start** - First few interactions won't have learned preferences
2. **Memory persistence** - Requires ChromaDB to be working
3. **Signal detection** - Some feedback may be missed if phrased unusually
4. **Conflicting signals** - Mixed signals may cause slow convergence

---

## Next Steps (Future Enhancements)

1. **Voice tone analysis** - Detect mood from voice characteristics
2. **Explicit preference setting** - "Sage, use more Sheng with me"
3. **Per-topic preferences** - Different style for work vs personal topics
4. **Preference decay** - Slowly forget old preferences over time
5. **Multi-user support** - Different preferences per detected user

---

## Quick Reference

### Start Brain with Phase 3:
```bash
export DEFAULT_PERSONALITY=kenyan_babe
export SAGE_DISABLE_QUIET_HOURS=true
./sage brain
```

### Test Memory System:
```bash
./test_phase3_memory.sh
```

### Check Current Preferences (Python):
```python
from brain.ai.personality_engine import get_personality_engine
engine = get_personality_engine()
print(engine.get_state_summary())
```

---

**Implementation Date:** 2026-01-14
**Status:** Complete, ready for testing
