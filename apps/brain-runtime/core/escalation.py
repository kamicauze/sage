import time

class EscalationEngine:
    def __init__(self, sage_state):
        self.sage = sage_state
        self.last_alert_ts = 0
        self.escalation_level = 0 # 0 to 5
        
    def evaluate_escalation(self, now_ms=None):
        """
        Main logic for escalating accountability.
        """
        if now_ms is None:
            now_ms = int(time.time() * 1000)
            
        snapshot = self.sage.get_snapshot()
        mode = snapshot["mode"]
        pushiness = snapshot["pushiness"]
        
        # Scenario 1: Stillness/Bed Rot Detection
        if mode == "STILL_PRESENT":
            return self._handle_stillness_escalation(now_ms, pushiness)
            
        # Scenario 2: Presence when it should be ABSENT (Future: Schedule integration)
        
        return None

    def _handle_stillness_escalation(self, now_ms, pushiness):
        """
        Escalates if user stays in STILL_PRESENT mode.
        """
        # Time since last alert
        time_since_alert = (now_ms - self.last_alert_ts) / 1000 # seconds
        
        # How often to bug the user based on pushiness
        alert_interval = max(120, (1.0 - pushiness) * 3600) 
        
        if time_since_alert > alert_interval:
            self.escalation_level = min(5, self.escalation_level + 1)
            self.last_alert_ts = now_ms
            
            # CRITICAL OVERRIDE: 
            # If it's very late (e.g., 1 AM to 5 AM) and we reach Level 2+, it's critical.
            from datetime import datetime
            hour = datetime.fromtimestamp(now_ms / 1000).hour
            is_critical = (1 <= hour <= 5) and (self.escalation_level >= 2)

            return {
                "type": "escalation_alert",
                "level": self.escalation_level,
                "reason": "stillness_prolonged",
                "pushiness": pushiness,
                "action": "notify_user",
                "severity": self.escalation_level / 5.0,
                "is_critical": is_critical
            }
            
        return None

    def reset_escalation(self):
        if self.escalation_level > 0:
            print("[Escalation] Resetting escalation levels.")
            self.escalation_level = 0
            self.last_alert_ts = 0

