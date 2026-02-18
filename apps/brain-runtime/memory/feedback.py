"""
Feedback Learning
Detects and processes user feedback signals to learn preferences.

Types of feedback:
- Explicit: "I like when you...", "Don't do that"
- Implicit positive: Follows suggestions, laughs, thanks
- Implicit negative: Ignores suggestions, changes topic, short responses
"""

import re
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class FeedbackDetector:
    """
    Detects feedback signals in user messages and behavior.
    """
    
    # Explicit positive patterns
    EXPLICIT_POSITIVE = [
        (r"i (?:really )?like (?:it )?when you (.+)", "explicit_like"),
        (r"i (?:really )?love (?:it )?when you (.+)", "explicit_like"),
        (r"that(?:'s| is) (?:exactly )?what i (?:needed|wanted)", "explicit_like"),
        (r"(?:perfect|great|awesome|helpful|thanks)", "explicit_positive"),
        (r"you(?:'re| are) (?:the best|amazing|so helpful)", "explicit_positive"),
        (r"keep (?:doing|being) (.+)", "explicit_like"),
    ]
    
    # Explicit negative patterns
    EXPLICIT_NEGATIVE = [
        (r"i (?:don't|do not) like (?:it )?when you (.+)", "explicit_dislike"),
        (r"(?:please )?(?:stop|don't|quit) (.+)", "explicit_dislike"),
        (r"that(?:'s| is) (?:annoying|not helpful|too much)", "explicit_dislike"),
        (r"(?:whatever|nevermind|forget it)", "implicit_negative"),
        (r"(?:not now|i'm busy|later)", "implicit_dismiss"),
    ]
    
    # Implicit positive signals
    IMPLICIT_POSITIVE = [
        (r"(?:haha|lol|lmao|😂|🤣|😊)", "humor_positive"),
        (r"(?:❤️|💕|🥰|😍)", "warmth_positive"),
        (r"(?:thanks|thank you|cheers|ty)", "gratitude"),
        (r"(?:yes|yeah|yep|sure|ok|okay|alright)(?:\s|!|$)", "agreement"),
    ]
    
    # Implicit negative signals
    IMPLICIT_NEGATIVE = [
        (r"(?:🙄|😒|😤|😑)", "annoyance"),
        (r"(?:ugh|sigh|meh)", "frustration"),
        (r"^(?:ok|k|fine)\.?$", "dismissive"),  # Very short responses
    ]
    
    def __init__(self):
        # Compile patterns
        self.positive_patterns = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.EXPLICIT_POSITIVE
        ]
        self.negative_patterns = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.EXPLICIT_NEGATIVE
        ]
        self.implicit_pos = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.IMPLICIT_POSITIVE
        ]
        self.implicit_neg = [
            (re.compile(p, re.IGNORECASE), t) for p, t in self.IMPLICIT_NEGATIVE
        ]
    
    def detect_feedback(
        self,
        user_message: str,
        previous_sage_message: str = None,
        suggestion_was_made: bool = False
    ) -> List[Dict]:
        """
        Detect feedback signals in a user message.
        
        Args:
            user_message: The user's message
            previous_sage_message: What Sage said before this
            suggestion_was_made: Whether Sage made a suggestion
            
        Returns:
            List of feedback signals detected
        """
        signals = []
        
        # Check explicit positive
        for pattern, signal_type in self.positive_patterns:
            match = pattern.search(user_message)
            if match:
                signals.append({
                    "type": signal_type,
                    "polarity": "positive",
                    "explicit": True,
                    "content": match.group(1) if match.groups() else user_message,
                    "context": previous_sage_message[:100] if previous_sage_message else ""
                })
        
        # Check explicit negative
        for pattern, signal_type in self.negative_patterns:
            match = pattern.search(user_message)
            if match:
                signals.append({
                    "type": signal_type,
                    "polarity": "negative",
                    "explicit": True,
                    "content": match.group(1) if match.groups() else user_message,
                    "context": previous_sage_message[:100] if previous_sage_message else ""
                })
        
        # Check implicit positive
        for pattern, signal_type in self.implicit_pos:
            if pattern.search(user_message):
                signals.append({
                    "type": signal_type,
                    "polarity": "positive",
                    "explicit": False,
                    "content": user_message,
                    "context": previous_sage_message[:100] if previous_sage_message else ""
                })
        
        # Check implicit negative
        for pattern, signal_type in self.implicit_neg:
            if pattern.search(user_message):
                signals.append({
                    "type": signal_type,
                    "polarity": "negative",
                    "explicit": False,
                    "content": user_message,
                    "context": previous_sage_message[:100] if previous_sage_message else ""
                })
        
        # Check for suggestion follow-through
        if suggestion_was_made:
            if self._indicates_following_suggestion(user_message):
                signals.append({
                    "type": "suggestion_followed",
                    "polarity": "positive",
                    "explicit": False,
                    "content": "Followed suggestion",
                    "context": previous_sage_message[:100] if previous_sage_message else ""
                })
            elif self._indicates_rejecting_suggestion(user_message):
                signals.append({
                    "type": "suggestion_rejected",
                    "polarity": "negative",
                    "explicit": False,
                    "content": "Rejected suggestion",
                    "context": previous_sage_message[:100] if previous_sage_message else ""
                })
        
        return signals
    
    def _indicates_following_suggestion(self, message: str) -> bool:
        """Check if message indicates user followed a suggestion."""
        follow_patterns = [
            r"(?:ok|okay|alright|sure|fine).{0,10}(?:will do|doing it|on it)",
            r"(?:good idea|you're right|true)",
            r"(?:going to|gonna|let me) (?:do|try|take)",
        ]
        return any(re.search(p, message, re.IGNORECASE) for p in follow_patterns)
    
    def _indicates_rejecting_suggestion(self, message: str) -> bool:
        """Check if message indicates user rejected a suggestion."""
        reject_patterns = [
            r"(?:no|nah|nope)",
            r"(?:not now|maybe later|in a bit)",
            r"(?:can't|don't want to|not going to)",
            r"(?:just|only) (?:\d+|a few|one) more",
        ]
        return any(re.search(p, message, re.IGNORECASE) for p in reject_patterns)


