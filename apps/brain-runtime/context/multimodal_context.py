#!/usr/bin/env python3
"""
Multimodal Context Builder for Sage
Fuses vision, audio, and sensor data to build rich context for LLM.

This enables responses like:
- "You look tired" + "I'm exhausted" → empathetic response
- "Holding coffee" + "good morning" → "Enjoying your coffee?"
- "Looking away" + long pause → "Everything okay?"
- "Frustrated face" + code on screen → "Stuck on something?"
"""

import time
import json
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict
from collections import deque
from enum import Enum


class ContextSignal(Enum):
    """Types of context signals"""
    # Vision
    FACE_DETECTED = "face_detected"
    FACE_LOST = "face_lost"
    EMOTION_CHANGE = "emotion_change"
    ACTIVITY_CHANGE = "activity_change"
    OBJECT_DETECTED = "object_detected"
    GAZE_CHANGE = "gaze_change"

    # Audio
    SPEECH_START = "speech_start"
    SPEECH_END = "speech_end"
    TONE_CHANGE = "tone_change"
    SILENCE_LONG = "silence_long"

    # Presence
    USER_ARRIVED = "user_arrived"
    USER_LEFT = "user_left"
    ROOM_CHANGE = "room_change"


@dataclass
class VisionContext:
    """Current vision state"""
    face_detected: bool = False
    people_count: int = 0
    primary_emotion: str = "neutral"
    emotion_confidence: float = 0.0
    activity: str = "unknown"  # working, relaxing, eating, etc.
    gaze_direction: str = "center"
    looking_at_camera: bool = False
    objects_detected: List[str] = field(default_factory=list)
    scene_description: str = ""
    last_update: float = 0


@dataclass
class AudioContext:
    """Current audio/speech state"""
    is_speaking: bool = False
    last_transcript: str = ""
    transcript_emotion: str = "neutral"  # inferred from text
    speaking_rate: str = "normal"  # slow, normal, fast
    voice_energy: str = "normal"  # low, normal, high
    silence_duration: float = 0
    last_speech_time: float = 0


@dataclass
class PresenceContext:
    """Presence and location state"""
    user_present: bool = False
    current_room: str = "unknown"
    time_in_room: float = 0
    arrived_at: float = 0
    session_duration: float = 0  # time since first interaction today


@dataclass
class TemporalContext:
    """Time-based context"""
    time_of_day: str = "day"  # morning, afternoon, evening, night
    day_of_week: str = ""
    is_work_hours: bool = False
    hours_since_last_break: float = 0
    interactions_today: int = 0


@dataclass
class MultimodalContext:
    """Complete multimodal context for LLM"""
    vision: VisionContext = field(default_factory=VisionContext)
    audio: AudioContext = field(default_factory=AudioContext)
    presence: PresenceContext = field(default_factory=PresenceContext)
    temporal: TemporalContext = field(default_factory=TemporalContext)

    # Inferred states
    user_state: str = "neutral"  # happy, focused, tired, frustrated, etc.
    engagement_level: str = "normal"  # low, normal, high
    suggested_tone: str = "neutral"  # empathetic, energetic, calm, professional

    # Recent signals
    recent_signals: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_prompt_context(self) -> str:
        """Generate context string for LLM prompt"""
        parts = []

        # Vision context
        if self.vision.face_detected:
            parts.append(f"User is present, looking {self.vision.gaze_direction}")
            if self.vision.primary_emotion != "neutral":
                parts.append(f"appears {self.vision.primary_emotion}")
            if self.vision.activity != "unknown":
                parts.append(f"currently {self.vision.activity}")
            if self.vision.objects_detected:
                parts.append(f"has {', '.join(self.vision.objects_detected[:3])} nearby")
        else:
            parts.append("User not visible")

        # Audio context
        if self.audio.last_transcript:
            if self.audio.voice_energy == "low":
                parts.append("speaking quietly/tiredly")
            elif self.audio.speaking_rate == "fast":
                parts.append("speaking quickly")

        # Presence context
        if self.presence.time_in_room > 7200:  # 2 hours
            hours = self.presence.time_in_room / 3600
            parts.append(f"has been here for {hours:.1f} hours")

        # Inferred state
        if self.user_state != "neutral":
            parts.append(f"overall seems {self.user_state}")

        return ". ".join(parts) + "." if parts else "No context available."


