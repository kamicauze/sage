import time
import os
try:
    from core.response_contract import router_result
except ImportError:
    from brain.core.response_contract import router_result

def in_quiet_hours(hour):
    if os.getenv("SAGE_DISABLE_QUIET_HOURS", "false").lower() == "true":
        return False
    return hour >= 23 or hour < 7

async def route(ai_out, evt=None, context=None, sage_instance=None):
    start_time = time.time()
    if not ai_out or ai_out.get("type") == "none":
        print("[Router] No output or type is 'none'")
        print(f"[Latency] router: {int((time.time() - start_time) * 1000)}ms")
        return router_result(True, "no_output")

    local_hour = context.get("local_hour", 12) if context else 12
    model = ai_out.get("model", "unknown")
    out_type = ai_out.get("type")
    
    # Check for Critical Override
    is_critical = evt.get("is_critical", False) if evt else False

    print(f"[Router] Processing AI output: type={out_type}, local_hour={local_hour}, critical={is_critical}")

    # Quiet hours: suppress output unless it's critical (Sterile Cockpit)
    if in_quiet_hours(local_hour) and not is_critical:
        print(f"[Router] Quiet hours; suppressed: {out_type} from {model}")
        print(f"[Latency] router: {int((time.time() - start_time) * 1000)}ms")
        return router_result(True, "quiet_hours")

    if out_type == "suggestion":
        conf = ai_out.get("confidence", 0.7)
        text = ai_out.get("text", "")
        print(f"[Router] Suggestion received: text=\"{text}\", confidence={conf}")

        # Personality-aware suppression: Check if response has strong personality markers
        # Strong personality markers indicate rich, contextual responses worth showing
        has_personality_markers = any(marker in text.lower() for marker in [
            "babes", "mahn", "chile", "fam", "bro", "manze", "si uko", "tutapanga",
            "pole sana", "sawa", "niaje", "poa", "uko fiti", "😂", "😭", "❤️", "✨"
        ])

        # Lower threshold for personality-rich responses
        min_confidence = 0.40 if has_personality_markers else 0.45

        if conf < min_confidence:
            print(f"[Router] Suggestion filtered: confidence {conf} < {min_confidence}")
            print(f"[Latency] router: {int((time.time() - start_time) * 1000)}ms")
            return router_result(True, "low_confidence")
            
        print(f"[Router] ({model}) suggestion: {text} (conf={conf})")
        print(f"[Latency] router: {int((time.time() - start_time) * 1000)}ms")
        return router_result(False, "allowed")

    if out_type == "action_plan":
        requires = ai_out.get("safety", {}).get("requires_confirmation", True)

        if requires:
            print(f"[Router] ({model}) action_plan queued (requires confirmation):", ai_out)
            print(f"[Latency] router: {int((time.time() - start_time) * 1000)}ms")
            return router_result(False, "requires_confirmation")

        for action in ai_out.get("actions", []):
            action_name = action.get("action")
            channel = action.get("channel")
            text = action.get("text", "")

            if action_name == "notify" and channel == "console":
                print(f"[Notify] {text}")
            elif action_name == "set_timer" and sage_instance:
                duration = action.get("duration_minutes", 10)
                label = action.get("text", "AI Timer")
                sage_instance.set_timer(duration, label=label)
            else:
                print(f"[Router] Blocked/unknown action: {action}")
        print(f"[Latency] router: {int((time.time() - start_time) * 1000)}ms")
        return router_result(False, "action_executed")

    print(f"[Latency] router: {int((time.time() - start_time) * 1000)}ms")
    return router_result(False, "noop")