class PreferenceLearner:
    """
    Learns user preferences from feedback signals over time.
    """
    
    # Map signal types to preference categories
    SIGNAL_TO_PREFERENCE = {
        "humor_positive": ("humor", "positive"),
        "warmth_positive": ("warmth", "positive"),
        "gratitude": ("helpfulness", "positive"),
        "annoyance": ("tone", "negative"),
        "frustration": ("approach", "negative"),
        "suggestion_followed": ("suggestions", "positive"),
        "suggestion_rejected": ("suggestions", "negative"),
    }
    
    def __init__(self, memory=None):
        self.memory = memory
        self.detector = FeedbackDetector()
        
    def _get_memory(self):
        """Lazy load memory."""
        if self.memory is None:
            from .sage_memory import get_memory
            self.memory = get_memory()
        return self.memory
    
    def process_feedback(
        self,
        user_message: str,
        sage_message: str = None,
        suggestion_made: bool = False
    ) -> List[str]:
        """
        Process a user message for feedback and update preferences.
        
        Args:
            user_message: What the user said
            sage_message: What Sage said before
            suggestion_made: Whether Sage made a suggestion
            
        Returns:
            List of preference updates made
        """
        signals = self.detector.detect_feedback(
            user_message=user_message,
            previous_sage_message=sage_message,
            suggestion_was_made=suggestion_made
        )
        
        if not signals:
            return []
        
        memory = self._get_memory()
        updates = []
        
        for signal in signals:
            signal_type = signal["type"]
            polarity = signal["polarity"]
            
            # Map to preference update
            if signal_type in self.SIGNAL_TO_PREFERENCE:
                pref_type, expected_polarity = self.SIGNAL_TO_PREFERENCE[signal_type]
                
                # Determine signal strength
                if signal["explicit"]:
                    signal_name = f"explicit_{polarity}"
                    strength = 0.8
                else:
                    signal_name = f"implicit_{polarity}"
                    strength = 0.5
                
                # Build preference value
                if polarity == "positive":
                    value = f"Responds well to {pref_type}"
                else:
                    value = f"Prefers less {pref_type}"
                
                # Update preference
                memory.update_preference(
                    pref_type=pref_type,
                    value=value,
                    signal=signal_name,
                    strength=strength
                )
                
                updates.append(f"{pref_type}: {value} ({signal_name})")
            
            # Handle explicit likes/dislikes specially
            elif signal_type == "explicit_like":
                content = signal["content"]
                memory.update_preference(
                    pref_type="explicit_like",
                    value=f"User likes: {content}",
                    signal="explicit",
                    strength=0.9
                )
                updates.append(f"Learned: User likes {content}")
                
            elif signal_type == "explicit_dislike":
                content = signal["content"]
                memory.update_preference(
                    pref_type="explicit_dislike",
                    value=f"User dislikes: {content}",
                    signal="explicit",
                    strength=0.9
                )
                updates.append(f"Learned: User dislikes {content}")
        
        if updates:
            print(f"[Feedback] Preference updates: {updates}")
        
        return updates
    
    def get_communication_guidance(self) -> Dict:
        """
        Get guidance on how to communicate based on learned preferences.
        
        Returns dict with:
        - should_use_humor: bool
        - should_be_warm: bool
        - suggestion_acceptance_rate: float
        - explicit_likes: list
        - explicit_dislikes: list
        """
        memory = self._get_memory()
        prefs = memory.get_preferences()
        
        guidance = {
            "should_use_humor": True,  # Default
            "should_be_warm": True,    # Default
            "should_be_direct": False,
            "suggestion_approach": "gentle",
            "explicit_likes": [],
            "explicit_dislikes": []
        }
        
        for pref in prefs:
            meta = pref.get("metadata", {})
            pref_type = meta.get("pref_type", "")
            strength = meta.get("strength", 0.5)
            value = pref.get("content", "")
            
            if pref_type == "humor":
                guidance["should_use_humor"] = strength > 0.5
            elif pref_type == "warmth":
                guidance["should_be_warm"] = strength > 0.5
            elif pref_type == "suggestions":
                if strength > 0.6:
                    guidance["suggestion_approach"] = "confident"
                elif strength < 0.4:
                    guidance["suggestion_approach"] = "tentative"
            elif pref_type == "explicit_like":
                guidance["explicit_likes"].append(value)
            elif pref_type == "explicit_dislike":
                guidance["explicit_dislikes"].append(value)
        
        return guidance


# Convenience function
def process_user_feedback(
    user_message: str,
    sage_message: str = None,
    suggestion_made: bool = False
) -> List[str]:
    """Process feedback from a user message."""
    learner = PreferenceLearner()
    return learner.process_feedback(user_message, sage_message, suggestion_made)
