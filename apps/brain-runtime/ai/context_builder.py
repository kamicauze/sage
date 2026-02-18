"""
Self-Narrative Context Builder
Transforms raw sensor data and patterns into natural language self-awareness.

Instead of Sage receiving: {"stillness_min": 45, "patterns": ["OVERWORK_LATE"]}
She receives: "I've been watching - you haven't moved in 45 minutes and it's 2am.
              This feels like you're overworking again."

This gives Sage genuine self-awareness of what she's observing.

Now includes:
- Long-term memory recall for persistent knowledge across sessions
- Multimodal context fusion (vision + audio + presence)
"""

from datetime import datetime
import time
from typing import Dict, List, Optional, Any
from .conversation import ConversationHistory, get_conversation

# Multimodal context integration
try:
    from brain.context import get_context_builder, MultimodalContext
    MULTIMODAL_AVAILABLE = True
except ImportError:
    MULTIMODAL_AVAILABLE = False
    print("[Context] Multimodal context module not available")


# Enable/disable long-term memory recall
ENABLE_MEMORY_RECALL = True

# Memory recall mode: "always", "explicit_only", or "disabled"
# - "always": Run memory recall on every message (slower but more context-aware)
# - "explicit_only": Only recall when user asks a question or references past (faster, recommended)
# - "disabled": Never recall memory
import os
MEMORY_RECALL_MODE = os.getenv("MEMORY_RECALL_MODE", "explicit_only")


# Day names for natural language
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Pattern descriptions - how Sage perceives each pattern
PATTERN_PERCEPTIONS = {
    "OVERWORK_LATE": "You've been at this way too long, especially for this hour",
    "LONG_FOCUS_BLOCK": "You've been locked in deep focus for a while now",
    "BREAK_OVERDUE": "You really need a break - it's been too long",
    "EXTENDED_STILLNESS": "You've been very still, barely moving",
    "PROLONGED_SILENCE": "It's been quiet for a long time - no conversation",
    "SOCIAL_ISOLATION_MULTI_DAY": "I haven't heard you talk to anyone in days",
    "MEETING_IN_PROGRESS": "Sounds like you're in a meeting or call",
    "NIGHT_AUDIO_ACTIVITY": "There's activity at an unusual hour",
    "EXTENDED_RECLINED_POSTURE": "You've been reclined for quite a while",
    "EYES_CLOSED_EXTENDED": "Your eyes have been closed for a bit",
    "HEAD_DOWN_SUSTAINED": "Your head has been down for a while",
    "SCREEN_HYPERFOCUS": "You've been glued to the screen without a break",
    "SEDENTARY_PATTERN": "You haven't moved around the space in hours",
    "FATIGUE_COMPOSITE": "You're showing signs of real fatigue",
    "SLEEP_DEPRIVATION_PATTERN": "You haven't been sleeping enough lately",
    "ERRATIC_SLEEP_SCHEDULE": "Your sleep schedule has been all over the place",
    "MISSED_COMMITMENT_IMMINENT": "You might be about to miss something important",
}

# Intent to natural concern mapping
INTENT_CONCERNS = {
    "INTERVENE_SLEEP": "I'm genuinely worried about your rest",
    "ALERT_COMMITMENT": "I need to remind you about something",
    "SUGGEST_REST": "I think you need some rest",
    "SUGGEST_BREAK": "A break would do you good right now",
    "SUGGEST_MOVEMENT": "Maybe time to stretch or move around",
    "CHECK_IN": "Just checking in on you",
    "DO_NOT_DISTURB": "I'll stay quiet - you seem busy",
    "NO_ACTION": None,  # No concern to express
}


