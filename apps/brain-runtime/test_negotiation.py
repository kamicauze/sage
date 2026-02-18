import asyncio
import json
import time
from datetime import datetime
from main import on_event, sage, escalator

async def simulate_negotiation():
    print("✈️  SAGE FLIGHT SIMULATOR: Late Night Negotiation")
    print("="*40)
    
    # 1. Force the state into STILL_PRESENT at 2:40 AM
    from core.state_machine import SageMode
    sage.mode = SageMode.STILL_PRESENT
    sage.rooms["office"] = {
        "occupied": True,
        "last_motion_ts": int(time.time() * 1000) - (25 * 60 * 1000),
        "last_presence_ts": int(time.time() * 1000),
        "raw": {}
    }
    
    # Trigger a critical escalation alert
    esc_event = {
        "type": "escalation_alert",
        "level": 3,
        "reason": "stillness_prolonged",
        "is_critical": True,
        "ts": int(time.time() * 1000)
    }
    
    print("--- 02:40 AM: Critical Alert Triggered ---")
    await on_event(esc_event)
    
    # 2. Simulate User Response: "chill kiasi dakika kumi tu"
    print("\n--- User Responds: 'chill kiasi dakika kumi tu' ---")
    user_intent = {
        "type": "user_intent",
        "intent": "request_extension",
        "text": "chill kiasi dakika kumi tu",
        "duration_minutes": 1, 
        "ts": int(time.time() * 1000),
        "is_critical": True # Allow breakthrough for conversation
    }
    
    await on_event(user_intent)
    
    print(f"\nActive Timers: {sage.active_timers}")
    
    # 3. Fast-forward to timer expiry
    print("\n--- Fast-forwarding 1 minute ---")
    expiry_ms = sage.active_timers[0]["expiry_ts"]
    
    # Manually trigger timer check as if main loop found it
    timer_evt = {
        "type": "timer_expired",
        "label": "10-minute break extension",
        "ts": expiry_ms,
        "metadata": {}
    }
    
    print("\n--- Timer Expired! ---")
    # Clear timers manually for simulation
    sage.active_timers = []
    await on_event(timer_evt)

if __name__ == "__main__":
    asyncio.run(simulate_negotiation())

