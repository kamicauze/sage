import time
from datetime import datetime

class SummaryEngine:
    """
    🧠 DETERMINISTIC SITUATION SUMMARY ENGINE
    
    Three-Layer Architecture:
    1. THIS ENGINE = Facts + Rule-based patterns (defendable)
    2. Local LLM = Inferences with confidence (interpretations)
    3. Cloud LLM = Personality (compressed context only)
    
    Output Format:
    {
        "facts": {sensor measurements, timestamps, geometry},
        "patterns": ["OVERWORK_LATE", ...],  # Rule-based thresholds
        "intent": "INTERVENE_SLEEP",          # Derived from patterns
        "constraints": {...}                   # For downstream LLM
    }
    
    Think: Instruments + Logbook (facts you can defend)
    """
    
    # ⚙️ Thresholds (explicit, tunable, defendable)
    QUIET_HOUR_START = 23
    QUIET_HOUR_END = 7
    OVERWORK_THRESHOLD_HOURS = 14
    HYPERFOCUS_THRESHOLD_MIN = 45
    BREAK_OVERDUE_THRESHOLD_MIN = 90
    LONG_STILLNESS_THRESHOLD_MIN = 30
    
    # Audio-based thresholds
    PROLONGED_SILENCE_HOURS = 6
    SOCIAL_ISOLATION_HOURS = 48
    MEETING_DURATION_MIN = 15
    AUDIO_SILENCE_HYPERFOCUS_MIN = 90
    
    # Vision-based thresholds
    EXTENDED_RECLINED_MIN = 120  # 2 hours
    EYES_CLOSED_EXTENDED_MIN = 20
    HEAD_DOWN_ANGLE_DEG = -30
    HEAD_DOWN_DURATION_MIN = 45
    
    # Multi-sensor thresholds
    SEDENTARY_HOURS = 4
    FATIGUE_COMPOSITE_MIN = 30
    
    # Sleep tracking thresholds
    SLEEP_VARIANCE_HOURS = 2
    SHORT_SLEEP_HOURS = 6
    SHORT_SLEEP_NIGHTS = 2
    COMMITMENT_WARNING_MIN = 15
    
    def __init__(self):
        # Rule-based pattern detection (defendable thresholds)
        self.patterns = {
            # Core patterns
            "OVERWORK_LATE": self._pattern_overwork_late,
            "LONG_FOCUS_BLOCK": self._pattern_long_focus_block,
            "BREAK_OVERDUE": self._pattern_break_overdue,
            "EXTENDED_STILLNESS": self._pattern_extended_stillness,
            
            # Audio-based patterns
            "PROLONGED_SILENCE": self._pattern_prolonged_silence,
            "SOCIAL_ISOLATION_MULTI_DAY": self._pattern_social_isolation,
            "MEETING_IN_PROGRESS": self._pattern_meeting_in_progress,
            "NIGHT_AUDIO_ACTIVITY": self._pattern_night_audio_activity,
            
            # Vision-based patterns
            "EXTENDED_RECLINED_POSTURE": self._pattern_extended_reclined_posture,
            "EYES_CLOSED_EXTENDED": self._pattern_eyes_closed_extended,
            "HEAD_DOWN_SUSTAINED": self._pattern_head_down_sustained,
            
            # Multi-sensor patterns
            "SCREEN_HYPERFOCUS": self._pattern_screen_hyperfocus,
            "SEDENTARY_PATTERN": self._pattern_sedentary_pattern,
            "FATIGUE_COMPOSITE": self._pattern_fatigue_composite,
            
            # Schedule patterns
            "SLEEP_DEPRIVATION_PATTERN": self._pattern_sleep_deprivation,
            "ERRATIC_SLEEP_SCHEDULE": self._pattern_erratic_sleep_schedule,
            "MISSED_COMMITMENT_IMMINENT": self._pattern_missed_commitment_imminent,
        }

    def generate_summary(self, state_snapshot, event_history, now_ms=None):
        """
        Generate deterministic summary: Facts + Patterns + Intent
        
        Returns: (summary_packet: dict, briefing: str)
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)
        
        # 1. Extract FACTS (measurements only - defendable)
        facts = self._extract_facts(state_snapshot, event_history, now_ms)
        
        # 2. Detect PATTERNS (rule-based thresholds - defendable)
        detected_patterns = []
        for name, rule_func in self.patterns.items():
            if rule_func(facts):
                detected_patterns.append(name)
        
        # 3. Derive INTENT (from patterns via explicit rules)
        intent, constraints = self._derive_intent(detected_patterns, facts)
        
        # 4. Assembly
        summary_packet = {
            "facts": facts,
            "patterns": detected_patterns,
            "intent": intent,
            "constraints": constraints
        }
        
        # 5. Briefing for Local LLM
        briefing = self._generate_briefing(summary_packet)
        
        return summary_packet, briefing

    def _extract_facts(self, state, history, now_ms):
        """
        Extract FACTS ONLY (measurements, geometry, timestamps).
        This is the factual record - defendable evidence.
        """
        dt = datetime.fromtimestamp(now_ms / 1000)
        
        # === TEMPORAL FACTS ===
        local_hour = dt.hour
        is_quiet_hours = local_hour >= self.QUIET_HOUR_START or local_hour < self.QUIET_HOUR_END
        
        # === PRESENCE FACTS ===
        is_present = state.get("flags", {}).get("home_active", False)
        rooms = state.get("rooms", {})
        active_rooms = [name for name, r in rooms.items() if r.get("occupied")]
        primary_room = active_rooms[0] if active_rooms else "none"
        
        # Stillness calculation
        stillness_min = 0
        if primary_room != "none":
            room_data = rooms[primary_room]
            last_motion_ts = room_data.get("last_motion_ts", 0)
            if last_motion_ts > 0:
                stillness_min = (now_ms - last_motion_ts) // (60 * 1000)
        
        # === AWAKE HOURS (from 24h history) ===
        awake_hours = 0
        window_24h = [e for e in history if e.get("ts", 0) >= (now_ms - 24 * 60 * 60 * 1000)]
        if window_24h:
            presence_events = [e for e in window_24h if e.get("type") in ["room_occupied", "motion", "activity_resumed"]]
            if presence_events:
                first_presence_ts = presence_events[0].get("ts", now_ms)
                awake_hours = round((now_ms - first_presence_ts) / (3600 * 1000), 1)
        
        # === BREAK TRACKING (from 60m history) ===
        time_since_break_min = None
        window_60m = [e for e in history if e.get("ts", 0) >= (now_ms - 60 * 60 * 1000)]
        break_events = [e for e in window_60m if e.get("type") in ["room_quiet", "activity_resumed"]]
        if break_events:
            last_break_ts = break_events[-1].get("ts")
            time_since_break_min = (now_ms - last_break_ts) // (60 * 1000)
        
        # === SCREEN STATE (if available) ===
        screen_active = state.get("screen_active", False)  # Activity proxy
        
        # === VISION GEOMETRY (if available) ===
        vision = None
        eyes_closed_duration_min = 0
        reclined_duration_min = 0
        head_down_duration_min = 0
        
        if primary_room != "none" and "vision" in rooms[primary_room]:
            v = rooms[primary_room]["vision"]
            vision = {
                "face_detected": v.get("face_detected", False),
                "head_pitch_deg": v.get("head_pitch_deg"),
                "body_configuration": v.get("body_configuration"),
                "torso_angle_deg": v.get("torso_angle_deg"),
                "eyes_open": v.get("eyes_open")
            }
            
            # Track duration of vision states
            eyes_closed_duration_min = v.get("eyes_closed_duration_min", 0)
            reclined_duration_min = v.get("reclined_duration_min", 0)
            head_down_duration_min = v.get("head_down_duration_min", 0)
        
        # === AUDIO FACTS (if available) ===
        audio_detected = state.get("audio_detected", False)
        audio_speech_detected = state.get("audio_speech_detected", False)
        audio_multi_voice = state.get("audio_multi_voice", False)
        audio_silence_min = state.get("audio_silence_min", 0)
        audio_silence_hours = audio_silence_min / 60.0 if audio_silence_min else 0
        audio_active_duration_min = state.get("audio_active_duration_min", 0)
        
        # === ROOM TRANSITIONS (from history) ===
        window_4h = [e for e in history if e.get("ts", 0) >= (now_ms - 4 * 60 * 60 * 1000)]
        room_transition_events = [e for e in window_4h if e.get("type") == "room_occupied"]
        room_transitions_4h = len(room_transition_events) - 1 if len(room_transition_events) > 1 else 0
        
        # === SLEEP TRACKING (if available - historical) ===
        sleep_variance_hours = state.get("sleep_variance_hours", 0)
        consecutive_short_sleep_nights = state.get("consecutive_short_sleep_nights", 0)
        avg_sleep_hours = state.get("avg_sleep_hours", 0)
        days_tracked = state.get("days_tracked", 0)
        
        # === SCHEDULE (if available) ===
        schedule_next = None
        # TODO: Extract from state when schedule integration is added
        
        # === ASSEMBLE FACTS ===
        facts = {
            # Temporal
            "time": dt.strftime("%H:%M"),
            "local_hour": local_hour,
            "day_of_week": dt.weekday(),
            "quiet_hours": is_quiet_hours,
            
            # Presence
            "present": is_present,
            "room": primary_room,
            "stillness_min": stillness_min,
            
            # Activity
            "screen_active": screen_active,
            
            # Duration
            "awake_hours": awake_hours,
            "time_since_break_min": time_since_break_min,
            
            # Vision geometry (if available)
            "vision": vision,
            "eyes_closed_duration_min": eyes_closed_duration_min,
            "reclined_duration_min": reclined_duration_min,
            "head_down_duration_min": head_down_duration_min,
            
            # Audio facts (if available)
            "audio_detected": audio_detected,
            "audio_speech_detected": audio_speech_detected,
            "audio_multi_voice": audio_multi_voice,
            "audio_silence_min": audio_silence_min,
            "audio_silence_hours": audio_silence_hours,
            "audio_active_duration_min": audio_active_duration_min,
            
            # Movement tracking
            "room_transitions_4h": room_transitions_4h,
            
            # Sleep tracking (historical - if available)
            "sleep_variance_hours": sleep_variance_hours,
            "consecutive_short_sleep_nights": consecutive_short_sleep_nights,
            "avg_sleep_hours": avg_sleep_hours,
            "days_tracked": days_tracked,
            
            # Schedule (if available)
            "schedule_next": schedule_next,
            
            # Mode
            "mode": state.get("mode", "UNKNOWN")
        }
        
        return facts

    # === PATTERN DETECTION (Rule-based, Defendable) ===
    
    def _pattern_overwork_late(self, facts):
        """
        Rule: Quiet hours AND awake > 14h AND present
        Evidence: measurable thresholds
        """
        return (facts["quiet_hours"] and 
                facts["awake_hours"] > self.OVERWORK_THRESHOLD_HOURS and 
                facts["present"])
    
    def _pattern_long_focus_block(self, facts):
        """
        Rule: Stillness > 45min AND present
        Evidence: duration threshold
        """
        return (facts["stillness_min"] > self.HYPERFOCUS_THRESHOLD_MIN and 
                facts["present"])
    
    def _pattern_break_overdue(self, facts):
        """
        Rule: Time since break > 90min AND present
        Evidence: duration threshold
        """
        return (facts["time_since_break_min"] is not None and
                facts["time_since_break_min"] > self.BREAK_OVERDUE_THRESHOLD_MIN and 
                facts["present"])
    
    def _pattern_extended_stillness(self, facts):
        """
        Rule: Stillness > 30min AND present
        Evidence: duration threshold
        """
        return (facts["stillness_min"] > self.LONG_STILLNESS_THRESHOLD_MIN and 
                facts["present"])
    
    # === AUDIO-BASED PATTERNS ===
    
    def _pattern_prolonged_silence(self, facts):
        """
        Rule: No speech detected for >6h during waking hours
        Evidence: audio_silence_hours threshold
        """
        return (not facts.get("quiet_hours") and
                facts.get("audio_silence_hours", 0) > self.PROLONGED_SILENCE_HOURS)
    
    def _pattern_social_isolation(self, facts):
        """
        Rule: No speech detected for >48h
        Evidence: extended audio silence threshold
        """
        return facts.get("audio_silence_hours", 0) > self.SOCIAL_ISOLATION_HOURS
    
    def _pattern_meeting_in_progress(self, facts):
        """
        Rule: Multiple voices detected for >15min
        Evidence: audio multi-voice + duration threshold
        """
        return (facts.get("audio_multi_voice") and
                facts.get("audio_active_duration_min", 0) > self.MEETING_DURATION_MIN)
    
    def _pattern_night_audio_activity(self, facts):
        """
        Rule: Audio detected during quiet hours
        Evidence: audio presence + quiet hours
        """
        return (facts.get("audio_detected") and
                facts.get("quiet_hours"))
    
    # === VISION-BASED PATTERNS ===
    
    def _pattern_extended_reclined_posture(self, facts):
        """
        Rule: Body configuration "reclined" for >2h during waking hours
        Evidence: vision geometry + duration threshold
        """
        vision = facts.get("vision")
        return (vision and
                vision.get("body_configuration") == "reclined" and
                facts.get("reclined_duration_min", 0) > self.EXTENDED_RECLINED_MIN and
                not facts.get("quiet_hours"))
    
    def _pattern_eyes_closed_extended(self, facts):
        """
        Rule: Eyes closed for >20min during waking hours
        Evidence: vision + duration threshold
        """
        vision = facts.get("vision")
        return (vision and
                vision.get("eyes_open") == False and
                facts.get("eyes_closed_duration_min", 0) > self.EYES_CLOSED_EXTENDED_MIN and
                not facts.get("quiet_hours"))
    
    def _pattern_head_down_sustained(self, facts):
        """
        Rule: Head pitch <-30° for >45min
        Evidence: vision geometry + duration threshold
        """
        vision = facts.get("vision")
        return (vision and
                vision.get("head_pitch_deg", 0) < self.HEAD_DOWN_ANGLE_DEG and
                facts.get("head_down_duration_min", 0) > self.HEAD_DOWN_DURATION_MIN)
    
    # === MULTI-SENSOR PATTERNS ===
    
    def _pattern_screen_hyperfocus(self, facts):
        """
        Rule: Screen active + stillness + no speech >90min
        Evidence: multi-sensor threshold
        """
        return (facts.get("screen_active") and
                facts.get("stillness_min", 0) > self.AUDIO_SILENCE_HYPERFOCUS_MIN and
                facts.get("audio_silence_min", 0) > self.AUDIO_SILENCE_HYPERFOCUS_MIN)
    
    def _pattern_sedentary_pattern(self, facts):
        """
        Rule: No room transitions for >4h during waking hours
        Evidence: motion tracking + duration threshold
        """
        return (facts.get("room_transitions_4h", 0) == 0 and
                not facts.get("quiet_hours") and
                facts.get("awake_hours", 0) > self.SEDENTARY_HOURS)
    
    def _pattern_fatigue_composite(self, facts):
        """
        Rule: Eyes closed + reclined + no speech >30min (waking hours)
        Evidence: multi-sensor fatigue indicators
        """
        vision = facts.get("vision")
        return (vision and
                vision.get("eyes_open") == False and
                vision.get("body_configuration") == "reclined" and
                facts.get("audio_silence_min", 0) > self.FATIGUE_COMPOSITE_MIN and
                not facts.get("quiet_hours"))
    
    # === SCHEDULE PATTERNS ===
    
    def _pattern_sleep_deprivation(self, facts):
        """
        Rule: <6h sleep for 2+ consecutive nights
        Evidence: historical sleep tracking
        """
        return (facts.get("consecutive_short_sleep_nights", 0) >= self.SHORT_SLEEP_NIGHTS and
                facts.get("avg_sleep_hours", 0) < self.SHORT_SLEEP_HOURS)
    
    def _pattern_erratic_sleep_schedule(self, facts):
        """
        Rule: Sleep time varies >2h over 3 days
        Evidence: historical sleep tracking
        """
        return (facts.get("sleep_variance_hours", 0) > self.SLEEP_VARIANCE_HOURS and
                facts.get("days_tracked", 0) >= 3)
    
    def _pattern_missed_commitment_imminent(self, facts):
        """
        Rule: Commitment <15min + not in correct location
        Evidence: schedule + location mismatch
        """
        schedule_next = facts.get("schedule_next")
        return (schedule_next and
                schedule_next.get("in_min", 999) < self.COMMITMENT_WARNING_MIN and
                facts.get("room") != schedule_next.get("location"))

    def _derive_intent(self, patterns, facts):
        """
        Derive intent from detected patterns using explicit rules.
        This is deterministic and defendable.
        
        Priority order (highest to lowest):
        1. CRITICAL - Immediate action needed
        2. HIGH - Strong suggestion
        3. MEDIUM - Gentle nudge
        4. LOW - Check-in
        5. SPECIAL - Respect/Do not disturb
        """
        
        # PRIORITY 1: CRITICAL (Immediate action)
        if "SLEEP_DEPRIVATION_PATTERN" in patterns or "OVERWORK_LATE" in patterns:
            return "INTERVENE_SLEEP", {
                "max_words": 45,
                "tone": "playful_firm",
                "no_guilt": True,
                "one_clear_action": True
            }
        
        if "MISSED_COMMITMENT_IMMINENT" in patterns:
            schedule = facts.get("schedule_next", {})
            return "ALERT_COMMITMENT", {
                "max_words": 30,
                "tone": "urgent_friendly",
                "commitment_name": schedule.get("name", "commitment"),
                "time_remaining_min": schedule.get("in_min", 0)
            }
        
        if "FATIGUE_COMPOSITE" in patterns:
            return "SUGGEST_REST", {
                "max_words": 40,
                "tone": "caring",
                "no_guilt": True
            }
        
        # PRIORITY 2: HIGH (Strong suggestion)
        if ("BREAK_OVERDUE" in patterns or 
            "SCREEN_HYPERFOCUS" in patterns or
            "EYES_CLOSED_EXTENDED" in patterns or
            "HEAD_DOWN_SUSTAINED" in patterns):
            return "SUGGEST_BREAK", {
                "max_words": 35,
                "tone": "gentle_nudge",
                "no_guilt": True,
                "one_clear_action": True
            }
        
        # PRIORITY 3: MEDIUM (Gentle nudge)
        if ("LONG_FOCUS_BLOCK" in patterns or
            "EXTENDED_STILLNESS" in patterns or
            "SEDENTARY_PATTERN" in patterns or
            "EXTENDED_RECLINED_POSTURE" in patterns):
            return "SUGGEST_MOVEMENT", {
                "max_words": 30,
                "tone": "gentle",
                "no_guilt": True
            }
        
        # PRIORITY 4: LOW (Check-in)
        if ("PROLONGED_SILENCE" in patterns or
            "SOCIAL_ISOLATION_MULTI_DAY" in patterns or
            "NIGHT_AUDIO_ACTIVITY" in patterns or
            "ERRATIC_SLEEP_SCHEDULE" in patterns):
            return "CHECK_IN", {
                "max_words": 25,
                "tone": "neutral",
                "no_pressure": True
            }
        
        # SPECIAL: Respect/Do not disturb
        if "MEETING_IN_PROGRESS" in patterns:
            return "DO_NOT_DISTURB", {
                "max_words": 0,
                "tone": "silent"
            }
        
        # DEFAULT: Monitor only
        return "NO_ACTION", {
            "max_words": 0,
            "tone": "neutral"
        }

    def _generate_briefing(self, packet):
        """
        Generate briefing for Local LLM.
        Format: Factual summary with detected patterns.
        """
        facts = packet["facts"]
        patterns = packet["patterns"]
        
        lines = []
        
        # Time & location
        lines.append(f"{facts['time']} {facts['room']}")
        if facts["quiet_hours"]:
            lines.append("quiet hours")
        
        # Duration facts
        lines.append(f"awake ~{facts['awake_hours']}h")
        if facts["stillness_min"] > 0:
            lines.append(f"still {facts['stillness_min']}m")
        if facts["time_since_break_min"] is not None:
            lines.append(f"no break ~{facts['time_since_break_min']}m")
        
        # Screen state
        if facts["screen_active"]:
            lines.append("screen active")
        
        # Vision geometry (if available)
        if facts["vision"] and facts["vision"]["face_detected"]:
            v = facts["vision"]
            if v["head_pitch_deg"] is not None:
                lines.append(f"head pitch {v['head_pitch_deg']}°")
            if v["body_configuration"]:
                lines.append(f"{v['body_configuration']}")
            if v["eyes_open"] is not None:
                lines.append(f"eyes {'open' if v['eyes_open'] else 'closed'}")
        
        # Patterns detected
        if patterns:
            lines.append(f"Patterns: {', '.join(patterns)}")
        
        briefing = "; ".join(lines) + "."
        return briefing


# Backward compatibility wrapper
def generate_summary_legacy(engine, state, history):
    """Legacy format for backward compatibility"""
    packet, briefing = engine.generate_summary(state, history)
    return packet, briefing