class SelfNarrativeBuilder:
    """
    Builds Sage's self-narrative - her internal understanding of the current situation.
    
    This transforms raw data into first-person observations that Sage
    can naturally incorporate into her responses.
    """
    
    def __init__(self):
        self.action_memory: List[Dict] = []  # Recent actions taken
        self.max_action_memory = 10
        
    def build_self_awareness(
        self,
        facts: Dict,
        patterns: List[str],
        intent: str,
        constraints: Dict,
        action_memory: List[Dict] = None,
        conversation: ConversationHistory = None,
        user_message: str = None
    ) -> str:
        """
        Build the complete self-awareness block for Sage.
        
        This is what Sage "knows" about the current situation,
        written in a way she can naturally understand and reference.
        
        Args:
            facts: From summary_engine (time, room, stillness, etc.)
            patterns: Detected behavioral patterns
            intent: Derived intent (SUGGEST_BREAK, etc.)
            constraints: Response constraints (tone, max_words, etc.)
            action_memory: Recent actions Sage has taken
            conversation: Current conversation history
            user_message: Current user message (for memory recall context)
            
        Returns:
            Natural language self-awareness block for the prompt
        """
        sections = []
        
        # 1. Time & Environment Awareness
        time_section = self._build_time_awareness(facts)
        if time_section:
            sections.append(time_section)
            
        # 2. Location & Presence Awareness
        location_section = self._build_location_awareness(facts)
        if location_section:
            sections.append(location_section)
            
        # 3. Observation Awareness (what I'm noticing)
        observation_section = self._build_observations(facts, patterns)
        if observation_section:
            sections.append(observation_section)
            
        # 4. My Concern (based on intent)
        concern_section = self._build_concern(intent, constraints)
        if concern_section:
            sections.append(concern_section)
            
        # 5. Recent Actions (what I've already done/suggested)
        if action_memory:
            action_section = self._build_action_memory(action_memory)
            if action_section:
                sections.append(action_section)
                
        # 6. Conversation Context (if ongoing)
        if conversation and not conversation.is_empty():
            convo_section = self._build_conversation_context(conversation)
            if convo_section:
                sections.append(convo_section)
        
        # 7. Long-term Memory Recall (what I remember about you)
        if ENABLE_MEMORY_RECALL and MEMORY_RECALL_MODE != "disabled":
            should_recall = self._should_run_memory_recall(user_message, MEMORY_RECALL_MODE)

            if should_recall:
                memory_section = self._build_memory_recall(
                    patterns=patterns,
                    user_message=user_message,
                    facts=facts
                )
                if memory_section:
                    sections.append(memory_section)

        # 8. Multimodal Context (vision + audio fusion)
        if MULTIMODAL_AVAILABLE:
            multimodal_section = self._build_multimodal_context()
            if multimodal_section:
                sections.append(multimodal_section)

        if not sections:
            return "I'm here and aware, ready to help."

        return "\n".join(sections)
    
    def _should_run_memory_recall(self, user_message: str, mode: str) -> bool:
        """
        Determine if memory recall should run based on the message content and mode.

        Args:
            user_message: User's message text
            mode: "always", "explicit_only", or "disabled"

        Returns:
            True if memory recall should run
        """
        if mode == "always":
            return True
        elif mode == "disabled":
            return False
        elif mode == "explicit_only":
            # Only recall if message seems to reference past or ask questions
            if not user_message:
                return False

            user_lower = user_message.lower()

            # Question indicators
            question_words = ["who", "what", "when", "where", "why", "how", "do you", "did i", "have i", "remember"]

            # Past reference indicators
            past_indicators = ["last time", "before", "yesterday", "earlier", "remember when", "you said", "we talked about"]

            # Check for questions or past references
            for indicator in question_words + past_indicators:
                if indicator in user_lower:
                    return True

            # Also recall if message is longer than 20 words (likely complex query)
            if len(user_message.split()) > 20:
                return True

            return False

        return False

    def _build_memory_recall(
        self,
        patterns: List[str] = None,
        user_message: str = None,
        facts: Dict = None
    ) -> str:
        """
        Build memory recall section from long-term memory.

        Retrieves relevant past conversations, facts, and preferences.
        """
        start_time = time.time()
        try:
            from brain.memory.recall import get_recall_engine

            recall = get_recall_engine()

            # Check if we have any memories at all
            if not recall.has_met_before():
                return ""  # No memories yet

            sections = []

            # 1. User identity - ALWAYS include if known
            identity_text = recall.get_identity_prompt()
            if identity_text:
                sections.append(f"Who I'm talking to: {identity_text}")

            # Extract topic from user message or patterns
            topic = None
            if user_message:
                topic = user_message[:50]
            elif patterns:
                topic = " ".join(patterns[:2])

            # 2. Get relevant memories
            memory_text = recall.recall_for_context(
                current_topic=topic,
                current_time=facts.get("time") if facts else None,
                emotional_signals=patterns,
                user_message=user_message,
                max_episodes=2,  # Keep it concise
                max_facts=3
            )

            if memory_text:
                sections.append(memory_text)

            if sections:
                return "\n" + "\n\n".join(sections)

            return ""

        except ImportError:
            return ""  # Memory module not available
        except Exception as e:
            print(f"[Context] Memory recall error: {e}")
            return ""
        finally:
            elapsed_ms = int((time.time() - start_time) * 1000)
            print(f"[Latency] memory_recall: {elapsed_ms}ms")
    
    def _build_time_awareness(self, facts: Dict) -> str:
        """Build time awareness: when it is, what kind of time."""
        time_str = facts.get("time", "")
        local_hour = facts.get("local_hour", 12)
        day_idx = facts.get("day_of_week", 0)
        is_quiet_hours = facts.get("quiet_hours", False)
        
        day_name = DAYS[day_idx] if 0 <= day_idx < 7 else ""
        
        # Time of day description
        if local_hour < 6:
            time_feel = "very late (or very early)"
        elif local_hour < 9:
            time_feel = "early morning"
        elif local_hour < 12:
            time_feel = "morning"
        elif local_hour < 14:
            time_feel = "around midday"
        elif local_hour < 17:
            time_feel = "afternoon"
        elif local_hour < 20:
            time_feel = "evening"
        elif local_hour < 23:
            time_feel = "late evening"
        else:
            time_feel = "very late at night"
        
        parts = [f"It's {time_str}"]
        if day_name:
            parts.append(f"{day_name}")
        parts.append(f"({time_feel})")
        
        if is_quiet_hours:
            parts.append("- these are quiet hours when you should be resting")
            
        return " ".join(parts) + "."
    
    def _build_location_awareness(self, facts: Dict) -> str:
        """Build location awareness: where the user is."""
        room = facts.get("room", "none")
        is_present = facts.get("present", False)
        
        if not is_present or room == "none":
            return "I don't sense you in the space right now."
            
        return f"You're in the {room}."
    
    def _build_observations(self, facts: Dict, patterns: List[str]) -> str:
        """Build observations: what I'm noticing about behavior."""
        observations = []
        
        # Stillness
        stillness_min = facts.get("stillness_min", 0)
        if stillness_min > 10:
            if stillness_min > 60:
                observations.append(f"You haven't moved in over an hour ({stillness_min} minutes)")
            elif stillness_min > 30:
                observations.append(f"You've been quite still for about {stillness_min} minutes")
            else:
                observations.append(f"You've been still for {stillness_min} minutes")
                
        # Awake hours
        awake_hours = facts.get("awake_hours", 0)
        if awake_hours > 12:
            observations.append(f"You've been awake for about {awake_hours:.0f} hours now")
        elif awake_hours > 8:
            observations.append(f"You've been up for {awake_hours:.0f} hours")
            
        # Break overdue
        break_min = facts.get("time_since_break_min")
        if break_min and break_min > 60:
            observations.append(f"It's been {break_min} minutes since your last break")
            
        # Screen activity
        if facts.get("screen_active"):
            observations.append("The screen is active")
            
        # Pattern-based observations
        for pattern in patterns:
            if pattern in PATTERN_PERCEPTIONS:
                observations.append(PATTERN_PERCEPTIONS[pattern])
                
        if not observations:
            return ""
            
        intro = "What I'm noticing:"
        bullet_points = "\n".join(f"- {obs}" for obs in observations[:5])  # Max 5
        return f"{intro}\n{bullet_points}"
    
    def _build_concern(self, intent: str, constraints: Dict) -> str:
        """Build concern expression based on derived intent."""
        concern = INTENT_CONCERNS.get(intent)
        if not concern:
            return ""
            
        tone = constraints.get("tone", "neutral")
        
        # Add tone context
        if tone == "playful_firm":
            return f"My feeling: {concern}. Time to be real with you."
        elif tone == "urgent_friendly":
            return f"My feeling: {concern}. This is important."
        elif tone == "caring":
            return f"My feeling: {concern}."
        elif tone == "gentle_nudge":
            return f"My thought: {concern}."
        elif tone == "silent":
            return ""
        else:
            return f"My sense: {concern}."
    
    def _build_action_memory(self, actions: List[Dict]) -> str:
        """Build memory of recent actions taken."""
        if not actions:
            return ""
            
        recent = actions[-3:]  # Last 3 actions
        lines = ["What I've done recently:"]
        
        for action in recent:
            action_type = action.get("type", "unknown")
            when = action.get("when", "earlier")
            detail = action.get("detail", "")
            outcome = action.get("outcome", "")
            
            if action_type == "suggestion":
                line = f"- {when}: I suggested {detail}"
                if outcome:
                    line += f" (you {outcome})"
            elif action_type == "timer":
                line = f"- {when}: I set a {detail} timer"
                if outcome:
                    line += f" ({outcome})"
            elif action_type == "check_in":
                line = f"- {when}: I checked in on you"
            else:
                line = f"- {when}: {detail}"
                
            lines.append(line)
            
        return "\n".join(lines)
    
    def _build_conversation_context(self, conversation: ConversationHistory) -> str:
        """Build context about the ongoing conversation."""
        summary = conversation.get_context_summary()

        turns = summary["turn_count"]
        duration = summary["duration_min"]

        parts = []

        if turns > 0:
            if duration > 10:
                parts.append(f"We've been talking for about {duration:.0f} minutes ({turns} exchanges)")
            elif turns > 1:
                parts.append(f"We've had {turns} exchanges so far")
            else:
                parts.append("We just started talking")

        return "Conversation context: " + "; ".join(parts) + "." if parts else ""

    def _build_multimodal_context(self) -> str:
        """
        Build multimodal context from vision, audio, and presence sensors.

        This fuses:
        - Vision: face detection, emotion, activity, detected objects
        - Audio: speaking state, tone, energy
        - Presence: room location, time in room
        """
        if not MULTIMODAL_AVAILABLE:
            return ""

        try:
            context_builder = get_context_builder()
            ctx = context_builder.get_context()

            parts = []

            # Vision context
            v = ctx.vision
            if v.face_detected:
                vision_parts = ["I can see you"]

                if v.primary_emotion and v.primary_emotion != "neutral" and v.primary_emotion != "unknown":
                    vision_parts.append(f"you look {v.primary_emotion}")

                if v.gaze_direction and v.gaze_direction != "center":
                    vision_parts.append(f"looking {v.gaze_direction}")

                if v.activity and v.activity != "unknown":
                    vision_parts.append(f"seems like you're {v.activity}")

                if v.objects_detected:
                    obj_list = ", ".join(v.objects_detected[:3])
                    vision_parts.append(f"I notice {obj_list} nearby")

                if len(vision_parts) > 1:
                    parts.append("What I see: " + ", ".join(vision_parts[1:]) + ".")

            # Audio context
            a = ctx.audio
            if a.is_speaking:
                parts.append("You're speaking right now.")
            elif a.silence_duration > 30:
                parts.append(f"It's been quiet for {int(a.silence_duration)} seconds.")

            if a.voice_energy == "low":
                parts.append("Your voice sounds tired/quiet.")
            elif a.voice_energy == "high":
                parts.append("You sound energetic.")

            # Inferred state
            if ctx.user_state and ctx.user_state != "neutral":
                parts.append(f"Overall impression: you seem {ctx.user_state}.")

            # Suggested tone (for Sage's response style)
            if ctx.suggested_tone and ctx.suggested_tone != "neutral":
                parts.append(f"(Respond with a {ctx.suggested_tone} tone)")

            if parts:
                return "Visual & Audio awareness:\n" + "\n".join(f"- {p}" for p in parts)

            return ""

        except Exception as e:
            print(f"[Context] Multimodal context error: {e}")
            return ""


