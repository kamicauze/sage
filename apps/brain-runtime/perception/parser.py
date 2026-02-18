import json
import time


def to_bool(value):
    """Best-effort bool normalization for heterogeneous sensor payloads."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"true", "1", "yes", "on", "present", "detected"}
    return False


def normalize_timestamp(ts):
    """
    Normalizes a timestamp to milliseconds.
    """
    try:
        n = float(ts)
        # If it's in seconds (like unix timestamp), convert to ms
        if n < 1e12:
            return int(n * 1000)
        return int(n)
    except (ValueError, TypeError):
        return int(time.time() * 1000)

def parse_presence(topic, payload_str):
    """
    Parses a presence message from MQTT.
    Topic format expected: sage/sensors/<room>/presence
    Also supports: sage/presence/<room>
    """
    parts = topic.split('/')
    if len(parts) < 3:
        return None
    
    room = parts[2]
    
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        print(f"[Perception] Error parsing JSON payload on {topic}")
        return None

    # Handle various ways motion/presence might be represented
    motion_val = payload.get("motion")
    presence_val = payload.get("presence", payload.get("present", motion_val))

    motion = to_bool(motion_val)
    presence = to_bool(presence_val)

    ts = normalize_timestamp(payload.get("ts", payload.get("timestamp", time.time() * 1000)))
    
    return {
        "type": "presence_update",
        "room": room,
        "motion": motion,
        "presence": presence,
        "ts": ts,
        "raw": payload
    }
