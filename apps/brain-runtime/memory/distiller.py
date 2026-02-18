"""
Memory Distiller
Extracts memorable content from conversations for long-term storage.

Converts raw conversation history into:
- Summaries: What happened in this conversation
- Facts: New things learned about the user
- Emotional arc: How the user's mood changed
- Preferences: Signals about communication preferences
"""

import re
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime


# Keywords that suggest facts worth remembering
FACT_INDICATORS = [
    # Personal info
    r"my (?:name is|cat|dog|pet|wife|husband|partner|kid|child|children|mom|dad|family)",
    r"i (?:work|live|am|have|own|like|love|hate|prefer|need)",
    r"i'm (?:a|an|from|in|at)",
    # Events/schedules
    r"(?:tomorrow|next week|on friday|this weekend) i (?:have|need|will)",
    r"i have (?:a|an) (?:meeting|presentation|deadline|appointment|interview)",
    # Preferences
    r"i (?:don't|do not) like",
    r"i (?:always|never|usually|prefer)",
]

# High-priority identity patterns - extract immediately
# Format: (pattern, fact_type, use_ignorecase)
# Note: Name patterns that rely on capitalization should set use_ignorecase=False
IDENTITY_PATTERNS = [
    # Name patterns - "am X" requires capital letter to avoid false positives
    (r"(?:my name is|i am|i'm)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)\b(?!\s+(?:a|an|the|from|in|at|going|doing|feeling|building|your))", "name", True),
    (r"\bam\s+([A-Z][a-z]+(?:\s+[A-Za-z]+)?)\b", "name", False),  # "am Martin Ngigi" - requires capital
    (r"(?:mimi ni|jina langu ni|naitwa)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", "name", True),  # Swahili
    # Nickname patterns - capture each nickname separately
    (r"(?:call me|they call me|people call me)\s+([A-Za-z]+)\b", "nickname", True),
    (r"(?:bwana|baba|mama|mzee)\s+([A-Za-z]+)", "nickname", True),  # Kenyan honorifics
    # Professional identity - expanded list
    (r"(?:i am|i'm|am)\s+(?:a|an)\s+(software engineer|developer|programmer|designer|architect|pilot|student pilot|doctor|lawyer|teacher|student|engineer|manager|founder|ceo|cto|builder|creator)", "profession", True),
    (r"(?:,\s*as|as a|as an)\s+(software engineer|developer|programmer|pilot|student pilot|engineer|builder|creator)", "profession", True),
    (r"(?:i work as|my job is|my profession is)\s+(?:a|an)?\s*(\w+(?:\s+\w+)?)", "profession", True),
    (r"(?:into|interested in|working in)\s+(real[- ]?estate|tech|finance|aviation|software)", "profession", True),
    # Creator/owner relationship - more flexible
    (r"(?:i am|i'm|am)\s+(?:your|the)\s*(creator|owner|maker|developer|builder)", "relationship", True),
    (r"your\s+(creator|owner|maker|developer|builder)", "relationship", True),
    (r"(?:i built|i created|i made|i'm building|am building)\s+(?:you|this|sage)", "relationship", True),
    # Location
    (r"(?:i live in|i'm from|i'm based in|located in)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)", "location", True),
    # Age/Birthday - handle "turned 30 jana"
    (r"(?:i am|i'm|just turned|turned|turning)\s+(\d{1,2})(?:\s+(?:years old|jana|yesterday))?", "age", True),
    (r"(?:my birthday is|born on)\s+(.+?)(?:\.|$)", "birthday", True),
]

# Guardrails to avoid storing placeholder/question values as identity.
INVALID_IDENTITY_VALUES = {
    "name",
    "my name",
    "nani",      # Swahili: who?
    "nini",      # Swahili: what?
    "gani",      # Swahili: which?
    "who",
    "what",
    "unknown",
    "none",
    "null",
}

INVALID_NAME_TOKENS = {"or", "and", "au", "na"}

SELF_IDENTITY_QUESTION_PATTERNS = [
    r"\bwho am i\b",
    r"\bwhat(?:'s| is) my name\b",
    r"\bmimi ni nani\b",
    r"\bjina langu ni nani\b",
    r"\bnaitwa nani\b",
]

