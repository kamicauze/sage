import asyncio
import json
import time
from datetime import datetime
from main import on_event, sage, buffer

async def simulate_2am_office_session():
    print("✈️  SAGE FLIGHT SIMULATOR: 2 AM Office Session & Stillness")
    print("="*40)
    
    # 1. Arrival at 2:00 AM (Both presence and motion)
    room = "office"
    start_ts = int(time.time() * 1000)
    
    raw_event = {
        "type": "presence",
        "room": room,
        "motion": True,
        "presence": True,
        "ts": start_ts,
        "raw": {"sensor": "mmwave"}
    }
    
    print("--- 02:00 AM: Arrival ---")
    sage.pushiness = 0.9 # High pushiness for testing
    sage.handle_presence_event(raw_event)
    print(f"Mode: {sage.mode.value}")

    # 2. Simulate 25 minutes of stillness (Presence: True, Motion: False)
    print("\n--- 02:25 AM: 25 Minutes Later (Still Presence) ---")
    future_ts = start_ts + (25 * 60 * 1000)
    
    # Send a ping to update the 'last_presence_ts'
    raw_event_still = {
        "type": "presence",
        "room": room,
        "motion": False,
        "presence": True,
        "ts": future_ts,
        "raw": {"sensor": "mmwave"}
    }
    sage.handle_presence_event(raw_event_still)
    
    # Check for transitions (should detect STILL_PRESENT)
    transitions = sage.check_transitions(future_ts)
    for evt in transitions:
        print(f"Reflex Event: {evt['type']}")
    
    print(f"Mode: {sage.mode.value}") # Should be STILL_PRESENT

    # 3. Escalation Engine Check
    from core.escalation import EscalationEngine
    escalator = EscalationEngine(sage)
    
    # Simulate first alert
    escalator.evaluate_escalation(future_ts)
    # Simulate second alert (should now be CRITICAL since level >= 2 and it's 2 AM)
    future_ts_2 = future_ts + (15 * 60 * 1000)
    esc_event = escalator.evaluate_escalation(future_ts_2)
    
    if esc_event:
        print(f"Escalation Event: {esc_event['type']} (Level {esc_event['level']}, Critical: {esc_event.get('is_critical')})")
        
        # 4. Consult the Soul about the Escalation
        from ai.advisor import advise
        mock_now = datetime.now().replace(hour=2, minute=40)
        context = {
            "now": mock_now.isoformat(),
            "local_hour": 2,
            "day_of_week": mock_now.weekday(),
            "trigger": esc_event,
            "state": sage.get_snapshot(),
            "recent_events": []
        }
        
        print("\nConsulting the Soul about your 'Late Night Hustle' at 2 AM...")
        ai_out = await advise(context, {"reason": "escalation_alert"})
        
        print("\n" + "-"*20)
        print(f"SAGE RESPONSE (2 AM ESCALATION):")
        if ai_out.get("type") == "suggestion":
            print(f"Output: \"{ai_out.get('text')}\"")
        else:
            print(f"AI Output Type: {ai_out.get('type')}")
        print("-"*20)
        
        # 5. Router Test
        from action.router import route
        print("\nTesting Router (Sterile Cockpit Rule at 2 AM)...")
        await route(ai_out, evt=esc_event, context=context)

if __name__ == "__main__":
    asyncio.run(simulate_2am_office_session())