def build_full_context(
    summary_packet: Dict,
    action_memory: List[Dict] = None,
    conversation: ConversationHistory = None,
    user_message: str = None
) -> str:
    """
    Convenience function to build full self-awareness context.
    
    Args:
        summary_packet: Output from SummaryEngine.generate_summary()
        action_memory: List of recent actions Sage has taken
        conversation: Current conversation history
        user_message: Current user message (for memory recall)
        
    Returns:
        Complete self-awareness block as string
    """
    builder = SelfNarrativeBuilder()
    
    return builder.build_self_awareness(
        facts=summary_packet.get("facts", {}),
        patterns=summary_packet.get("patterns", []),
        intent=summary_packet.get("intent", "NO_ACTION"),
        constraints=summary_packet.get("constraints", {}),
        action_memory=action_memory,
        conversation=conversation,
        user_message=user_message
    )


def build_minimal_context(facts: Dict) -> str:
    """
    Build minimal context for fast voice queries.
    Lighter weight than full self-awareness.
    """
    parts = []
    
    # Time
    time_str = facts.get("time", "")
    if time_str:
        parts.append(f"Time: {time_str}")
        
    # Location
    room = facts.get("room", "none")
    if room != "none":
        parts.append(f"Location: {room}")
        
    # Quick state
    if facts.get("quiet_hours"):
        parts.append("(quiet hours)")
        
    return " | ".join(parts) if parts else "Ready to help."