# Keywords suggesting emotional states
EMOTIONAL_KEYWORDS = {
    "stressed": ["stressed", "anxious", "worried", "overwhelmed", "busy", "crazy", "hectic"],
    "tired": ["tired", "exhausted", "sleepy", "drained", "burnt out", "burnout"],
    "happy": ["happy", "excited", "great", "awesome", "good", "wonderful", "amazing"],
    "sad": ["sad", "down", "depressed", "upset", "disappointed", "lonely"],
    "frustrated": ["frustrated", "annoyed", "angry", "irritated", "mad"],
    "calm": ["calm", "relaxed", "peaceful", "chill", "okay", "fine", "alright"]
}

# Preference signals
PREFERENCE_SIGNALS = {
    "explicit_like": [
        r"i like (?:it )?when you",
        r"i love (?:it )?when you",
        r"that was (?:helpful|great|perfect|exactly what i needed)"
    ],
    "explicit_dislike": [
        r"i (?:don't|do not) like (?:it )?when you",
        r"stop (?:doing|being|saying)",
        r"don't (?:do|be|say) that",
        r"that's (?:annoying|not helpful|too much)"
    ],
    "avoid_phrase": [
        r"(?:don't|do not|stop) (?:say|saying|use|using) ['\"]?(\w+)['\"]?",
        r"(?:don't|do not) say ['\"]?([^'\"]+?)['\"]? (?:again|anymore|tena)",
        r"(?:please|tafadhali) (?:don't|do not) use ['\"]?(\w+)['\"]?",
        r"usiseme ['\"]?(\w+)['\"]? (?:again|tena|anymore)",
        r"si nilikushow (?:si lazima )? ?you say ['\"]?(\w+)['\"]?"
    ],
    "implicit_positive": [
        r"(?:haha|lol|lmao|😂|😊|❤️)",
        r"thanks|thank you|cheers",
        r"you're (?:right|the best|amazing|helpful)"
    ],
    "implicit_negative": [
        r"(?:whatever|nevermind|forget it|ok fine)",
        r"(?:not now|later|busy)",
        r"(?:sigh|ugh|😒|🙄)"
    ]
}