class MultimodalContextBuilder:
    """
    Builds and maintains multimodal context by fusing multiple inputs.

    Usage:
        builder = MultimodalContextBuilder()

        # Update from vision
        builder.update_vision(face_detected=True, emotion="happy")

        # Update from STT
        builder.update_audio(transcript="Good morning!", is_speaking=True)

        # Get context for LLM
        context = builder.get_context()
        prompt_addition = context.to_prompt_context()
    """

    # Emotion mappings for inference
    TIRED_INDICATORS = ["tired", "exhausted", "sleepy", "drained", "beat"]
    FRUSTRATED_INDICATORS = ["frustrated", "annoyed", "stuck", "ugh", "damn", "argh"]
    HAPPY_INDICATORS = ["happy", "great", "awesome", "excited", "good"]
    SAD_INDICATORS = ["sad", "down", "depressed", "upset", "bad"]

    def __init__(self):
        self.context = MultimodalContext()
        self._signal_history = deque(maxlen=50)
        self._emotion_history = deque(maxlen=10)
        self._last_break_time = time.time()
        self._session_start = time.time()

    def update_vision(
        self,
        face_detected: bool = None,
        people_count: int = None,
        emotion: str = None,
        emotion_confidence: float = None,
        activity: str = None,
        gaze_direction: str = None,
        objects: List[str] = None,
        scene_description: str = None,
    ):
        """Update vision context"""
        v = self.context.vision
        changed = False

        if face_detected is not None:
            if face_detected != v.face_detected:
                self._add_signal(
                    ContextSignal.FACE_DETECTED if face_detected else ContextSignal.FACE_LOST
                )
                changed = True
            v.face_detected = face_detected

        if people_count is not None:
            v.people_count = people_count

        if emotion is not None and emotion != v.primary_emotion:
            self._add_signal(ContextSignal.EMOTION_CHANGE, {"from": v.primary_emotion, "to": emotion})
            v.primary_emotion = emotion
            self._emotion_history.append(emotion)
            changed = True

        if emotion_confidence is not None:
            v.emotion_confidence = emotion_confidence

        if activity is not None and activity != v.activity:
            self._add_signal(ContextSignal.ACTIVITY_CHANGE, {"from": v.activity, "to": activity})
            v.activity = activity
            changed = True

        if gaze_direction is not None:
            if gaze_direction != v.gaze_direction:
                self._add_signal(ContextSignal.GAZE_CHANGE, {"direction": gaze_direction})
            v.gaze_direction = gaze_direction
            v.looking_at_camera = gaze_direction == "center"

        if objects is not None:
            new_objects = set(objects) - set(v.objects_detected)
            for obj in new_objects:
                self._add_signal(ContextSignal.OBJECT_DETECTED, {"object": obj})
            v.objects_detected = objects

        if scene_description is not None:
            v.scene_description = scene_description

        v.last_update = time.time()

        if changed:
            self._infer_user_state()

    def update_audio(
        self,
        is_speaking: bool = None,
        transcript: str = None,
        speaking_rate: str = None,
        voice_energy: str = None,
    ):
        """Update audio/speech context"""
        a = self.context.audio

        if is_speaking is not None:
            if is_speaking and not a.is_speaking:
                self._add_signal(ContextSignal.SPEECH_START)
                a.last_speech_time = time.time()
            elif not is_speaking and a.is_speaking:
                self._add_signal(ContextSignal.SPEECH_END)
            a.is_speaking = is_speaking

        if transcript is not None:
            a.last_transcript = transcript
            a.transcript_emotion = self._infer_emotion_from_text(transcript)

        if speaking_rate is not None:
            a.speaking_rate = speaking_rate

        if voice_energy is not None:
            if voice_energy != a.voice_energy:
                self._add_signal(ContextSignal.TONE_CHANGE, {"energy": voice_energy})
            a.voice_energy = voice_energy

        # Update silence duration
        if not a.is_speaking and a.last_speech_time > 0:
            a.silence_duration = time.time() - a.last_speech_time
            if a.silence_duration > 30:  # 30 seconds of silence
                self._add_signal(ContextSignal.SILENCE_LONG)
        else:
            a.silence_duration = 0

        self._infer_user_state()

    def update_presence(
        self,
        user_present: bool = None,
        room: str = None,
    ):
        """Update presence context"""
        p = self.context.presence
        now = time.time()

        if user_present is not None:
            if user_present and not p.user_present:
                self._add_signal(ContextSignal.USER_ARRIVED)
                p.arrived_at = now
            elif not user_present and p.user_present:
                self._add_signal(ContextSignal.USER_LEFT)
            p.user_present = user_present

        if room is not None and room != p.current_room:
            self._add_signal(ContextSignal.ROOM_CHANGE, {"from": p.current_room, "to": room})
            p.current_room = room
            p.arrived_at = now

        # Update time tracking
        if p.user_present and p.arrived_at > 0:
            p.time_in_room = now - p.arrived_at

        p.session_duration = now - self._session_start

    def update_temporal(self):
        """Update time-based context"""
        t = self.context.temporal
        now = time.localtime()

        hour = now.tm_hour
        if 5 <= hour < 12:
            t.time_of_day = "morning"
        elif 12 <= hour < 17:
            t.time_of_day = "afternoon"
        elif 17 <= hour < 21:
            t.time_of_day = "evening"
        else:
            t.time_of_day = "night"

        days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        t.day_of_week = days[now.tm_wday]

        t.is_work_hours = now.tm_wday < 5 and 9 <= hour < 18

        t.hours_since_last_break = (time.time() - self._last_break_time) / 3600

    def record_break(self):
        """Record that user took a break"""
        self._last_break_time = time.time()

    def _add_signal(self, signal: ContextSignal, data: Dict = None):
        """Add a context signal to history"""
        entry = {
            "signal": signal.value,
            "timestamp": time.time(),
            "data": data or {}
        }
        self._signal_history.append(entry)

        # Keep recent signals in context (last 5)
        self.context.recent_signals = list(self._signal_history)[-5:]

    def _infer_emotion_from_text(self, text: str) -> str:
        """Infer emotion from transcript text"""
        text_lower = text.lower()

        if any(word in text_lower for word in self.TIRED_INDICATORS):
            return "tired"
        if any(word in text_lower for word in self.FRUSTRATED_INDICATORS):
            return "frustrated"
        if any(word in text_lower for word in self.HAPPY_INDICATORS):
            return "happy"
        if any(word in text_lower for word in self.SAD_INDICATORS):
            return "sad"

        return "neutral"

    def _infer_user_state(self):
        """Infer overall user state from all signals"""
        v = self.context.vision
        a = self.context.audio

        # Combine vision emotion + text emotion + voice energy
        signals = []

        if v.primary_emotion and v.primary_emotion != "neutral":
            signals.append(v.primary_emotion)

        if a.transcript_emotion and a.transcript_emotion != "neutral":
            signals.append(a.transcript_emotion)

        if a.voice_energy == "low":
            signals.append("tired")
        elif a.voice_energy == "high":
            signals.append("energetic")

        # Determine dominant state
        if "frustrated" in signals or "angry" in signals:
            self.context.user_state = "frustrated"
            self.context.suggested_tone = "empathetic"
        elif "tired" in signals or "sad" in signals:
            self.context.user_state = "tired"
            self.context.suggested_tone = "gentle"
        elif "happy" in signals or "energetic" in signals:
            self.context.user_state = "positive"
            self.context.suggested_tone = "upbeat"
        elif v.activity == "working" and v.primary_emotion == "neutral":
            self.context.user_state = "focused"
            self.context.suggested_tone = "professional"
        else:
            self.context.user_state = "neutral"
            self.context.suggested_tone = "neutral"

        # Engagement level
        if v.looking_at_camera and a.is_speaking:
            self.context.engagement_level = "high"
        elif not v.face_detected or a.silence_duration > 60:
            self.context.engagement_level = "low"
        else:
            self.context.engagement_level = "normal"

    def get_context(self) -> MultimodalContext:
        """Get current multimodal context"""
        self.update_temporal()
        return self.context

    def get_context_for_llm(self) -> str:
        """Get context formatted for LLM prompt injection"""
        ctx = self.get_context()
        return ctx.to_prompt_context()

    def should_proactively_speak(self) -> Optional[str]:
        """
        Determine if Sage should proactively say something.
        Returns suggested prompt or None.
        """
        ctx = self.context

        # User just arrived
        recent = [s["signal"] for s in ctx.recent_signals[-3:]]
        if ContextSignal.USER_ARRIVED.value in recent:
            return f"User just arrived in {ctx.presence.current_room}. Greet them appropriately for {ctx.temporal.time_of_day}."

        # User seems frustrated
        if ctx.user_state == "frustrated":
            return "User seems frustrated. Offer help or acknowledge their frustration."

        # Long silence after speech
        if ctx.audio.silence_duration > 60 and ctx.vision.face_detected:
            return "User has been quiet for a while but is still present. Check if they need anything."

        # Been working too long
        if ctx.temporal.hours_since_last_break > 2 and ctx.vision.activity == "working":
            return "User has been working for over 2 hours without a break. Gently suggest a break."

        return None


