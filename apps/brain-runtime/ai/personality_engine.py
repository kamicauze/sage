"""
PersonalityEngine - Phase 2 Deep Personality System

Centralizes all personality logic and provides:
1. State tracking (conversation depth, emotional trajectory, cultural context)
2. Dynamic personality adaptation based on user signals
3. Response enrichment for personality consistency
4. Memory-driven personality preferences
5. Cultural context auto-detection (Sheng patterns)
"""

import os
import re
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from brain.memory.personality_prefs import PersonalityMemory


class EmotionalState(Enum):
    """User's detected emotional state."""
    NEUTRAL = "neutral"
    SAD = "sad"
    FRUSTRATED = "frustrated"
    PLAYFUL = "playful"
    OVERWHELMED = "overwhelmed"
    GRIEVING = "grieving"
    ANXIOUS = "anxious"
    HAPPY = "happy"


class CulturalMode(Enum):
    """How much cultural flavor to inject."""
    MINIMAL = "minimal"      # Mostly English, occasional Sheng
    MODERATE = "moderate"    # Natural code-switching
    FULL = "full"           # Heavy Sheng, full Nairobi energy


@dataclass
class PersonalityState:
    """Tracks the current personality state across the conversation."""
    # Conversation depth
    turn_count: int = 0
    conversation_start: float = field(default_factory=time.time)

    # Emotional tracking
    current_emotion: EmotionalState = EmotionalState.NEUTRAL
    emotion_history: List[EmotionalState] = field(default_factory=list)
    emotion_intensity: float = 0.5  # 0-1 scale

    # Cultural context
    cultural_mode: CulturalMode = CulturalMode.MODERATE
    sheng_count: int = 0  # How many Sheng phrases user has used
    user_language_style: str = "mixed"  # "english", "sheng", "mixed"

    # Personality adaptation
    roast_mode: bool = False  # User has invited playful roasting
    tender_mode: bool = False  # User needs extra gentleness
    direct_mode: bool = False  # User prefers straight talk

    # Memory-driven preferences (loaded from long-term memory)
    preferred_phrases: List[str] = field(default_factory=list)
    avoided_phrases: List[str] = field(default_factory=list)

    def get_conversation_depth(self) -> str:
        """Returns conversation depth level."""
        if self.turn_count <= 2:
            return "opening"  # Still warming up
        elif self.turn_count <= 5:
            return "engaged"  # Getting into it
        elif self.turn_count <= 10:
            return "deep"     # Full personality unlocked
        else:
            return "intimate" # Maximum trust/openness


