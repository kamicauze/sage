from enum import Enum
import time
from typing import List, Dict, Optional
from datetime import datetime


class SageMode(Enum):
    ABSENT = "ABSENT"
    PRESENT = "PRESENT"
    STILL_PRESENT = "STILL_PRESENT"
    FOCUS = "FOCUS"
    QUIET = "QUIET"
    DND = "DO_NOT_DISTURB"


class ActionMemory:
    """
    Tracks Sage's recent actions for self-awareness.
    
    Sage needs to know what she's already said/done to avoid
    repetition and to reference past interactions naturally.
    """
    
    MAX_ACTIONS = 20  # Keep last 20 actions
    
    def __init__(self):
        self.actions: List[Dict] = []
        
    def record_suggestion(self, suggestion_text: str, intent: str = None) -> Dict:
        """Record that Sage made a suggestion."""
        action = {
            "type": "suggestion",
            "detail": suggestion_text[:100],  # Truncate
            "intent": intent,
            "timestamp": time.time(),
            "when": self._relative_time(time.time()),
            "outcome": None  # Can be updated later
        }
        self._add_action(action)
        return action
        
    def record_timer(self, minutes: int, label: str) -> Dict:
        """Record that Sage set a timer."""
        action = {
            "type": "timer",
            "detail": f"{minutes} minute {label}",
            "duration_min": minutes,
            "label": label,
            "timestamp": time.time(),
            "when": self._relative_time(time.time()),
            "outcome": "pending"
        }
        self._add_action(action)
        return action
        
    def record_check_in(self, reason: str = None) -> Dict:
        """Record that Sage checked in on the user."""
        action = {
            "type": "check_in",
            "detail": reason or "general check-in",
            "timestamp": time.time(),
            "when": self._relative_time(time.time()),
            "outcome": None
        }
        self._add_action(action)
        return action
        
    def record_response(self, response_text: str, response_type: str = "chat") -> Dict:
        """Record a general response from Sage."""
        action = {
            "type": "response",
            "detail": response_text[:100],
            "response_type": response_type,
            "timestamp": time.time(),
            "when": self._relative_time(time.time()),
            "outcome": None
        }
        self._add_action(action)
        return action
        
    def update_outcome(self, action_index: int, outcome: str) -> None:
        """Update the outcome of a past action."""
        if 0 <= action_index < len(self.actions):
            self.actions[action_index]["outcome"] = outcome
            
    def mark_timer_expired(self, label: str) -> None:
        """Mark a timer action as expired."""
        for action in reversed(self.actions):
            if action["type"] == "timer" and action.get("label") == label:
                action["outcome"] = "expired"
                break
                
    def mark_suggestion_followed(self, followed: bool = True) -> None:
        """Mark the last suggestion as followed or ignored."""
        for action in reversed(self.actions):
            if action["type"] == "suggestion":
                action["outcome"] = "followed" if followed else "ignored"
                break
                
    def get_recent_actions(self, limit: int = 5, action_type: str = None) -> List[Dict]:
        """Get recent actions, optionally filtered by type."""
        actions = self.actions
        if action_type:
            actions = [a for a in actions if a["type"] == action_type]
        
        # Update relative times before returning
        for action in actions:
            action["when"] = self._relative_time(action["timestamp"])
            
        return actions[-limit:]
        
    def get_last_suggestion(self) -> Optional[Dict]:
        """Get the most recent suggestion made."""
        for action in reversed(self.actions):
            if action["type"] == "suggestion":
                action["when"] = self._relative_time(action["timestamp"])
                return action
        return None
        
    def time_since_last_action(self, action_type: str = None) -> Optional[float]:
        """Get minutes since last action of a type (or any action)."""
        for action in reversed(self.actions):
            if action_type is None or action["type"] == action_type:
                return (time.time() - action["timestamp"]) / 60
        return None
        
    def _add_action(self, action: Dict) -> None:
        """Add action and trim to max size."""
        self.actions.append(action)
        if len(self.actions) > self.MAX_ACTIONS:
            self.actions = self.actions[-self.MAX_ACTIONS:]
            
    def _relative_time(self, timestamp: float) -> str:
        """Convert timestamp to relative time description."""
        minutes_ago = (time.time() - timestamp) / 60
        
        if minutes_ago < 1:
            return "just now"
        elif minutes_ago < 5:
            return "a few minutes ago"
        elif minutes_ago < 15:
            return f"about {int(minutes_ago)} minutes ago"
        elif minutes_ago < 60:
            return f"{int(minutes_ago)} minutes ago"
        elif minutes_ago < 120:
            return "about an hour ago"
        else:
            hours = int(minutes_ago / 60)
            return f"about {hours} hours ago"
            
    def clear(self) -> None:
        """Clear all action memory."""
        self.actions = []
        
    def get_summary(self) -> Dict:
        """Get a summary of action memory for debugging."""
        return {
            "total_actions": len(self.actions),
            "recent_types": [a["type"] for a in self.actions[-5:]],
            "last_action_min_ago": self.time_since_last_action(),
        }


