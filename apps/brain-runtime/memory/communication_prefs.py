"""
Communication Preferences Manager
Tracks and enforces user preferences about communication style.

Specifically handles:
- Phrases/words to avoid
- Tone preferences
- Interaction style preferences
"""

import re
from typing import List, Dict, Optional, TYPE_CHECKING
from .sage_memory import get_memory

if TYPE_CHECKING:
    from .sage_memory import SageMemory


class CommunicationPrefsManager:
    """
    Manages communication preferences that should be enforced in prompts.
    """

    def __init__(self, memory: Optional["SageMemory"] = None):
        """
        Args:
            memory: SageMemory instance for persistence
        """
        self.memory = memory or get_memory()

    def record_avoided_phrase(self, phrase: str, user_message: str = "") -> str:
        """
        Record a phrase that the user wants to avoid.

        Args:
            phrase: The phrase/word to avoid (e.g., "Aaaai", "bro")
            user_message: Original user message for context

        Returns:
            ID of stored preference
        """
        # Normalize the phrase
        phrase_normalized = phrase.strip().lower()

        # Check if we already have this preference
        existing = self._get_avoided_phrases()
        if phrase_normalized in [p.lower() for p in existing]:
            print(f"[Prefs] Already tracking avoidance of '{phrase}'")
            return "existing"

        # Store as preference
        pref_id = self.memory.update_preference(
            pref_type="avoid_phrase",
            value=f"Do not use the word/phrase '{phrase}'",
            signal="explicit",
            strength=1.0  # Strong signal since user explicitly requested
        )

        print(f"[Prefs] Recorded: Avoid phrase '{phrase}' (ID: {pref_id})")
        return pref_id

    def _get_avoided_phrases(self) -> List[str]:
        """Get list of phrases to avoid."""
        prefs = self.memory.get_preferences(pref_type="avoid_phrase")

        phrases = []
        for pref in prefs:
            # Extract phrase from value like "Do not use the word/phrase 'X'"
            # Note: get_preferences returns 'content' field, not 'document'
            text = pref.get("content", "") or pref.get("document", "")
            match = re.search(r"'([^']+)'", text)
            if match:
                phrases.append(match.group(1))

        return phrases

    def get_communication_rules(self) -> str:
        """
        Get a formatted string of communication rules for injection into prompts.

        Returns:
            String like "IMPORTANT: User has requested you NOT use: ['Aaaai']"
        """
        avoided_phrases = self._get_avoided_phrases()

        if not avoided_phrases:
            return ""

        # Build rule text
        rules = "CRITICAL COMMUNICATION RULES:\n"
        rules += f"- The user has EXPLICITLY requested you NEVER use these words/phrases: {avoided_phrases}\n"
        rules += "- This is a hard requirement. Do NOT use them under any circumstances.\n"
        rules += "- If you accidentally use them, the user will be frustrated.\n"

        return rules

    def process_user_feedback(self, user_message: str) -> bool:
        """
        Detect if user message contains feedback about avoided phrases.
        Automatically extract and record them.

        Args:
            user_message: User's message text

        Returns:
            True if feedback was detected and processed
        """
        # Patterns to detect "don't say X" requests
        avoid_patterns = [
            r"(?:don't|do not|stop) (?:say|saying|use|using) ['\"]?(\w+)['\"]?",
            r"(?:don't|do not) say ['\"]?([^'\"]+?)['\"]? (?:again|anymore|tena)",
            r"(?:please|tafadhali) (?:don't|do not) use ['\"]?(\w+)['\"]?",
            r"usiseme ['\"]?(\w+)['\"]? (?:again|tena|anymore)",
            r"si nilikushow (?:si lazima )?you say ['\"]?(\w+)['\"]?"
        ]

        for pattern in avoid_patterns:
            match = re.search(pattern, user_message, re.IGNORECASE)
            if match and match.groups():
                phrase = match.group(1).strip()
                print(f"[Prefs] Detected avoidance request: '{phrase}'")
                self.record_avoided_phrase(phrase, user_message)
                return True

        return False


# Global instance (initialized when needed)
_prefs_manager: Optional[CommunicationPrefsManager] = None


def get_prefs_manager() -> CommunicationPrefsManager:
    """Get or create the global communication preferences manager."""
    global _prefs_manager
    if _prefs_manager is None:
        _prefs_manager = CommunicationPrefsManager()
    return _prefs_manager


def get_communication_rules() -> str:
    """
    Convenience function to get communication rules for prompt injection.

    Returns:
        Formatted string of rules, or empty string if none
    """
    return get_prefs_manager().get_communication_rules()


def process_user_feedback(user_message: str) -> bool:
    """
    Convenience function to process user feedback.

    Args:
        user_message: User's message text

    Returns:
        True if feedback was detected
    """
    return get_prefs_manager().process_user_feedback(user_message)
