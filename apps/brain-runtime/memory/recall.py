"""
Recall Engine
Retrieves relevant memories for building context-aware responses.

Searches across:
- Episodic memories (past conversations)
- Semantic facts (learned information)
- Preferences (communication style)

Returns natural language memory blocks for prompt injection.
"""

import time
import re
from typing import List, Dict, Optional
from datetime import datetime

INVALID_IDENTITY_NAMES = {
    "nani",
    "who",
    "what",
    "unknown",
    "none",
    "null",
    "name",
    "my name",
}
INVALID_NAME_TOKENS = {"or", "and", "au", "na"}


class RecallEngine:
    """
    Retrieves relevant memories for context building.
    
    Given the current situation (time, topic, emotional state),
    finds memories that would help Sage respond better.
    """
    
    def __init__(self, memory=None):
        self.memory = memory
        
    def _get_memory(self):
        """Lazy load memory instance."""
        if self.memory is None:
            from .sage_memory import get_memory
            self.memory = get_memory()
        return self.memory
    
    def recall_for_context(
        self,
        current_topic: str = None,
        current_time: str = None,
        emotional_signals: List[str] = None,
        user_message: str = None,
        max_episodes: int = 3,
        max_facts: int = 5
    ) -> str:
        """
        Recall memories relevant to the current context.
        
        Args:
            current_topic: What the user is talking about
            current_time: Current time of day
            emotional_signals: Detected emotional patterns
            user_message: The user's current message
            max_episodes: Max episodic memories to recall
            max_facts: Max facts to recall
            
        Returns:
            Natural language memory block for prompt injection
        """
        memory = self._get_memory()
        sections = []
        
        # Build query from context
        query = self._build_query(current_topic, user_message, emotional_signals)
        
        # 1. Recall relevant episodes
        if query:
            episodes = memory.recall_episodes(query, n_results=max_episodes)
            episode_text = self._format_episodes(episodes)
            if episode_text:
                sections.append(episode_text)
        
        # 2. Recall relevant facts
        facts = self._recall_relevant_facts(query, max_facts)
        fact_text = self._format_facts(facts)
        if fact_text:
            sections.append(fact_text)
        
        # 3. Get preferences
        preferences = memory.get_preferences()
        pref_text = self._format_preferences(preferences)
        if pref_text:
            sections.append(pref_text)
        
        if not sections:
            return ""
        
        return "\n\n".join(sections)
    
    def _build_query(
        self,
        topic: str = None,
        message: str = None,
        emotions: List[str] = None
    ) -> str:
        """Build a semantic search query from context."""
        parts = []
        
        if topic:
            parts.append(topic)
        
        if message:
            # Extract key phrases from message
            # Take first 100 chars as query
            parts.append(message[:100])
        
        if emotions:
            parts.extend(emotions[:2])  # Max 2 emotions
        
        return " ".join(parts) if parts else None
    
    def _recall_relevant_facts(self, query: str, max_facts: int) -> List[Dict]:
        """Recall facts relevant to the query."""
        memory = self._get_memory()
        
        if query:
            # Semantic search for relevant facts
            facts = memory.recall_facts(query=query, n_results=max_facts)
        else:
            # Get high-confidence facts
            facts = memory.recall_facts(n_results=max_facts, min_confidence=0.7)
        
        return facts
    
    def _format_episodes(self, episodes: List[Dict]) -> str:
        """Format episodic memories into natural language."""
        if not episodes:
            return ""
        
        lines = ["Past conversations I remember:"]
        
        for ep in episodes:
            meta = ep.get("metadata", {})
            date = meta.get("date", "")
            time_of_day = meta.get("time", "")
            summary = ep.get("content", "")
            emotional_arc = meta.get("emotional_arc", "")
            
            # Build episode description
            when = ""
            if date:
                # Calculate relative time
                when = self._relative_date(date)
            
            line = f"- {when}: {summary}"
            if emotional_arc and emotional_arc != "neutral":
                line += f" (mood: {emotional_arc})"
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def _format_facts(self, facts: List[Dict]) -> str:
        """Format facts into natural language."""
        if not facts:
            return ""
        
        lines = ["What I know about you:"]
        
        for fact in facts:
            content = fact.get("content", "")
            meta = fact.get("metadata", {})
            confidence = meta.get("confidence", 0.5)
            
            # Only include facts we're reasonably confident about
            if confidence >= 0.5:
                lines.append(f"- {content}")
        
        if len(lines) == 1:  # Only header, no facts
            return ""
        
        return "\n".join(lines)
    
    def _format_preferences(self, preferences: List[Dict]) -> str:
        """Format preferences into natural language."""
        if not preferences:
            return ""
        
        # Group preferences by type
        strong_prefs = []
        
        for pref in preferences:
            meta = pref.get("metadata", {})
            strength = meta.get("strength", 0.5)
            pref_type = meta.get("pref_type", "")
            
            # Only include strong preferences
            if strength >= 0.6:
                if "like" in pref.get("content", "").lower():
                    strong_prefs.append(f"You respond well when I {pref_type}")
                elif "dislike" in pref.get("content", "").lower():
                    strong_prefs.append(f"You prefer I avoid {pref_type}")
        
        if not strong_prefs:
            return ""
        
        lines = ["Your preferences I've learned:"]
        lines.extend([f"- {p}" for p in strong_prefs[:3]])  # Max 3
        
        return "\n".join(lines)
    
    def _relative_date(self, date_str: str) -> str:
        """Convert date string to relative description."""
        try:
            date = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now().date()
            delta = (today - date.date()).days
            
            if delta == 0:
                return "Earlier today"
            elif delta == 1:
                return "Yesterday"
            elif delta < 7:
                return f"{delta} days ago"
            elif delta < 14:
                return "Last week"
            elif delta < 30:
                return f"{delta // 7} weeks ago"
            else:
                return f"{delta // 30} months ago"
        except:
            return date_str
    
    def recall_similar_situations(
        self,
        patterns: List[str],
        time_of_day: int = None,
        n_results: int = 3
    ) -> List[Dict]:
        """
        Recall past situations similar to current one.
        
        Useful for: "Last time you were working late, you..."
        """
        memory = self._get_memory()
        
        # Build query from patterns
        query = " ".join(patterns) if patterns else "conversation"
        
        # Filter by time of day if relevant
        time_filter = None
        if time_of_day is not None:
            # Similar time of day (within 3 hours)
            time_filter = {
                "$and": [
                    {"hour": {"$gte": max(0, time_of_day - 3)}},
                    {"hour": {"$lte": min(23, time_of_day + 3)}}
                ]
            }
        
        return memory.recall_episodes(
            query=query,
            n_results=n_results,
            time_filter=time_filter
        )
    
    def get_user_fact(self, topic: str) -> Optional[str]:
        """
        Get a specific fact about the user.

        Example: get_user_fact("pet") -> "User has a cat named Luna"
        """
        memory = self._get_memory()
        facts = memory.recall_facts(query=topic, n_results=1, min_confidence=0.6)

        if facts:
            return facts[0].get("content")
        return None

    def get_user_identity(self) -> Dict:
        """
        Get user identity information (name, profession, relationship, etc.)

        Returns dict with identity fields found, e.g.:
        {"name": "Martin Ngigi", "nickname": "Marto", "profession": "software engineer"}
        """
        memory = self._get_memory()
        identity = {}

        # Search for identity-category facts
        facts = memory.recall_facts(category="identity", n_results=10, min_confidence=0.5)

        for fact in facts:
            content = fact.get("content", "").lower()

            if "name is" in content:
                # Extract name after "name is"
                match = re.search(r"name is\s+(.+)", content, re.IGNORECASE)
                if match:
                    candidate_name = match.group(1).strip().strip(".,!?\"'`")
                    name_parts = [p for p in candidate_name.split() if p]
                    has_invalid_name_token = any(part in INVALID_NAME_TOKENS for part in name_parts)
                    if has_invalid_name_token and "name" not in identity:
                        # Compatibility fallback for previously stored bad facts
                        # like "marto or" -> keep the first valid token.
                        fallback_parts = [
                            part for part in name_parts
                            if part not in INVALID_NAME_TOKENS and part not in INVALID_IDENTITY_NAMES
                        ]
                        if fallback_parts:
                            identity["name"] = fallback_parts[0].title()
                        continue
                    if (
                        candidate_name not in INVALID_IDENTITY_NAMES
                        and not has_invalid_name_token
                        and "name" not in identity
                    ):
                        identity["name"] = candidate_name.title()
            elif "nickname" in content:
                match = re.search(r"nickname\s+(.+)", content, re.IGNORECASE)
                if match:
                    identity["nickname"] = match.group(1).strip()
            elif "is a " in content or "is an " in content:
                # Profession
                match = re.search(r"is (?:a|an)\s+(.+)", content, re.IGNORECASE)
                if match:
                    identity["profession"] = match.group(1).strip()
            elif "creator" in content or "owner" in content:
                identity["relationship"] = "creator"
            elif "years old" in content or re.search(r"\bis\s+\d+\b", content):
                match = re.search(r"(\d+)", content)
                if match:
                    identity["age"] = int(match.group(1))
            elif "from" in content or "lives in" in content:
                match = re.search(r"(?:from|lives in)\s+(.+)", content, re.IGNORECASE)
                if match:
                    identity["location"] = match.group(1).strip()

        return identity

    def get_identity_prompt(self) -> str:
        """
        Get a formatted identity string for prompt injection.

        Returns something like:
        "User's name is Martin (also called Marto). They are your creator
        and work as a software engineer."
        """
        identity = self.get_user_identity()
        if not identity:
            return ""

        parts = []

        # Name
        name = identity.get("name", "")
        nickname = identity.get("nickname", "")
        if name and nickname:
            parts.append(f"User's name is {name} (also called {nickname})")
        elif name:
            parts.append(f"User's name is {name}")
        elif nickname:
            parts.append(f"User goes by {nickname}")

        # Relationship
        if identity.get("relationship") == "creator":
            parts.append("They are your creator/developer")

        # Profession
        if identity.get("profession"):
            parts.append(f"They work as a {identity['profession']}")

        # Age
        if identity.get("age"):
            parts.append(f"They are {identity['age']} years old")

        # Location
        if identity.get("location"):
            parts.append(f"They are from {identity['location']}")

        return ". ".join(parts) + "." if parts else ""

    def has_met_before(self) -> bool:
        """Check if we've had conversations before."""
        memory = self._get_memory()
        stats = memory.get_stats()
        return stats["episodes"] > 0 or stats["facts"] > 0


# Singleton instance
_recall_engine: Optional[RecallEngine] = None


def get_recall_engine() -> RecallEngine:
    """Get the shared recall engine instance."""
    global _recall_engine
    if _recall_engine is None:
        _recall_engine = RecallEngine()
    return _recall_engine