# Singleton instance for easy access
_context_builder: Optional[MultimodalContextBuilder] = None

def get_context_builder() -> MultimodalContextBuilder:
    """Get or create the global context builder"""
    global _context_builder
    if _context_builder is None:
        _context_builder = MultimodalContextBuilder()
    return _context_builder


if __name__ == "__main__":
    # Demo
    builder = MultimodalContextBuilder()

    # Simulate: User arrives, looks frustrated, says "I'm so tired"
    print("=== Simulating multimodal context ===\n")

    builder.update_presence(user_present=True, room="office")
    print("1. User arrived in office")

    builder.update_vision(
        face_detected=True,
        emotion="frustrated",
        activity="working",
        gaze_direction="center"
    )
    print("2. Vision: frustrated, working, looking at camera")

    builder.update_audio(
        is_speaking=True,
        transcript="I'm so tired of this bug",
        voice_energy="low"
    )
    print("3. Audio: 'I'm so tired of this bug', low energy")

    print("\n=== Generated Context ===")
    ctx = builder.get_context()
    print(f"User state: {ctx.user_state}")
    print(f"Suggested tone: {ctx.suggested_tone}")
    print(f"Engagement: {ctx.engagement_level}")
    print(f"\nLLM context: {ctx.to_prompt_context()}")

    proactive = builder.should_proactively_speak()
    if proactive:
        print(f"\nProactive prompt: {proactive}")