class PersonalityEngine:
    """
    Central hub for personality management.

    Responsibilities:
    1. Track conversation state and emotional trajectory
    2. Detect cultural context from user messages
    3. Adapt personality parameters dynamically
    4. Enrich responses with personality markers
    5. Load/save personality preferences from memory
    """

    # Sheng detection patterns
    SHENG_PATTERNS = [
        r'\bniaje\b', r'\bpoa\b', r'\bsawa\b', r'\bmanze\b', r'\bfiti\b',
        r'\buko\b', r'\btutapanga\b', r'\bpole\s*sana\b', r'\bsi\s+uko\b',
        r'\bbro\b', r'\bfam\b', r'\bbabes?\b', r'\bmdogo\b', r'\bmrembo\b',
        r'\bkiplani\b', r'\bkilimani\b', r'\bwesti\b', r'\brongai\b',
        r'\bdakika\b', r'\bkesho\b', r'\bleo\b', r'\bjana\b', r'\bsasa\b',
        r'\bniko\b', r'\bwewe\b', r'\byeye\b', r'\bsisi\b', r'\bwao\b',
        r'\bhii\b', r'\bhiyo\b', r'\bkitu\b', r'\bmtu\b', r'\bwatu\b',
    ]

    # Emotional keywords
    EMOTION_KEYWORDS = {
        EmotionalState.SAD: [
            'sad', 'down', 'depressed', 'crying', 'cry', 'tears', 'hurt',
            'pain', 'lost', 'empty', 'lonely', 'alone', 'miss', 'grief'
        ],
        EmotionalState.FRUSTRATED: [
            'frustrated', 'angry', 'pissed', 'annoyed', 'fed up', 'tired of',
            'hate', 'sucks', 'damn', 'shit', 'fuck', 'ugh', 'argh'
        ],
        EmotionalState.PLAYFUL: [
            'lol', 'lmao', 'haha', 'funny', 'joke', 'tease', 'roast',
            '😂', '🤣', '😅', '😜', '😏'
        ],
        EmotionalState.OVERWHELMED: [
            'overwhelmed', 'too much', 'cant cope', "can't handle", 'drowning',
            'stressed', 'anxiety', 'panic', 'everything', 'breaking'
        ],
        EmotionalState.GRIEVING: [
            'died', 'death', 'passed away', 'lost', 'suicide', 'cancer',
            'funeral', 'gone', 'rip', 'heaven', 'memorial'
        ],
        EmotionalState.ANXIOUS: [
            'anxious', 'worried', 'scared', 'fear', 'nervous', 'panic',
            'what if', 'cant sleep', "can't sleep", 'racing thoughts'
        ],
        EmotionalState.HAPPY: [
            'happy', 'excited', 'great', 'amazing', 'wonderful', 'blessed',
            'grateful', 'good news', 'celebrate', '🎉', '✨', '❤️'
        ],
    }

    # Personality enrichment phrases by emotion
    ENRICHMENT_PHRASES = {
        EmotionalState.SAD: {
            'opening': ['Aii, pole sana', 'Babes...', 'Manze...'],
            'closing': ['❤️', '✨', 'Tutapanga.', 'I\'m here.'],
            'mid': ['si ndio?', 'you know?', 'sawa?'],
        },
        EmotionalState.FRUSTRATED: {
            'opening': ['Aii!', 'Mahn...', 'Okay okay...'],
            'closing': ['Tutapanga.', '💪', 'We got this.'],
            'mid': ['seriously', 'for real', 'manze'],
        },
        EmotionalState.PLAYFUL: {
            'opening': ['Ayy!', 'Niaje!', 'Oya!'],
            'closing': ['😂', '✨', '💅'],
            'mid': ['manze', 'bro', 'fam'],
        },
        EmotionalState.NEUTRAL: {
            'opening': ['Sawa', 'Okay', 'Alright'],
            'closing': ['✨', 'Tutapanga.'],
            'mid': ['you know', 'si ndio'],
        },
    }

    def __init__(self, default_personality: str = "kenyan_babe"):
        self.personality = default_personality
        self.state = PersonalityState()
        self._last_user_message = ""
        self._last_response = ""
        self._personality_memory: Optional["PersonalityMemory"] = None
        self._memory_loaded = False

    def _ensure_memory(self) -> bool:
        """Lazily load PersonalityMemory to avoid circular imports."""
        if self._personality_memory is not None:
            return True

        try:
            from brain.memory.personality_prefs import get_personality_memory
            self._personality_memory = get_personality_memory()

            # Load preferences from long-term memory
            if not self._memory_loaded:
                self._personality_memory.load_from_memory()
                self._apply_memory_preferences()
                self._memory_loaded = True
                print("[PersonalityEngine] Loaded preferences from memory")

            return True
        except ImportError as e:
            print(f"[PersonalityEngine] Warning: Could not import PersonalityMemory: {e}")
            return False
        except Exception as e:
            print(f"[PersonalityEngine] Error loading memory: {e}")
            return False

    def _apply_memory_preferences(self):
        """Apply loaded memory preferences to state."""
        if not self._personality_memory:
            return

        # Load liked/disliked phrases
        self.state.preferred_phrases = self._personality_memory.get_liked_phrases(max_count=15)
        self.state.avoided_phrases = self._personality_memory.get_disliked_phrases(max_count=15)

        # Apply mode preferences
        roast_tolerance = self._personality_memory.get_preference("roast_tolerance", 0.3)
        if roast_tolerance > 0.6:
            self.state.roast_mode = True

        tender_pref = self._personality_memory.get_preference("tender_preference", 0.5)
        if tender_pref > 0.7:
            self.state.tender_mode = True

        directness = self._personality_memory.get_preference("directness", 0.5)
        if directness > 0.7:
            self.state.direct_mode = True

        # Apply cultural mode from memory
        sheng_level = self._personality_memory.get_preference("sheng_level", 0.5)
        if sheng_level > 0.7:
            self.state.cultural_mode = CulturalMode.FULL
        elif sheng_level < 0.3:
            self.state.cultural_mode = CulturalMode.MINIMAL

    def process_user_message(self, message: str) -> Dict:
        """
        Process a user message and update personality state.

        Returns dict with:
        - emotion: Detected emotional state
        - cultural_score: How Sheng-heavy the message is (0-1)
        - recommended_mode: Suggested personality mode
        - enrichment_hints: Suggested enrichment for response
        """
        # Ensure memory is loaded on first message
        self._ensure_memory()

        self._last_user_message = message
        self.state.turn_count += 1

        # Detect emotion
        emotion, intensity = self._detect_emotion(message)
        self.state.current_emotion = emotion
        self.state.emotion_intensity = intensity
        self.state.emotion_history.append(emotion)

        # Detect cultural context
        cultural_score = self._detect_cultural_context(message)
        self._update_cultural_mode(cultural_score)

        # Update personality modes
        self._update_personality_modes(message, emotion)

        # Get enrichment hints
        enrichment = self._get_enrichment_hints(emotion)

        return {
            "emotion": emotion.value,
            "emotion_intensity": intensity,
            "cultural_score": cultural_score,
            "cultural_mode": self.state.cultural_mode.value,
            "conversation_depth": self.state.get_conversation_depth(),
            "turn_count": self.state.turn_count,
            "roast_mode": self.state.roast_mode,
            "tender_mode": self.state.tender_mode,
            "enrichment_hints": enrichment,
        }

    def _detect_emotion(self, message: str) -> Tuple[EmotionalState, float]:
        """Detect emotional state from message."""
        message_lower = message.lower()

        # Check each emotion category
        emotion_scores = {}
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            if score > 0:
                emotion_scores[emotion] = score

        if not emotion_scores:
            return EmotionalState.NEUTRAL, 0.5

        # Get highest scoring emotion
        best_emotion = max(emotion_scores, key=emotion_scores.get)
        max_score = emotion_scores[best_emotion]

        # Calculate intensity (0.5-1.0 based on keyword count)
        intensity = min(0.5 + (max_score * 0.1), 1.0)

        # Grieving always takes priority if detected
        if EmotionalState.GRIEVING in emotion_scores:
            return EmotionalState.GRIEVING, 1.0

        # Overwhelmed + sad = higher intensity sad
        if EmotionalState.OVERWHELMED in emotion_scores and EmotionalState.SAD in emotion_scores:
            return EmotionalState.SAD, 1.0

        return best_emotion, intensity

    def _detect_cultural_context(self, message: str) -> float:
        """
        Detect how much Sheng/cultural context is in the message.
        Returns score from 0.0 (pure English) to 1.0 (heavy Sheng).
        """
        message_lower = message.lower()

        matches = 0
        for pattern in self.SHENG_PATTERNS:
            if re.search(pattern, message_lower):
                matches += 1
                self.state.sheng_count += 1

        # Calculate score based on matches vs message length
        words = len(message.split())
        if words == 0:
            return 0.0

        # Score is matches normalized, with bonus for consecutive Sheng
        base_score = min(matches / max(words / 3, 1), 1.0)

        # Bonus if user has been consistently using Sheng
        history_bonus = min(self.state.sheng_count / 10, 0.3)

        return min(base_score + history_bonus, 1.0)

    def _update_cultural_mode(self, cultural_score: float):
        """Update cultural mode based on detected score."""
        if cultural_score >= 0.5:
            self.state.cultural_mode = CulturalMode.FULL
            self.state.user_language_style = "sheng"
        elif cultural_score >= 0.2:
            self.state.cultural_mode = CulturalMode.MODERATE
            self.state.user_language_style = "mixed"
        else:
            self.state.cultural_mode = CulturalMode.MINIMAL
            self.state.user_language_style = "english"

    def _update_personality_modes(self, message: str, emotion: EmotionalState):
        """Update special personality modes based on signals."""
        message_lower = message.lower()

        # Roast mode: User invites playful teasing
        roast_signals = ['roast', 'tease', 'drag me', 'be real', 'dont sugarcoat', 'be honest']
        if any(sig in message_lower for sig in roast_signals):
            self.state.roast_mode = True

        # Tender mode: User needs extra gentleness
        if emotion in (EmotionalState.GRIEVING, EmotionalState.SAD, EmotionalState.OVERWHELMED):
            self.state.tender_mode = True
            self.state.roast_mode = False  # Never roast when tender

        # Direct mode: User wants straight talk
        direct_signals = ['just tell me', 'straight up', 'no bs', 'be direct', 'bottom line']
        if any(sig in message_lower for sig in direct_signals):
            self.state.direct_mode = True

    def _get_enrichment_hints(self, emotion: EmotionalState) -> Dict:
        """Get enrichment hints for response generation."""
        phrases = self.ENRICHMENT_PHRASES.get(emotion, self.ENRICHMENT_PHRASES[EmotionalState.NEUTRAL])

        # Adjust based on cultural mode
        if self.state.cultural_mode == CulturalMode.FULL:
            # Heavy Sheng
            return {
                "opening_options": phrases['opening'],
                "closing_options": phrases['closing'],
                "mid_options": phrases['mid'],
                "emoji_encouraged": True,
                "sheng_level": "high",
            }
        elif self.state.cultural_mode == CulturalMode.MODERATE:
            # Natural mix
            return {
                "opening_options": phrases['opening'][:1],  # Just first option
                "closing_options": phrases['closing'],
                "mid_options": phrases['mid'][:1],
                "emoji_encouraged": True,
                "sheng_level": "medium",
            }
        else:
            # Minimal Sheng
            return {
                "opening_options": [],
                "closing_options": phrases['closing'][-1:],  # Just emoji
                "mid_options": [],
                "emoji_encouraged": emotion != EmotionalState.NEUTRAL,
                "sheng_level": "low",
            }

    def enrich_response(self, response: str) -> str:
        """
        Enrich a response with personality markers if needed.

        This is a post-processing step that can add:
        - Opening phrases if missing
        - Closing emojis if missing
        - Mid-sentence Sheng if appropriate
        """
        if not response:
            return response

        self._last_response = response
        enriched = response

        # Skip enrichment if response already has good personality markers
        has_opening = any(
            response.lower().startswith(phrase.lower())
            for phrases in self.ENRICHMENT_PHRASES.values()
            for phrase in phrases.get('opening', [])
        )
        has_emoji = bool(re.search(r'[\U0001F300-\U0001F9FF]', response))
        has_sheng = any(
            re.search(pattern, response.lower())
            for pattern in self.SHENG_PATTERNS[:10]  # Check first 10
        )

        # Calculate personality score
        personality_score = (
            (0.3 if has_opening else 0) +
            (0.3 if has_emoji else 0) +
            (0.4 if has_sheng else 0)
        )

        # If personality score is low and we're in moderate+ cultural mode, enrich
        if personality_score < 0.5 and self.state.cultural_mode != CulturalMode.MINIMAL:
            hints = self._get_enrichment_hints(self.state.current_emotion)

            # Do not auto-prepend greeting/opening markers.
            # This caused repetitive "new conversation" vibes mid-chat.

            # Add closing emoji if missing and encouraged
            if not has_emoji and hints['emoji_encouraged']:
                closing_options = hints['closing_options']
                emoji_options = [c for c in closing_options if re.search(r'[\U0001F300-\U0001F9FF]', c)]
                if emoji_options:
                    enriched = f"{enriched} {emoji_options[0]}"

        return enriched

    def get_prompt_injection(self) -> str:
        """
        Get additional prompt text to inject based on current state.

        This provides dynamic guidance to the LLM based on:
        - Conversation depth
        - Emotional trajectory
        - Cultural context
        - Special modes (roast, tender, direct)
        - Memory-driven preferences (Phase 3)
        """
        injections = []

        # Phase 3: Memory-driven guidance (highest priority)
        if self._personality_memory:
            memory_guidance = self._personality_memory.get_personality_guidance()
            if memory_guidance:
                injections.append(f"[From memory] {memory_guidance}")

        # Conversation depth guidance
        depth = self.state.get_conversation_depth()
        if depth == "opening":
            injections.append("This is early in the conversation. Be warm but not overwhelming.")
        elif depth in ("deep", "intimate"):
            injections.append("You've been talking for a while. Feel free to be more open and personal.")

        # Emotional trajectory
        if len(self.state.emotion_history) >= 3:
            recent = self.state.emotion_history[-3:]
            if all(e == EmotionalState.SAD for e in recent):
                injections.append("User has been consistently sad. Prioritize comfort over solutions.")
            elif EmotionalState.PLAYFUL in recent and EmotionalState.SAD in recent:
                injections.append("User's mood is shifting. Match their energy transitions.")

        # Cultural mode
        if self.state.cultural_mode == CulturalMode.FULL:
            injections.append("User is using heavy Sheng. Match their energy with full Nairobi flavor.")
        elif self.state.cultural_mode == CulturalMode.MINIMAL:
            injections.append("User prefers English. Use minimal Sheng, mostly English.")

        # Special modes
        if self.state.roast_mode:
            injections.append("User invited roasting. You can tease and be playfully direct.")
        if self.state.tender_mode:
            injections.append("User needs tenderness. Be extra gentle and validating.")
        if self.state.direct_mode:
            injections.append("User wants directness. Skip the fluff, be straight up.")

        # Emotion-specific
        if self.state.current_emotion == EmotionalState.GRIEVING:
            injections.append("User is dealing with loss. Handle with utmost care and respect.")
        elif self.state.current_emotion == EmotionalState.OVERWHELMED:
            injections.append("User is overwhelmed. Help them focus on one thing at a time.")

        return " ".join(injections) if injections else ""

    def learn_from_interaction(
        self,
        user_message: str,
        sage_response: str,
        implicit_signal: str = None
    ):
        """
        Phase 3: Learn from an interaction to improve future responses.

        Args:
            user_message: What the user said
            sage_response: How Sage responded
            implicit_signal: One of:
                - "continued_conversation": User kept talking (positive)
                - "changed_topic": User abruptly changed topic (negative)
                - "silence": User went silent (neutral/negative)
                - "explicit_positive": User said thanks/good/etc
                - "explicit_negative": User expressed displeasure
        """
        if not self._ensure_memory():
            return

        self._personality_memory.learn_from_response(
            user_message=user_message,
            sage_response=sage_response,
            implicit_signal=implicit_signal
        )

        # Log learning event
        print(f"[PersonalityEngine] Learning from interaction: signal={implicit_signal}")

    def detect_user_feedback(self, message: str) -> Optional[str]:
        """
        Detect explicit feedback signals in user message.

        Returns:
            - "explicit_positive": User expressed approval
            - "explicit_negative": User expressed displeasure
            - None: No explicit feedback detected
        """
        message_lower = message.lower()

        # Positive signals
        positive_signals = [
            'thanks', 'thank you', 'good', 'nice', 'love it', 'perfect',
            'exactly', 'yes', 'helpful', 'awesome', 'great', 'amazing',
            'asante', 'poa', 'sawa sawa', 'fiti', 'nice one', 'you get me'
        ]
        if any(sig in message_lower for sig in positive_signals):
            return "explicit_positive"

        # Negative signals
        negative_signals = [
            'no', 'wrong', 'not what i', "that's not", 'stop', 'dont',
            "don't", 'bad', 'annoying', 'weird', 'too much', 'less',
            'hapana', 'acha', 'si hivyo', 'mbaya', 'nah', 'bruh no'
        ]
        if any(sig in message_lower for sig in negative_signals):
            return "explicit_negative"

        return None

    def save_preferences(self):
        """Save current preferences to long-term memory."""
        if self._personality_memory:
            self._personality_memory.save_to_memory()
            print("[PersonalityEngine] Preferences saved to memory")

    def reset_conversation(self):
        """Reset state for a new conversation."""
        self.state = PersonalityState()

    def load_preferences_from_memory(self, memory_data: Dict):
        """Load user preferences from long-term memory."""
        if not memory_data:
            return

        # Load preferred phrases
        if 'preferred_phrases' in memory_data:
            self.state.preferred_phrases = memory_data['preferred_phrases']

        # Load avoided phrases
        if 'avoided_phrases' in memory_data:
            self.state.avoided_phrases = memory_data['avoided_phrases']

        # Load default modes
        if memory_data.get('prefers_roasting'):
            self.state.roast_mode = True
        if memory_data.get('prefers_tenderness'):
            self.state.tender_mode = True
        if memory_data.get('prefers_directness'):
            self.state.direct_mode = True

    def get_state_summary(self) -> Dict:
        """Get a summary of current personality state for logging/debugging."""
        return {
            "personality": self.personality,
            "turn_count": self.state.turn_count,
            "emotion": self.state.current_emotion.value,
            "emotion_intensity": self.state.emotion_intensity,
            "cultural_mode": self.state.cultural_mode.value,
            "conversation_depth": self.state.get_conversation_depth(),
            "roast_mode": self.state.roast_mode,
            "tender_mode": self.state.tender_mode,
            "direct_mode": self.state.direct_mode,
            "sheng_count": self.state.sheng_count,
        }


# Singleton instance
_engine_instance: Optional[PersonalityEngine] = None


def get_personality_engine() -> PersonalityEngine:
    """Get or create the singleton PersonalityEngine instance."""
    global _engine_instance
    if _engine_instance is None:
        default_personality = os.getenv("DEFAULT_PERSONALITY", "kenyan_babe")
        _engine_instance = PersonalityEngine(default_personality)
    return _engine_instance


def reset_personality_engine():
    """Reset the personality engine (e.g., for new conversation)."""
    global _engine_instance
    if _engine_instance:
        _engine_instance.reset_conversation()
