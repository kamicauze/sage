"""
Phase 3: Personality Preferences Memory

Stores and recalls personality-related preferences:
- Language preferences (Sheng level, formality)
- Emotional response preferences (tender vs direct)
- Roasting tolerance
- Phrase preferences (liked/avoided)
- Time-based personality adjustments
- Emotional trajectory patterns
"""

import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import json


@dataclass
class PersonalityPreference:
    """A single personality preference learned from interactions."""
    pref_type: str              # e.g., "sheng_level", "roast_tolerance"
    value: Any                  # The preference value
    strength: float = 0.5       # How strong (0-1)
    positive_signals: int = 0   # Times user responded positively
    negative_signals: int = 0   # Times user responded negatively
    last_updated: float = field(default_factory=time.time)
    source: str = "implicit"    # "explicit" or "implicit"


@dataclass
class EmotionalPattern:
    """Tracks emotional patterns over time."""
    time_of_day: str            # "morning", "afternoon", "evening", "night"
    common_emotions: List[str]  # Most frequent emotions at this time
    preferred_tone: str         # How user prefers to be addressed then
    sample_count: int = 0       # How many samples we have


class PersonalityMemory:
    """
    Manages personality preferences in long-term memory.

    Stores:
    - Sheng level preference (how much Sheng to use)
    - Roast tolerance (can we tease the user?)
    - Tender preference (does user prefer softer responses?)
    - Phrase tracking (which phrases landed well/poorly)
    - Emotional patterns by time of day
    - Response length preferences
    """

    # Preference types we track
    PREF_TYPES = {
        "sheng_level": "How much Sheng/slang to use (0=minimal, 1=heavy)",
        "roast_tolerance": "How much playful teasing is OK (0=none, 1=full roast)",
        "tender_preference": "Preference for soft/tender responses (0=direct, 1=very tender)",
        "emoji_preference": "How many emojis to use (0=none, 1=lots)",
        "response_length": "Preferred response length (0=brief, 1=detailed)",
        "directness": "How direct vs cushioned (0=cushioned, 1=very direct)",
        "humor_style": "Humor preference (dry, playful, sarcastic, none)",
    }

    def __init__(self, memory_instance=None):
        """
        Initialize PersonalityMemory.

        Args:
            memory_instance: Optional SageMemory instance. If None, will get singleton.
        """
        self.memory = memory_instance
        self._preferences: Dict[str, PersonalityPreference] = {}
        self._emotional_patterns: Dict[str, EmotionalPattern] = {}
        self._liked_phrases: List[str] = []
        self._disliked_phrases: List[str] = []
        self._initialized = False

    def _ensure_memory(self):
        """Ensure we have a memory instance."""
        if self.memory is None:
            try:
                from brain.memory.recall import get_memory
                self.memory = get_memory()
            except ImportError:
                print("[PersonalityMemory] Warning: Could not import memory system")
                return False
        return True

    def load_from_memory(self) -> bool:
        """
        Load personality preferences from long-term memory.

        Returns:
            True if loaded successfully
        """
        if not self._ensure_memory():
            return False

        try:
            # Load preferences from sage_preferences collection
            prefs = self.memory.get_preferences(pref_type="personality")

            for pref in prefs:
                pref_type = pref.get("metadata", {}).get("sub_type", "")
                if pref_type:
                    self._preferences[pref_type] = PersonalityPreference(
                        pref_type=pref_type,
                        value=pref.get("content", ""),
                        strength=pref.get("metadata", {}).get("strength", 0.5),
                        source="memory"
                    )

            self._initialized = True
            print(f"[PersonalityMemory] Loaded {len(self._preferences)} preferences from memory")
            return True

        except Exception as e:
            print(f"[PersonalityMemory] Error loading from memory: {e}")
            return False

    def save_to_memory(self) -> bool:
        """
        Save current preferences to long-term memory.

        Returns:
            True if saved successfully
        """
        if not self._ensure_memory():
            return False

        try:
            for pref_type, pref in self._preferences.items():
                self.memory.update_preference(
                    pref_type=f"personality_{pref_type}",
                    value=json.dumps(asdict(pref)),
                    signal=pref.source,
                    strength=pref.strength
                )

            # Save liked/disliked phrases
            if self._liked_phrases:
                self.memory.update_preference(
                    pref_type="personality_liked_phrases",
                    value=json.dumps(self._liked_phrases[-20:]),  # Keep last 20
                    signal="implicit",
                    strength=0.7
                )

            if self._disliked_phrases:
                self.memory.update_preference(
                    pref_type="personality_disliked_phrases",
                    value=json.dumps(self._disliked_phrases[-20:]),
                    signal="implicit",
                    strength=0.7
                )

            print(f"[PersonalityMemory] Saved {len(self._preferences)} preferences to memory")
            return True

        except Exception as e:
            print(f"[PersonalityMemory] Error saving to memory: {e}")
            return False

    # ==================== PREFERENCE LEARNING ====================

    def learn_from_response(
        self,
        user_message: str,
        sage_response: str,
        user_feedback: str = None,
        implicit_signal: str = None
    ):
        """
        Learn personality preferences from an interaction.

        Args:
            user_message: What the user said
            sage_response: How Sage responded
            user_feedback: Explicit feedback if any ("good", "bad", etc.)
            implicit_signal: Implicit signal ("continued_conversation", "changed_topic", etc.)
        """
        # Detect language preference from user message
        sheng_level = self._detect_sheng_level(user_message)
        self._update_preference("sheng_level", sheng_level, implicit_signal or "implicit")

        # Detect if user invited roasting
        if self._contains_roast_invitation(user_message):
            self._update_preference("roast_tolerance", 0.8, "implicit_positive")

        # Detect tender signals
        if self._contains_vulnerability(user_message):
            self._update_preference("tender_preference", 0.8, "implicit_positive")

        # Track phrase success/failure
        if user_feedback == "positive" or implicit_signal == "continued_conversation":
            self._track_successful_phrases(sage_response)
        elif user_feedback == "negative" or implicit_signal == "changed_topic":
            self._track_failed_phrases(sage_response)

        # Track emotional pattern by time
        self._record_emotional_pattern(user_message)

    def _detect_sheng_level(self, text: str) -> float:
        """Detect how much Sheng the user is using."""
        sheng_words = [
            'niaje', 'poa', 'sawa', 'manze', 'fiti', 'bro', 'fam',
            'babes', 'mdogo', 'tutapanga', 'pole', 'sana', 'leo',
            'kesho', 'jana', 'niko', 'uko', 'kiplani', 'kilimani'
        ]

        text_lower = text.lower()
        word_count = len(text.split())
        if word_count == 0:
            return 0.5

        sheng_count = sum(1 for word in sheng_words if word in text_lower)

        # Calculate ratio and scale to 0-1
        ratio = sheng_count / max(word_count / 3, 1)
        return min(ratio, 1.0)

    def _contains_roast_invitation(self, text: str) -> bool:
        """Check if user is inviting playful teasing."""
        roast_signals = [
            'roast me', 'tease me', 'drag me', 'be real',
            'dont sugarcoat', "don't sugarcoat", 'be honest',
            'give it to me straight', 'no bs'
        ]
        text_lower = text.lower()
        return any(sig in text_lower for sig in roast_signals)

    def _contains_vulnerability(self, text: str) -> bool:
        """Check if user is being vulnerable/emotional."""
        vulnerability_signals = [
            'sad', 'depressed', 'crying', 'hurt', 'scared',
            'anxious', 'overwhelmed', 'lost', 'grief', 'died',
            'suicide', 'struggling', 'hard time'
        ]
        text_lower = text.lower()
        return any(sig in text_lower for sig in vulnerability_signals)

    def _update_preference(self, pref_type: str, value: Any, signal: str):
        """Update a preference based on observed signal."""
        if pref_type not in self._preferences:
            self._preferences[pref_type] = PersonalityPreference(
                pref_type=pref_type,
                value=value,
                strength=0.5
            )

        pref = self._preferences[pref_type]

        # Adjust based on signal type
        if signal == "explicit":
            pref.value = value
            pref.strength = 0.9
            pref.source = "explicit"
        elif signal in ("implicit_positive", "continued_conversation"):
            pref.positive_signals += 1
            # Blend toward observed value
            if isinstance(value, (int, float)) and isinstance(pref.value, (int, float)):
                pref.value = pref.value * 0.7 + value * 0.3
            pref.strength = min(1.0, pref.strength + 0.05)
        elif signal in ("implicit_negative", "changed_topic"):
            pref.negative_signals += 1
            pref.strength = max(0.1, pref.strength - 0.1)
        else:
            # Neutral implicit - slight blend
            if isinstance(value, (int, float)) and isinstance(pref.value, (int, float)):
                pref.value = pref.value * 0.9 + value * 0.1

        pref.last_updated = time.time()

    def _track_successful_phrases(self, response: str):
        """Track phrases from a successful response."""
        # Extract key phrases (simple heuristic - sentences with Sheng)
        import re
        sentences = re.split(r'[.!?]', response)
        for sentence in sentences:
            if len(sentence.strip()) > 10:
                # Check if sentence has personality markers
                if any(marker in sentence.lower() for marker in
                       ['pole sana', 'manze', 'babes', 'tutapanga', 'aii']):
                    if sentence.strip() not in self._liked_phrases:
                        self._liked_phrases.append(sentence.strip())

    def _track_failed_phrases(self, response: str):
        """Track phrases from a failed response."""
        import re
        sentences = re.split(r'[.!?]', response)
        for sentence in sentences:
            if len(sentence.strip()) > 10:
                if sentence.strip() not in self._disliked_phrases:
                    self._disliked_phrases.append(sentence.strip())

    def _record_emotional_pattern(self, user_message: str):
        """Record emotional pattern by time of day."""
        hour = datetime.now().hour

        if 5 <= hour < 12:
            time_slot = "morning"
        elif 12 <= hour < 17:
            time_slot = "afternoon"
        elif 17 <= hour < 21:
            time_slot = "evening"
        else:
            time_slot = "night"

        # Detect emotion from message
        emotion = self._detect_emotion(user_message)

        if time_slot not in self._emotional_patterns:
            self._emotional_patterns[time_slot] = EmotionalPattern(
                time_of_day=time_slot,
                common_emotions=[],
                preferred_tone="neutral"
            )

        pattern = self._emotional_patterns[time_slot]
        pattern.common_emotions.append(emotion)
        pattern.sample_count += 1

        # Keep only last 20 emotions per time slot
        pattern.common_emotions = pattern.common_emotions[-20:]

        # Update preferred tone based on most common emotion
        if pattern.common_emotions:
            from collections import Counter
            most_common = Counter(pattern.common_emotions).most_common(1)[0][0]
            if most_common in ('sad', 'grieving', 'overwhelmed'):
                pattern.preferred_tone = "tender"
            elif most_common in ('playful', 'happy'):
                pattern.preferred_tone = "playful"
            elif most_common in ('frustrated', 'angry'):
                pattern.preferred_tone = "calm"
            else:
                pattern.preferred_tone = "neutral"

    def _detect_emotion(self, text: str) -> str:
        """Simple emotion detection."""
        text_lower = text.lower()

        if any(w in text_lower for w in ['sad', 'down', 'depressed', 'crying']):
            return 'sad'
        elif any(w in text_lower for w in ['died', 'death', 'lost', 'grief', 'suicide']):
            return 'grieving'
        elif any(w in text_lower for w in ['overwhelmed', 'too much', 'stressed']):
            return 'overwhelmed'
        elif any(w in text_lower for w in ['angry', 'pissed', 'frustrated', 'annoyed']):
            return 'frustrated'
        elif any(w in text_lower for w in ['happy', 'excited', 'great', 'amazing']):
            return 'happy'
        elif any(w in text_lower for w in ['lol', 'haha', 'funny', '😂']):
            return 'playful'
        else:
            return 'neutral'

    # ==================== PREFERENCE RETRIEVAL ====================

    def get_preference(self, pref_type: str, default: Any = None) -> Any:
        """Get a specific preference value."""
        if pref_type in self._preferences:
            return self._preferences[pref_type].value
        return default

    def get_preference_strength(self, pref_type: str) -> float:
        """Get how confident we are in a preference."""
        if pref_type in self._preferences:
            return self._preferences[pref_type].strength
        return 0.0

    def get_all_preferences(self) -> Dict[str, Any]:
        """Get all preferences as a dict."""
        return {
            pref_type: {
                "value": pref.value,
                "strength": pref.strength,
                "positive_signals": pref.positive_signals,
                "negative_signals": pref.negative_signals
            }
            for pref_type, pref in self._preferences.items()
        }

    def get_emotional_pattern(self, time_slot: str = None) -> Optional[EmotionalPattern]:
        """Get emotional pattern for a time slot (or current time)."""
        if time_slot is None:
            hour = datetime.now().hour
            if 5 <= hour < 12:
                time_slot = "morning"
            elif 12 <= hour < 17:
                time_slot = "afternoon"
            elif 17 <= hour < 21:
                time_slot = "evening"
            else:
                time_slot = "night"

        return self._emotional_patterns.get(time_slot)

    def get_liked_phrases(self, max_count: int = 10) -> List[str]:
        """Get phrases that have worked well."""
        return self._liked_phrases[-max_count:]

    def get_disliked_phrases(self, max_count: int = 10) -> List[str]:
        """Get phrases to avoid."""
        return self._disliked_phrases[-max_count:]

    def get_personality_guidance(self) -> str:
        """
        Get personality guidance based on learned preferences.

        Returns a string that can be injected into the prompt.
        """
        guidance_parts = []

        # Sheng level
        sheng = self.get_preference("sheng_level", 0.5)
        if sheng > 0.7:
            guidance_parts.append("User prefers heavy Sheng - use lots of Nairobi slang.")
        elif sheng < 0.3:
            guidance_parts.append("User prefers minimal Sheng - mostly English with light slang.")

        # Roast tolerance
        roast = self.get_preference("roast_tolerance", 0.3)
        if roast > 0.6:
            guidance_parts.append("User enjoys playful teasing and roasting.")
        elif roast < 0.2:
            guidance_parts.append("User prefers no roasting - keep it gentle.")

        # Tender preference
        tender = self.get_preference("tender_preference", 0.5)
        if tender > 0.7:
            guidance_parts.append("User responds well to tender, soft responses.")
        elif tender < 0.3:
            guidance_parts.append("User prefers direct responses without too much softness.")

        # Emoji preference
        emoji = self.get_preference("emoji_preference", 0.5)
        if emoji > 0.7:
            guidance_parts.append("User likes emojis - use them freely.")
        elif emoji < 0.3:
            guidance_parts.append("User prefers minimal emojis.")

        # Time-based emotional pattern
        pattern = self.get_emotional_pattern()
        if pattern and pattern.sample_count >= 3:
            guidance_parts.append(
                f"At this time of day ({pattern.time_of_day}), user typically feels "
                f"{pattern.common_emotions[-1] if pattern.common_emotions else 'neutral'} - "
                f"prefer a {pattern.preferred_tone} tone."
            )

        return " ".join(guidance_parts) if guidance_parts else ""

    def get_summary(self) -> Dict:
        """Get a summary of all personality preferences."""
        return {
            "preferences": self.get_all_preferences(),
            "emotional_patterns": {
                slot: {
                    "common_emotions": pattern.common_emotions[-5:],
                    "preferred_tone": pattern.preferred_tone,
                    "sample_count": pattern.sample_count
                }
                for slot, pattern in self._emotional_patterns.items()
            },
            "liked_phrases_count": len(self._liked_phrases),
            "disliked_phrases_count": len(self._disliked_phrases),
            "initialized": self._initialized
        }


# Singleton instance
_personality_memory_instance: Optional[PersonalityMemory] = None


def get_personality_memory() -> PersonalityMemory:
    """Get or create the singleton PersonalityMemory instance."""
    global _personality_memory_instance
    if _personality_memory_instance is None:
        _personality_memory_instance = PersonalityMemory()
    return _personality_memory_instance