class SageState:
    QUIET_AFTER_MS = 2 * 60 * 1000 # 2 minutes
    STILL_THRESHOLD_MS = 20 * 60 * 1000 # 20 minutes without significant change

    def __init__(self):
        self.mode = SageMode.ABSENT
        self.rooms = {} # { room_name: { occupied: bool, last_motion_ts: int, last_presence_ts: int, last_state_change: int, raw: dict } }
        self.flags = {
            "home_active": False,
            "home_quiet": True
        }
        self.pushiness = 0.5 
        self.active_timers = [] # List of { "expiry_ts": int, "label": str, "metadata": dict }
        self.action_memory = ActionMemory()  # Track Sage's actions for self-awareness
        
    def set_timer(self, minutes, label="generic", metadata=None):
        now_ms = int(time.time() * 1000)
        expiry = now_ms + (int(minutes) * 60 * 1000)
        timer = {
            "expiry_ts": expiry,
            "label": label,
            "metadata": metadata or {}
        }
        self.active_timers.append(timer)
        
        # Record in action memory for self-awareness
        self.action_memory.record_timer(minutes, label)
        
        print(f"[State] Timer set: {label} for {minutes} minutes (expires at {expiry})")
        return timer

    def check_timers(self, now_ms=None):
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        
        expired = []
        remaining = []
        for timer in self.active_timers:
            if now_ms >= timer["expiry_ts"]:
                print(f"[State] Timer expired: {timer['label']}")
                # Mark in action memory
                self.action_memory.mark_timer_expired(timer['label'])
                expired.append(timer)
            else:
                remaining.append(timer)
        
        self.active_timers = remaining
        return expired

    def handle_presence_event(self, event):
        """
        Processes a raw presence update and returns a derived event if a state changed.
        """
        room_name = event["room"]
        motion = event["motion"]
        presence = event.get("presence", motion) # mmWave static presence
        ts = event["ts"]

        if room_name not in self.rooms:
            self.rooms[room_name] = {
                "occupied": False, 
                "last_motion_ts": 0, 
                "last_presence_ts": 0,
                "last_state_change": ts,
                "raw": {}
            }

        room = self.rooms[room_name]
        room["raw"] = event["raw"]

        # Track last time we saw ANY presence (static or motion)
        if presence:
            room["last_presence_ts"] = ts

        # Handle Room Occupied transition
        if presence and not room["occupied"]:
            room["occupied"] = True
            room["last_state_change"] = ts
            self._recalculate_flags()
            self._evaluate_mode()
            return {
                "type": "room_occupied",
                "room": room_name,
                "ts": ts,
                "raw": event["raw"]
            }

        if motion:
            room["last_motion_ts"] = ts
            # Transition back from STILL_PRESENT to PRESENT
            if self.mode == SageMode.STILL_PRESENT:
                self.mode = SageMode.PRESENT
                print(f"[State] Movement detected! Mode: {self.mode.value}")
                return {"type": "activity_resumed", "room": room_name, "ts": ts}
            return {"type": "motion", "room": room_name, "ts": ts}
        
        return {"type": "presence_ping", "room": room_name, "ts": ts}

    def check_transitions(self, now_ms=None):
        """
        Checks all rooms for quiet transitions and the global state for stillness.
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)
            
        events = []
        
        # 1. Check Quiet Transitions (No presence at all for 2 mins)
        for room_name, room in self.rooms.items():
            if room["occupied"]:
                # If no presence (static or motion) for 2 minutes
                if now_ms - room["last_presence_ts"] > self.QUIET_AFTER_MS:
                    room["occupied"] = False
                    room["last_state_change"] = now_ms
                    print(f"[State] 🌙 {room_name} became QUIET (no presence detected)")
                    events.append({
                        "type": "room_quiet",
                        "room": room_name,
                        "ts": now_ms,
                        "raw": room["raw"]
                    })
        
        if events:
            self._recalculate_flags()
            self._evaluate_mode()
            
        # 2. Check Stillness (Presence detected but no MOTION for 20 mins)
        if self.mode == SageMode.PRESENT:
            active_rooms = [r for r in self.rooms.values() if r["occupied"]]
            if active_rooms:
                # Find the last time ANY occupied room saw motion
                last_motion = max(r["last_motion_ts"] for r in active_rooms)
                if now_ms - last_motion > self.STILL_THRESHOLD_MS:
                    self.mode = SageMode.STILL_PRESENT
                    print(f"[State] Mode changed: {self.mode.value} (Presence detected but no motion for 20m)")
                    events.append({
                        "type": "stillness_detected",
                        "ts": now_ms,
                        "duration_ms": now_ms - last_motion
                    })

        return events

    def _recalculate_flags(self):
        self.flags["home_active"] = any(r["occupied"] for r in self.rooms.values())
        self.flags["home_quiet"] = not self.flags["home_active"]

    def _evaluate_mode(self):
        # Simplistic state machine logic for now
        if self.flags["home_quiet"]:
            self.mode = SageMode.ABSENT
        else:
            # If any room is active, we are PRESENT
            # Future: add STILL_PRESENT and FOCUS logic based on mmWave/CV
            if self.mode == SageMode.ABSENT:
                self.mode = SageMode.PRESENT
                print(f"[State] Mode changed: {self.mode.value}")

    def get_snapshot(self):
        return {
            "mode": self.mode.value,
            "flags": self.flags,
            "rooms": self.rooms,
            "pushiness": self.pushiness,
            "active_timers": self.active_timers,
            "action_memory": self.action_memory.get_recent_actions(limit=5)
        }

