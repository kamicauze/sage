# 🏗️ Architecture Specification

## Three-Layer Architecture

**Philosophy:** Separate facts from inferences from personality

```
Layer 1: Deterministic Engine = Instruments + Logbook (defendable facts)
Layer 2: Local LLM = Copilot Commentary (mood inference, compression)
Layer 3: Cloud LLM = Cabin Crew (personality, privacy-protected)
```

---

## Layer 1: Deterministic Summary Engine

### Output Format
```json
{
  "facts": {
    "time": "02:30",
    "quiet_hours": true,
    "awake_hours": 20.0,
    "stillness_min": 95,
    "vision": {"head_pitch_deg": -35.0, "body_configuration": "seated"},
    "audio_silence_min": 95
  },
  "patterns": ["OVERWORK_LATE", "SCREEN_HYPERFOCUS"],
  "intent": "INTERVENE_SLEEP",
  "constraints": {"max_words": 45, "tone": "playful_firm", "no_guilt": true}
}
```

### 17 Patterns (Rule-Based, Defendable)

**All patterns use explicit thresholds you can defend:**
- OVERWORK_LATE: `quiet_hours=true AND awake_hours>14 AND present=true`
- SCREEN_HYPERFOCUS: `screen_active=true AND stillness>90m AND audio_silence>90m`
- etc.

### Sensor Input Types

1. **Presence & Motion** - mmWave, PIR (binary detection)
2. **Vision Geometry** - Head angles, body configuration, eye state (NO emotions)
3. **Audio Presence** - Speech detection, voice count (NO content/transcription)
4. **Time & Schedule** - Clock, commitments (highest authority)
5. **Activity Proxies** - Screen state, keyboard (low authority)

**Rule:** Sensors report what exists, not what it means.

---

## Layer 2: Local LLM (Inference)

### Purpose
1. Infer mood from sensor data (with confidence)
2. Compress context for cloud (privacy)
3. Generate mood-aware prompt for cloud

### Output Format
```json
{
  "inferences": [{
    "label": "sleep_intervention_urgent",
    "confidence": 0.92,
    "evidence": ["quiet_hours=True", "awake_hours=20.0"]
  }],
  "mood": {"inference": "exhausted", "intensity": 9},
  "compressed_brief": "02:30 quiet hours; awake 20h; exhausted (9/10); Goal: sleep NOW.",
  "ask_cloud": "User is EXHAUSTED (9/10) - be VERY gentle and caring..."
}
```

### Validation Rules
- ✅ Must cite evidence
- ✅ Must provide confidence
- ❌ No clinical labels ("depressed", "anxious disorder")
- ❌ No moral language ("lazy", "should be ashamed")

---

## Layer 3: Cloud LLM (Personality)

### Input (Compressed Only)
```
"02:30 quiet hours; awake 20h; exhausted (9/10); Goal: sleep NOW."
"User is EXHAUSTED - be VERY gentle and caring. Write in warm_caring Kenyan babe tone..."
```

### Output
```
"Aaaai, my love… I see you. That dedication is *fiti*, wallai, but look at you – 
head down, eyes tired. Close that laptop, mrembo—sleep now. Your ancestors are 
watching and saying, "Pole pole, uko sawa." ❤️"
```

### Privacy
- Cloud sees: Compressed brief (177 chars)
- Cloud never sees: Raw sensors, vision geometry, audio details, full history

---

## Mood-Aware System

### Mood Detection (Layer 2)
Local LLM infers mood from sensor data:
- exhausted (9/10) - from OVERWORK_LATE + 20h awake
- frustrated (8/10) - from head_down + high stillness
- anxious (7/10) - from erratic patterns

### Tone Adjustment
| Mood | Intensity | Adjusted Tone | Instructions |
|------|-----------|---------------|--------------|
| exhausted | 9/10 | warm_caring | "be VERY gentle, warm, and caring" |
| frustrated | 8/10 | gentle_empathetic | "be EXTRA gentle, empathetic" |
| anxious | 7/10 | reassuring_calm | "be reassuring and calming" |
| calm | 3/10 | playful_firm | (normal approach) |

### Response Adaptation
Cloud/Local LLM receives mood context and adapts language:
- Acknowledges emotional state explicitly
- Uses appropriate tone
- Avoids mismatch (playful + frustrated = bad)

---

## Sensor Specifications

### Allowed (Measurable)
- ✅ "Motion ceased 38 minutes ago"
- ✅ "Head pitch: -35°"
- ✅ "Body configuration: reclined"
- ✅ "Eyes: closed"
- ✅ "Audio silence: 95 minutes"

### NOT Allowed (Interpretive)
- ❌ "User is tired"
- ❌ "User is slouching"
- ❌ "User is stressed"

**Rule:** If you can't measure it, timestamp it, and justify it numerically → it doesn't belong in Layer 1.

---

## Fallback Strategy

When cloud is unreachable:
1. Local LLM detects mood
2. Adjusts tone accordingly
3. Generates personality response locally
4. Quality: As good or better than cloud!

**Example:**
- Cloud unavailable ✗
- Local LLM: "Aaaai, my love… I see you. look at you – head down, eyes tired..."
- Quality: Excellent ✅

---

## Test Results

### Full Flow Test
- Layer 1: 5 patterns detected ✅
- Layer 2: Mood "frustrated" (8/10) ✅
- Layer 3: Grok response mood-adapted ✅

### Fallback Test
- Cloud: Unreachable ✗
- Local fallback: Mood "exhausted" (9/10) ✅
- Response quality: Excellent ✅

---

**Status:** Production ready with real LLM integration, mood awareness, and graceful degradation.

---

## Sensor Input Specification

### Core Principle
**SENSORS REPORT WHAT EXISTS, NOT WHAT IT MEANS**

### Allowed Sensor Outputs

#### 1. Presence & Motion (mmWave, PIR)
- ✅ `presence_detected: bool`
- ✅ `motion_detected: bool`
- ✅ `stillness_duration_ms: int`

#### 2. Vision Geometry (IR cameras)
- ✅ `head_pitch_deg: float` (angle)
- ✅ `body_configuration: "seated"|"upright"|"reclined"` (geometry)
- ✅ `eyes_open: bool` (state)
- ❌ NOT "tired", "slouching", "stressed" (interpretations)

#### 3. Audio Presence (Conference mics)
- ✅ `audio_detected: bool` (presence/absence)
- ✅ `audio_multi_voice: bool` (count estimation)
- ✅ `audio_silence_min: int` (duration)
- ❌ NOT speech content, transcription, voice ID

#### 4. Time & Schedule
- ✅ `quiet_hours: bool` (23:00-07:00)
- ✅ `awake_hours: float` (duration)
- ✅ `schedule_next: object` (commitments)

#### 5. Activity Proxies
- ✅ `screen_active: bool`
- ✅ `keyboard_events: int`

### Language Rules
- ✅ "Motion ceased 38 minutes ago" (measurement)
- ❌ "User is tired" (interpretation)

### Anchor Question
> "Which sensor or measurement explicitly supports this claim?"

If answer is "interpretation" → doesn't belong in Layer 1.