class MemoryDistiller:
    """
    Extracts memorable content from conversations.
    
    Takes raw conversation messages and produces:
    - A summary suitable for episodic memory
    - Facts learned about the user
    - Emotional arc (mood changes)
    - Preference signals
    """
    
    def __init__(self):
        self.fact_patterns = [re.compile(p, re.IGNORECASE) for p in FACT_INDICATORS]
        self.preference_patterns = {
            signal_type: [re.compile(p, re.IGNORECASE) for p in patterns]
            for signal_type, patterns in PREFERENCE_SIGNALS.items()
        }
    
    def distill_conversation(
        self,
        messages: List[Dict],
        duration_min: float = 0,
        patterns_detected: List[str] = None
    ) -> Dict:
        """
        Distill a conversation into memorable components.
        
        Args:
            messages: List of {"role": "user"/"assistant", "content": str}
            duration_min: How long the conversation lasted
            patterns_detected: Behavioral patterns detected during conversation
            
        Returns:
            {
                "should_remember": bool,
                "summary": str,
                "facts_learned": [str],
                "emotional_arc": str,
                "topics": [str],
                "preference_signals": [{"type": str, "content": str}],
                "metadata": {...}
            }
        """
        if not messages:
            return {"should_remember": False}
        
        # Extract user messages
        user_messages = [m["content"] for m in messages if m.get("role") == "user"]
        assistant_messages = [m["content"] for m in messages if m.get("role") == "assistant"]
        all_text = " ".join(user_messages)
        
        # 1. Extract facts
        facts = self._extract_facts(user_messages)
        
        # 2. Detect emotional arc
        emotional_arc = self._detect_emotional_arc(user_messages)
        
        # 3. Extract topics
        topics = self._extract_topics(all_text)
        
        # 4. Detect preference signals
        preference_signals = self._detect_preference_signals(user_messages)
        
        # 5. Generate summary
        summary = self._generate_summary(
            user_messages, 
            assistant_messages,
            emotional_arc,
            topics
        )
        
        # 6. Decide if worth remembering
        should_remember = self._should_remember(
            messages, facts, emotional_arc, preference_signals, duration_min
        )
        
        return {
            "should_remember": should_remember,
            "summary": summary,
            "facts_learned": facts,
            "emotional_arc": emotional_arc,
            "topics": topics,
            "preference_signals": preference_signals,
            "metadata": {
                "turn_count": len(user_messages),
                "duration_min": duration_min,
                "patterns_detected": patterns_detected or [],
                "timestamp": time.time(),
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        }
    
    def _extract_facts(self, user_messages: List[str]) -> List[str]:
        """Extract potential facts from user messages."""
        facts = []
        
        for msg in user_messages:
            # Check each pattern
            for pattern in self.fact_patterns:
                matches = pattern.findall(msg)
                if matches:
                    # Extract the sentence containing the match
                    sentences = re.split(r'[.!?]', msg)
                    for sentence in sentences:
                        if pattern.search(sentence):
                            fact = sentence.strip()
                            if fact and len(fact) > 10:
                                # Clean up and normalize
                                fact = self._clean_fact(fact)
                                if fact:
                                    facts.append(fact)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_facts = []
        for fact in facts:
            fact_lower = fact.lower()
            if fact_lower not in seen:
                seen.add(fact_lower)
                unique_facts.append(fact)
        
        return unique_facts[:5]  # Max 5 facts per conversation
    
    def _clean_fact(self, fact: str) -> str:
        """Clean and normalize a fact string."""
        # Remove extra whitespace
        fact = " ".join(fact.split())
        
        # Capitalize first letter
        if fact:
            fact = fact[0].upper() + fact[1:]
        
        # Ensure it ends with punctuation
        if fact and fact[-1] not in ".!?":
            fact += "."
        
        return fact
    
    def _detect_emotional_arc(self, user_messages: List[str]) -> str:
        """Detect how the user's emotional state changed."""
        if not user_messages:
            return ""
        
        def detect_emotion(text: str) -> Optional[str]:
            text_lower = text.lower()
            for emotion, keywords in EMOTIONAL_KEYWORDS.items():
                if any(kw in text_lower for kw in keywords):
                    return emotion
            return None
        
        # Check first third and last third of messages
        first_portion = user_messages[:max(1, len(user_messages)//3)]
        last_portion = user_messages[-max(1, len(user_messages)//3):]
        
        start_emotions = [detect_emotion(m) for m in first_portion]
        end_emotions = [detect_emotion(m) for m in last_portion]
        
        # Get most common emotion in each portion
        start_emotion = max(set(filter(None, start_emotions)), key=start_emotions.count) if any(start_emotions) else None
        end_emotion = max(set(filter(None, end_emotions)), key=end_emotions.count) if any(end_emotions) else None
        
        if start_emotion and end_emotion and start_emotion != end_emotion:
            return f"{start_emotion} -> {end_emotion}"
        elif start_emotion:
            return start_emotion
        elif end_emotion:
            return end_emotion
        else:
            return "neutral"
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract main topics from conversation."""
        # Simple keyword extraction (could be enhanced with NLP)
        topics = []
        
        topic_keywords = {
            "work": ["work", "job", "office", "meeting", "project", "deadline", "boss", "colleague"],
            "health": ["sleep", "tired", "exercise", "sick", "headache", "doctor", "health"],
            "relationships": ["friend", "family", "partner", "wife", "husband", "mom", "dad"],
            "coding": ["code", "bug", "feature", "api", "function", "error", "debug"],
            "home": ["home", "house", "room", "kitchen", "bedroom", "living room"],
            "schedule": ["tomorrow", "meeting", "appointment", "deadline", "calendar"],
            "mood": ["feel", "feeling", "stressed", "happy", "sad", "anxious", "excited"]
        }
        
        text_lower = text.lower()
        for topic, keywords in topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)
        
        return topics[:3]  # Max 3 topics
    
    def _detect_preference_signals(self, user_messages: List[str]) -> List[Dict]:
        """Detect signals about user preferences."""
        signals = []

        for msg in user_messages:
            for signal_type, patterns in self.preference_patterns.items():
                for pattern in patterns:
                    match = pattern.search(msg)
                    if match:
                        signal_data = {
                            "type": signal_type,
                            "content": msg[:100]  # Truncate
                        }

                        # For "avoid_phrase" type, extract the specific phrase/word
                        if signal_type == "avoid_phrase" and match.groups():
                            # Extract the captured group (the phrase to avoid)
                            avoided_phrase = match.group(1) if match.groups() else None
                            if avoided_phrase:
                                signal_data["avoided_phrase"] = avoided_phrase.strip()

                        signals.append(signal_data)
                        break  # One signal per message per type

        return signals
    
    def _generate_summary(
        self,
        user_messages: List[str],
        assistant_messages: List[str],
        emotional_arc: str,
        topics: List[str]
    ) -> str:
        """Generate a natural language summary of the conversation."""
        if not user_messages:
            return ""
        
        # Build summary components
        parts = []
        
        # Topic context
        if topics:
            parts.append(f"Talked about {', '.join(topics)}")
        
        # Emotional context
        if emotional_arc and emotional_arc != "neutral":
            if "->" in emotional_arc:
                parts.append(f"User's mood shifted from {emotional_arc}")
            else:
                parts.append(f"User seemed {emotional_arc}")
        
        # Key user statement (first substantive message)
        for msg in user_messages:
            if len(msg) > 20:
                # Truncate and clean
                key_msg = msg[:150].strip()
                if not key_msg.endswith(('.', '!', '?')):
                    key_msg += "..."
                parts.append(f'User said: "{key_msg}"')
                break
        
        # Combine
        if parts:
            return ". ".join(parts) + "."
        else:
            return f"Brief exchange with {len(user_messages)} messages."
    
    def _should_remember(
        self,
        messages: List[Dict],
        facts: List[str],
        emotional_arc: str,
        preference_signals: List[Dict],
        duration_min: float
    ) -> bool:
        """
        Decide if this conversation is worth storing in long-term memory.
        
        We remember conversations that:
        - Contain new facts about the user
        - Show significant emotional change
        - Have preference signals
        - Are substantial (not just "hi" / "ok")
        """
        # Has facts = definitely remember
        if facts:
            return True
        
        # Has preference signals = remember
        if preference_signals:
            return True
        
        # Significant emotional arc = remember
        if emotional_arc and "->" in emotional_arc:
            return True
        
        # Long conversation = remember
        if duration_min > 5 or len(messages) > 6:
            return True
        
        # Check for substantive content
        user_text = " ".join(m["content"] for m in messages if m.get("role") == "user")
        if len(user_text) > 200:
            return True
        
        return False


def distill_and_store(
    messages: List[Dict],
    duration_min: float = 0,
    patterns_detected: List[str] = None
):
    """
    Convenience function to distill and store a conversation.
    
    Called when a conversation ends to extract and persist memories.
    """
    from .sage_memory import get_memory
    
    distiller = MemoryDistiller()
    result = distiller.distill_conversation(
        messages=messages,
        duration_min=duration_min,
        patterns_detected=patterns_detected
    )
    
    if not result["should_remember"]:
        print("[Distiller] Conversation not significant enough to remember")
        return None
    
    memory = get_memory()
    
    # Store episodic memory
    start_mood = None
    end_mood = None
    if result["emotional_arc"]:
        if "->" in result["emotional_arc"]:
            parts = result["emotional_arc"].split("->")
            start_mood = parts[0].strip()
            end_mood = parts[1].strip()
        else:
            start_mood = result["emotional_arc"]
            end_mood = result["emotional_arc"]
    
    episode_id = memory.remember_conversation(
        summary=result["summary"],
        emotional_arc=result["emotional_arc"],
        topics=result["topics"],
        user_mood_start=start_mood,
        user_mood_end=end_mood,
        duration_min=duration_min,
        turn_count=result["metadata"]["turn_count"]
    )
    
    # Store learned facts
    for fact in result["facts_learned"]:
        # Determine category
        category = "general"
        for topic in result["topics"]:
            if topic in ["work", "coding"]:
                category = "work"
                break
            elif topic in ["health"]:
                category = "health"
                break
            elif topic in ["relationships"]:
                category = "personal"
                break
        
        memory.learn_fact(
            fact=fact,
            category=category,
            source="conversation",
            confidence=0.7
        )
    
    # Process preference signals
    for signal in result["preference_signals"]:
        signal_type = signal["type"]
        content = signal["content"]
        
        if "like" in signal_type:
            pref_type = "communication_style"
            if "humor" in content.lower() or "haha" in content.lower():
                pref_type = "humor"
            
            memory.update_preference(
                pref_type=pref_type,
                value=content,
                signal=signal_type,
                strength=0.7 if "explicit" in signal_type else 0.5
            )
    
    print(f"[Distiller] Stored conversation with {len(result['facts_learned'])} facts")
    return episode_id


def extract_identity_realtime(message: str) -> List[Dict]:
    """
    Extract high-priority identity information from a single message in real-time.

    Called during conversation to immediately capture identity facts.
    Returns list of identity facts found.

    Example:
        extract_identity_realtime("I am Martin Ngigi, a software engineer")
        -> [{"type": "name", "value": "Martin Ngigi"}, {"type": "profession", "value": "software engineer"}]
    """
    identity_facts = []
    seen_values = set()  # Deduplicate
    lowered_message = message.lower()
    asks_identity_question = any(
        re.search(pattern, lowered_message) for pattern in SELF_IDENTITY_QUESTION_PATTERNS
    )

    for pattern, fact_type, use_ignorecase in IDENTITY_PATTERNS:
        flags = re.IGNORECASE if use_ignorecase else 0
        matches = re.findall(pattern, message, flags)
        for match in matches:
            if isinstance(match, tuple):
                # Handle multiple capture groups
                for m in match:
                    if m and len(m.strip()) > 1:
                        value = m.strip()
                        value_norm = value.lower().strip(".,!?\"'`")
                        if fact_type in {"name", "nickname"}:
                            if asks_identity_question:
                                continue
                            if value_norm in INVALID_IDENTITY_VALUES:
                                continue
                            if fact_type == "name":
                                parts = [p for p in value_norm.split() if p]
                                if any(part in INVALID_NAME_TOKENS for part in parts):
                                    continue
                        key = (fact_type, value.lower())
                        if key not in seen_values:
                            seen_values.add(key)
                            identity_facts.append({
                                "type": fact_type,
                                "value": value
                            })
            elif match and len(match.strip()) > 1:
                value = match.strip()
                value_norm = value.lower().strip(".,!?\"'`")
                if fact_type in {"name", "nickname"}:
                    if asks_identity_question:
                        continue
                    if value_norm in INVALID_IDENTITY_VALUES:
                        continue
                    if fact_type == "name":
                        parts = [p for p in value_norm.split() if p]
                        if any(part in INVALID_NAME_TOKENS for part in parts):
                            continue
                key = (fact_type, value.lower())
                if key not in seen_values:
                    seen_values.add(key)
                    identity_facts.append({
                        "type": fact_type,
                        "value": value
                    })

    return identity_facts


def store_identity_facts(identity_facts: List[Dict]) -> int:
    """
    Store identity facts immediately to long-term memory.

    Args:
        identity_facts: List of {"type": str, "value": str} dicts

    Returns:
        Number of facts stored
    """
    if not identity_facts:
        return 0

    try:
        from .sage_memory import get_memory
        memory = get_memory()

        stored = 0
        for fact in identity_facts:
            fact_type = fact["type"]
            value = fact["value"]

            # Format as a natural language fact
            if fact_type == "name":
                fact_text = f"User's name is {value}"
            elif fact_type == "nickname":
                fact_text = f"User goes by the nickname {value}"
            elif fact_type == "profession":
                fact_text = f"User is a {value}"
            elif fact_type == "relationship":
                fact_text = f"User is the {value} of Sage"
            elif fact_type == "location":
                fact_text = f"User is from/lives in {value}"
            elif fact_type == "age":
                fact_text = f"User is {value} years old"
            elif fact_type == "birthday":
                fact_text = f"User's birthday is {value}"
            else:
                fact_text = f"User's {fact_type}: {value}"

            # Store with high confidence for identity facts
            memory.learn_fact(
                fact=fact_text,
                category="identity",
                source="direct_disclosure",
                confidence=0.95
            )
            stored += 1
            print(f"[Identity] Stored: {fact_text}")

        return stored

    except Exception as e:
        print(f"[Identity] Error storing facts: {e}")
        return 0


def process_message_for_identity(message: str) -> int:
    """
    One-shot function to extract and store identity from a message.

    Call this during conversation processing when a user message
    contains potential identity information.

    Returns number of identity facts stored.
    """
    facts = extract_identity_realtime(message)
    if facts:
        return store_identity_facts(facts)
    return 0
