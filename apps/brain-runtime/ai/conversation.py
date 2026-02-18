"""
Conversation History Manager
Maintains a sliding window of recent exchanges for context continuity.

Sage needs to remember what was just said to have coherent conversations.
This provides that short-term conversational memory.

Now integrates with long-term memory:
- Distills conversations to memory when they end
- Processes feedback signals to learn preferences
"""

import time
import uuid
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime


# Flag to enable/disable long-term memory integration
ENABLE_LONG_TERM_MEMORY = True


@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)  # intent, patterns detected, etc.


class ConversationHistory:
    """
    Sliding window conversation history.

    Features:
    - Keeps last N turns (configurable)
    - Auto-clears after silence timeout
    - Tracks conversation start time and duration
    - Tracks conversation mode (emotional, technical, playful, neutral)
    - Can be serialized for persistence
    """

    # Default settings
    DEFAULT_MAX_TURNS = 8  # Keep last 8 exchanges (16 messages)
    SILENCE_TIMEOUT_SEC = 30 * 60  # 30 minutes of silence = new conversation
    MODE_DECAY_TURNS = 5  # Turns before mode decays back to neutral

    # Conversation modes
    MODE_NEUTRAL = "neutral"
    MODE_EMOTIONAL = "emotional"
    MODE_TECHNICAL = "technical"
    MODE_PLAYFUL = "playful"

    def __init__(self, max_turns: int = DEFAULT_MAX_TURNS):
        self.max_turns = max_turns
        self.messages: List[Message] = []
        self.conversation_start: Optional[float] = None
        self.last_activity: Optional[float] = None
        self.session_id: str = str(uuid.uuid4())
        self.core_prompt_sent: bool = False
        self.force_core_refresh: bool = False

        # Conversation mode tracking
        self.mode: str = self.MODE_NEUTRAL
        self.mode_since_turn: int = 0
        self.mode_topic: Optional[str] = None  # e.g., "grief", "work_stress"
        self.recent_intents: List[str] = []  # Last 3 intents for context
        
    def add_user_message(self, content: str, metadata: Dict = None) -> None:
        """Add a user message to history."""
        self._check_timeout()
        
        now = time.time()
        if self.conversation_start is None:
            self.conversation_start = now
        self.last_activity = now
        
        self.messages.append(Message(
            role='user',
            content=content,
            timestamp=now,
            metadata=metadata or {}
        ))
        
        self._trim_history()
        
        # Process feedback signals for preference learning
        self._process_feedback(content)
        
    def add_assistant_message(self, content: str, metadata: Dict = None) -> None:
        """Add Sage's response to history."""
        now = time.time()
        self.last_activity = now
        
        self.messages.append(Message(
            role='assistant',
            content=content,
            timestamp=now,
            metadata=metadata or {}
        ))
        
        self._trim_history()
        
    def _check_timeout(self) -> None:
        """Clear history if too much time has passed since last activity."""
        if self.last_activity is None:
            return
            
        elapsed = time.time() - self.last_activity
        if elapsed > self.SILENCE_TIMEOUT_SEC:
            # This is a natural conversation end - distill to long-term memory
            self._distill_to_memory(reason="timeout")
            self._clear_internal()
            
    def _trim_history(self) -> None:
        """Keep only the last N turns (2N messages)."""
        max_messages = self.max_turns * 2
        if len(self.messages) > max_messages:
            self.messages = self.messages[-max_messages:]
    
    def _distill_to_memory(self, reason: str = "manual") -> None:
        """
        Distill current conversation to long-term memory.
        Called before clearing when conversation ends.
        """
        if not ENABLE_LONG_TERM_MEMORY:
            return
            
        if not self.messages or len(self.messages) < 2:
            return  # Nothing worth remembering
        
        try:
            from brain.memory.distiller import distill_and_store
            
            # Convert Message objects to dicts
            messages_dict = [
                {"role": msg.role, "content": msg.content, "metadata": msg.metadata}
                for msg in self.messages
            ]
            
            # Collect patterns from metadata
            patterns = []
            for msg in self.messages:
                if msg.metadata.get("patterns"):
                    patterns.extend(msg.metadata["patterns"])
            
            # Distill and store
            distill_and_store(
                messages=messages_dict,
                duration_min=self.get_conversation_duration_min(),
                patterns_detected=list(set(patterns))
            )
            
            print(f"[Conversation] Distilled to long-term memory (reason: {reason})")
            
        except ImportError:
            print("[Conversation] Long-term memory not available")
        except Exception as e:
            print(f"[Conversation] Error distilling to memory: {e}")
    
    def _clear_internal(self) -> None:
        """Internal clear without distillation."""
        self.messages = []
        self.conversation_start = None
        self.last_activity = None
        self.session_id = str(uuid.uuid4())
        self.core_prompt_sent = False
        self.force_core_refresh = False
        # Reset mode tracking
        self.mode = self.MODE_NEUTRAL
        self.mode_since_turn = 0
        self.mode_topic = None
        self.recent_intents = []
            
    def clear(self, save_to_memory: bool = True) -> None:
        """
        Clear conversation history (new conversation).
        
        Args:
            save_to_memory: If True, distill conversation to long-term memory first
        """
        if save_to_memory and self.messages:
            self._distill_to_memory(reason="manual_clear")
        
        self._clear_internal()
    
    def _process_feedback(self, user_message: str) -> None:
        """
        Process user message for feedback signals.
        Updates preferences based on implicit/explicit feedback.
        
        Only processes when there's actual feedback to learn from (has prior context).
        Skipped on first message to avoid cold-start latency.
        """
        if not ENABLE_LONG_TERM_MEMORY:
            return
        
        # Skip feedback processing on first message (no context to learn from)
        # This avoids triggering memory import on cold start
        if len(self.messages) < 2:
            return
        
        # Only process if there's a prior assistant message to learn from
        last_sage = self.get_last_assistant_message()
        if not last_sage:
            return
            
        try:
            from brain.memory.feedback import process_user_feedback
            
            # Check if Sage made a suggestion
            suggestion_made = False
            suggestion_keywords = ["should", "why don't you", "try", "maybe", "how about"]
            suggestion_made = any(kw in last_sage.lower() for kw in suggestion_keywords)
            
            # Process feedback
            updates = process_user_feedback(
                user_message=user_message,
                sage_message=last_sage,
                suggestion_made=suggestion_made
            )
            
            if updates:
                print(f"[Conversation] Learned from feedback: {len(updates)} preferences updated")
                
        except ImportError:
            pass  # Memory module not available
        except Exception as e:
            print(f"[Conversation] Error processing feedback: {e}")
        
    def get_messages(self) -> List[Dict]:
        """Get messages in LLM-ready format."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in self.messages
        ]
        
    def get_formatted_history(self) -> str:
        """
        Get conversation history as formatted text for prompt injection.
        Returns empty string if no history.
        """
        if not self.messages:
            return ""
            
        lines = []
        for msg in self.messages:
            prefix = "You" if msg.role == 'assistant' else "User"
            # Truncate very long messages
            content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
            lines.append(f"{prefix}: {content}")
            
        return "\n".join(lines)
        
    def get_last_user_message(self) -> Optional[str]:
        """Get the most recent user message."""
        for msg in reversed(self.messages):
            if msg.role == 'user':
                return msg.content
        return None
        
    def get_last_assistant_message(self) -> Optional[str]:
        """Get the most recent assistant message."""
        for msg in reversed(self.messages):
            if msg.role == 'assistant':
                return msg.content
        return None
        
    def get_conversation_duration_min(self) -> float:
        """Get how long this conversation has been going (in minutes)."""
        if self.conversation_start is None:
            return 0
        return (time.time() - self.conversation_start) / 60
        
    def get_turn_count(self) -> int:
        """Get number of complete turns (user + assistant pairs)."""
        user_count = sum(1 for m in self.messages if m.role == 'user')
        assistant_count = sum(1 for m in self.messages if m.role == 'assistant')
        return min(user_count, assistant_count)
        
    def is_empty(self) -> bool:
        """Check if there's no conversation history."""
        return len(self.messages) == 0
        
    def get_context_summary(self) -> Dict:
        """
        Get a summary of the conversation context.
        Useful for the self-narrative generator.
        """
        return {
            "turn_count": self.get_turn_count(),
            "duration_min": round(self.get_conversation_duration_min(), 1),
            "last_user_message": self.get_last_user_message(),
            "last_assistant_message": self.get_last_assistant_message(),
            "is_ongoing": not self.is_empty(),
            "session_id": self.session_id
        }

    def mark_core_prompt_sent(self) -> None:
        """Mark the core prompt as sent for this session."""
        self.core_prompt_sent = True

    def request_core_prompt_refresh(self) -> None:
        """Force a core prompt refresh on the next turn."""
        self.force_core_refresh = True

    # --- Conversation Mode Tracking ---

    def update_mode(self, user_message: str, intent_type: str = None) -> None:
        """
        Update conversation mode based on user message content.
        Called after adding a user message.
        """
        lowered = user_message.lower()
        current_turn = self.get_turn_count()

        # Track recent intents
        if intent_type:
            self.recent_intents.append(intent_type)
            if len(self.recent_intents) > 3:
                self.recent_intents = self.recent_intents[-3:]

        # Detect emotional mode triggers
        emotional_triggers = [
            # Grief/loss
            ("grief", ["died", "death", "passed away", "suicide", "funeral", "miss my",
                       "miss him", "miss her", "lost my", "grief", "mourning", "sijaheal"]),
            # Sadness/depression
            ("sadness", ["feeling sad", "i'm sad", "depressed", "lonely", "empty",
                         "can't cope", "struggling", "overwhelmed"]),
            # Anxiety/stress
            ("anxiety", ["anxious", "scared", "worried", "stressed", "panic",
                         "can't sleep", "nervous"]),
            # General emotional
            ("emotional", ["need to talk", "need to vent", "something happened",
                           "can i tell you", "hurts", "painful"]),
        ]

        for topic, keywords in emotional_triggers:
            if any(kw in lowered for kw in keywords):
                self._set_mode(self.MODE_EMOTIONAL, topic, current_turn)
                return

        # Detect technical mode triggers
        technical_triggers = ["code", "bug", "error", "implement", "refactor",
                              "function", "api", "database", "deploy", "architect"]
        if any(kw in lowered for kw in technical_triggers):
            self._set_mode(self.MODE_TECHNICAL, "coding", current_turn)
            return

        # Detect playful mode triggers
        playful_triggers = ["haha", "lol", "joke", "funny", "😂", "🤣", "kidding",
                            "just playing", "messing with you"]
        if any(kw in lowered for kw in playful_triggers):
            self._set_mode(self.MODE_PLAYFUL, None, current_turn)
            return

        # Check for mode decay (return to neutral after N turns of non-matching content)
        if self.mode != self.MODE_NEUTRAL:
            turns_in_mode = current_turn - self.mode_since_turn
            if turns_in_mode >= self.MODE_DECAY_TURNS:
                self._set_mode(self.MODE_NEUTRAL, None, current_turn)

    def _set_mode(self, mode: str, topic: Optional[str], turn: int) -> None:
        """Internal: set conversation mode."""
        if self.mode != mode:
            print(f"[Conversation] Mode shift: {self.mode} -> {mode}" +
                  (f" (topic: {topic})" if topic else ""))
        self.mode = mode
        self.mode_topic = topic
        self.mode_since_turn = turn

    def get_intent_context(self) -> Dict:
        """
        Get context for intent classification.
        This helps the intent classifier understand conversation flow.
        """
        return {
            "mode": self.mode,
            "mode_topic": self.mode_topic,
            "emotional_mode": self.mode == self.MODE_EMOTIONAL,
            "turns_in_mode": self.get_turn_count() - self.mode_since_turn,
            "recent_intents": self.recent_intents.copy(),
            "turn_count": self.get_turn_count(),
        }

    def is_emotional_context(self) -> bool:
        """Check if we're in an emotional conversation context."""
        return self.mode == self.MODE_EMOTIONAL


# Singleton instance for the main conversation
_conversation: Optional[ConversationHistory] = None


def get_conversation() -> ConversationHistory:
    """Get the shared conversation history instance."""
    global _conversation
    if _conversation is None:
        _conversation = ConversationHistory()
    return _conversation


def reset_conversation() -> ConversationHistory:
    """Reset and return fresh conversation history."""
    global _conversation
    _conversation = ConversationHistory()
    return _conversation
