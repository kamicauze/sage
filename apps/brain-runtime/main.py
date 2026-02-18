import paho.mqtt.client as mqtt
import json
import asyncio
import os
import time
import sys
import signal
import socket
from typing import Dict
from uuid import uuid4
from datetime import datetime
from dotenv import load_dotenv

class SingleInstanceLock:
    def __init__(self, port=60001):
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
    def acquire(self):
        try:
            self.sock.bind(('127.0.0.1', self.port))
            print(f"[Lock] Acquired single-instance lock on port {self.port}")
            return True
        except socket.error:
            print(f"[Lock] Error: Another instance of Sage Brain is already running!")
            return False

# Ensure single instance
instance_lock = SingleInstanceLock()
if not instance_lock.acquire():
    sys.exit(1)

# Load environment variables BEFORE importing modules that depend on them
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Import our new Python components
from core.state_machine import SageState
from core.escalation import EscalationEngine
from core.event_buffer import EventBuffer
from core.summary_engine import SummaryEngine
from ai.advisor import advise
from ai.cloud_client import cloud_brain
from ai.personalities import build_core_identity_prompt
from ai.warmup import run_preflight_checks
from ai.conversation import ConversationHistory, get_conversation  # NEW: Conversation history
from perception.parser import parse_presence
from action.router import route
try:
    from core.response_contract import normalize_router_result, normalize_voice_response
except ImportError:
    from brain.core.response_contract import normalize_router_result, normalize_voice_response

# Voice & Architect & Agent integration
from voice.handler import VoiceHandler
from voice.streamer import TTSStreamer
from bridges.architect_bridge import ArchitectBridge
from bridges.agent_bridge import AgentBridge

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
CHAT_REQUEST_TOPIC = os.getenv("SAGE_BRAIN_CHAT_REQUEST_TOPIC", "sage/brain/chat/request")
CHAT_RESPONSE_TOPIC = os.getenv("SAGE_BRAIN_CHAT_RESPONSE_TOPIC", "sage/brain/chat/response")

# Performance: Enable streaming TTS for lower perceived latency
# Disabled by default - can cause duplicate responses if not handled carefully
STREAM_TTS = os.getenv("SAGE_STREAM_TTS", "true").lower() == "true"


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _cloud_api_key_present(provider: str) -> bool:
    """Check whether required cloud key exists and looks non-placeholder."""
    if provider == "openai":
        key = (os.getenv("OPENAI_API_KEY") or "").strip()
        return bool(key and "your_" not in key.lower() and "placeholder" not in key.lower())

    key = (os.getenv("XAI_API_KEY") or os.getenv("GROK_API_KEY") or "").strip()
    return bool(key and "your_" not in key.lower() and "placeholder" not in key.lower())


# Optional cloud-only mode for low-VRAM machines:
# route voice/user reasoning directly to cloud and skip local LLM usage.
FORCE_CLOUD_REASONING = _env_flag("SAGE_FORCE_CLOUD_REASONING", False)
CLOUD_REASONING_PROVIDER = (os.getenv("SAGE_CLOUD_PROVIDER", "grok") or "grok").strip().lower()
if CLOUD_REASONING_PROVIDER not in {"grok", "openai"}:
    print(f"[Brain] Invalid SAGE_CLOUD_PROVIDER='{CLOUD_REASONING_PROVIDER}', falling back to 'grok'")
    CLOUD_REASONING_PROVIDER = "grok"
CLOUD_REASONING_MODEL = (os.getenv("SAGE_CLOUD_MODEL") or "").strip() or None
if FORCE_CLOUD_REASONING and not _cloud_api_key_present(CLOUD_REASONING_PROVIDER):
    print(
        f"[Brain] SAGE_FORCE_CLOUD_REASONING=true but {CLOUD_REASONING_PROVIDER} key is missing/invalid. "
        "Falling back to local reasoning mode."
    )
    FORCE_CLOUD_REASONING = False

# Initialize the state machine, escalation engine, event buffer, and summary engine
sage = SageState()
escalator = EscalationEngine(sage)
buffer = EventBuffer()
summarizer = SummaryEngine()

# Initialize Architect bridge, Agent bridge, and Voice handler
architect_bridge = ArchitectBridge()
agent_bridge = AgentBridge()

async def brain_voice_callback(intent, context, reason, on_token=None):
    """
    Callback for Voice -> Brain pathway.
    Converts voice intents into events for the existing pipeline.
    """
    event_data = {
        "type": reason,
        "text": intent.query,
        "intent": intent.type,
        "original_text": intent.original,
        "source": "voice_pipeline",
        "ts": int(time.time() * 1000)
    }
    # Wait for the full processing pipeline
    result = await on_event(event_data, on_token=on_token)
    route_hint = context.get("routing_hint", {}) if isinstance(context, dict) else {}
    default_route = route_hint.get("route", "LOCAL")

    if result and result.get("suppressed"):
        print(f"[VoiceCallback] Suppressed response: reason={result.get('reason')}")
        return normalize_voice_response(
            {
                "type": "none",
                "text": "",
                "suppressed": True,
                "reason": result.get("reason", "suppressed"),
            },
            default_intent=reason,
            default_route=default_route,
        )

    # Debug logging
    print(f"[VoiceCallback] on_event returned: type={result.get('type') if result else None}, has_text={bool(result.get('text')) if result else False}")

    # If we got a valid text response, return it. Otherwise fall back.
    if result and result.get("text"):
        print(f"[VoiceCallback] Returning success with text: {result['text'][:50]}...")
        return normalize_voice_response(
            {"type": "success", "text": result["text"]},
            default_intent=reason,
            default_route=default_route,
        )

    # Only use fallback if result is truly empty or has type "none"
    if result and result.get("type") == "none":
        print("[VoiceCallback] Result type is 'none', using fallback")
    elif not result:
        print("[VoiceCallback] Result is None, using fallback")
    else:
        print(f"[VoiceCallback] Result has no text field, using fallback. Result: {result}")

    # Personality-aware fallback based on current personality
    fallback_messages = {
        "kenyan_babe": "Eeh... nilikuskia lakini sijui niseme nini. 🤔",
        "sage": "I hear you, babes. Give me a sec to gather my thoughts.",
        "martin": "Heard that. Not sure how to respond right now."
    }
    fallback_text = fallback_messages.get(current_personality, "I heard you, but I'm not sure what to say.")

    return normalize_voice_response(
        {"type": "acknowledged", "text": fallback_text},
        default_intent=reason,
        default_route=default_route,
    )

voice_handler = VoiceHandler(brain_voice_callback, architect_bridge, agent_bridge)

def build_situational_summary(summary_packet, briefing):
    """
    Passes the comprehensive briefing directly to the cloud.
    The briefing now contains all sensor data and context.
    """
    return briefing

# Global State
current_personality = os.getenv("DEFAULT_PERSONALITY", "kenyan_babe")
chat_conversations: Dict[str, ConversationHistory] = {}


def _get_chat_conversation(conversation_id: str, max_turns: int = ConversationHistory.DEFAULT_MAX_TURNS) -> ConversationHistory:
    conversation = chat_conversations.get(conversation_id)
    if conversation is None:
        conversation = ConversationHistory(max_turns=max_turns)
        chat_conversations[conversation_id] = conversation
    return conversation

async def on_event(event_data, on_token=None):
    """
    Handles derived events (occupied, quiet, escalation, etc.)
    """
    if not event_data:
        return
        
    event_type = event_data.get("type")
    event_source = event_data.get("source")
    
    # Store event in buffer for history
    buffer.push(event_data)
    
    # Reset escalation if activity resumes
    if event_type == "activity_resumed":
        escalator.reset_escalation()
    
    # Ignore simple 'motion' or 'motion_false' for AI consulting to avoid noise
    if event_type in ["motion", "motion_false", "presence_ping"]:
        return
    print(f"[NervousSystem] Handling significant event: {event_type}")

    # FAST PATH: Check for explicit Grok/cloud requests to skip local LLM
    user_text_lower = event_data.get("text", "").lower()
    user_text_original = event_data.get("text", "")
    explicit_grok_request = any(phrase in user_text_lower for phrase in [
        "ask grok", "use grok", "grok", "switch to cloud", "ask cloud", "use cloud"
    ])
    is_smalltalk = event_type == "smalltalk"
    force_cloud_reasoning = FORCE_CLOUD_REASONING and event_type in ("user_intent", "smalltalk", "home_control")
    direct_cloud_reasoning = explicit_grok_request or force_cloud_reasoning
    
    state_snapshot = sage.get_snapshot()
    summary_packet = {}
    briefing = ""
    if not is_smalltalk:
        # 1. Generate Deterministic Summary (lightweight for fast path)
        # For fast path, use shorter time window to speed up summary generation
        t_summary = time.time()
        time_window = 15 * 60 * 1000 if direct_cloud_reasoning else 24 * 60 * 60 * 1000
        recent_events = buffer.get_recent(time_window)
        summary_packet, briefing = summarizer.generate_summary(state_snapshot, recent_events)
        print(f"[Latency] summary_engine: {int((time.time() - t_summary) * 1000)}ms")
        print(f"[SummaryEngine] {briefing}")

    # 2. Build Context for the Soul
    now = datetime.now()
    recent_events = [] if is_smalltalk else buffer.get_recent(15 * 60 * 1000)
    context = {
        "now": now.isoformat(),
        "local_hour": now.hour,
        "day_of_week": now.weekday(),
        "trigger": event_data,
        "state": state_snapshot,
        "recent_events": recent_events, # last 15m for context
        "summary": summary_packet,
        "personality": current_personality # Inject dynamic personality
    }

    # Get conversation history for context continuity
    conversation = get_conversation()
    
    # If this is a user message, add it to conversation history
    if user_text_original and event_type in ("user_intent", "smalltalk"):
        if event_source != "voice_pipeline":
            conversation.add_user_message(user_text_original, {"event_type": event_type})

        # Detect and record communication preferences (e.g., "don't say X")
        try:
            from brain.memory.communication_prefs import process_user_feedback
            if process_user_feedback(user_text_original):
                print(f"[NervousSystem] Communication preference detected and recorded")
        except Exception as e:
            print(f"[NervousSystem] Failed to process communication feedback: {e}")
    
    # FAST PATH: Skip local LLM if user explicitly asked for cloud,
    # or if global cloud-only reasoning mode is enabled.
    if direct_cloud_reasoning and event_type in ("user_intent", "smalltalk", "home_control"):
        handoff_reason = "explicit_grok_request" if explicit_grok_request else "forced_cloud_mode"
        if explicit_grok_request:
            print("[NervousSystem] Fast path: Direct cloud handoff (explicit request, skipping local LLM)")
        else:
            print(
                f"[NervousSystem] Cloud-only mode: Direct {CLOUD_REASONING_PROVIDER} handoff "
                f"(skipping local LLM)"
            )
        ai_out = {"type": "handoff", "reason": handoff_reason}
    elif is_smalltalk:
        meta = {"reason": "smalltalk"}
        ai_out = await advise(context, meta, conversation=conversation, on_token=on_token)
    else:
        meta = {"reason": event_type}
        ai_out = await advise(context, meta, conversation=conversation, on_token=on_token)
    
    # --- NEW: Handoff to Grok/Cloud ---
    # We handoff ONLY if the Soul explicitly asks for it (Local First Policy)
    if ai_out.get("type") == "handoff":
        handoff_reason = ai_out.get("reason", "")
        direct_handoff = handoff_reason in {"explicit_grok_request", "forced_cloud_mode"}

        # For fast path (explicit Grok requests), use simplified summary
        if direct_handoff:
            # Extract the actual question from the user text (remove "ask grok" etc.)
            user_query = user_text_original
            if handoff_reason == "explicit_grok_request":
                for phrase in ["ask grok", "use grok", "grok", "switch to cloud", "ask cloud", "use cloud"]:
                    user_query = user_query.replace(phrase, "").replace(phrase.capitalize(), "").strip()
            if not user_query or len(user_query) < 3:
                user_query = user_text_original

            # Simplified summary for fast path - include recent conversation when available
            convo_context = ""
            try:
                if conversation and not conversation.is_empty():
                    convo_context = conversation.get_formatted_history()
            except Exception:
                convo_context = ""

            convo_block = f"\n\nRecent conversation:\n{convo_context}" if convo_context else ""
            situational_summary = (
                f"User asked: {user_query}"
                f"{convo_block}\n\nBrief context: {briefing[:300]}..."
            )
            if handoff_reason == "explicit_grok_request":
                print("[NervousSystem] Fast path: Direct cloud handoff (skipped local LLM)")
            else:
                print(
                    f"[NervousSystem] Cloud-only mode: Direct {CLOUD_REASONING_PROVIDER} handoff "
                    f"(skipped local LLM)"
                )
        else:
            situational_summary = build_situational_summary(summary_packet, briefing)
            print(f"[NervousSystem] Handoff to Grok. Local Summary:\n{situational_summary}")

        # Use valid current personality
        system_prompt = build_core_identity_prompt(current_personality, include_examples=False)
        messages = [{"role": "system", "content": system_prompt}]
        if direct_handoff:
            messages.append({
                "role": "system",
                "content": (
                    "User requested cloud reasoning or cloud-only mode is enabled. "
                    "Answer directly and helpfully."
                )
            })
        messages.append({
            "role": "user",
            "content": f"{situational_summary}\nUser said: '{event_data.get('text', 'N/A')}'"
        })

        cloud_provider = CLOUD_REASONING_PROVIDER if handoff_reason == "forced_cloud_mode" else "grok"
        cloud_model = CLOUD_REASONING_MODEL if handoff_reason == "forced_cloud_mode" else None
        try:
            cloud_response = await cloud_brain.chat_stream(
                cloud_provider, messages, model=cloud_model, on_token=on_token
            )
            print(f"[Cloud:{cloud_provider}] Response: {cloud_response[:120]}...")
            # Convert Grok response into a suggestion format for the router
            ai_out = {
                "model": cloud_model or cloud_provider,
                "type": "suggestion",
                "text": cloud_response,
                "confidence": 1.0,
                "report": summary_packet # Pass the deterministic packet along
            }
        except Exception as e:
            print(f"[Cloud] Failed to reach cloud provider: {e}. Falling back to local suggestion.")

            # If cloud-only mode is enabled but cloud failed, gracefully fall back
            # to local reasoning instead of repeating API-key errors to the user.
            local_fallback_done = False
            if handoff_reason == "forced_cloud_mode":
                try:
                    print("[Cloud] Forced cloud mode failed; retrying this turn with local reasoning.")
                    local_meta = {"reason": event_type, "cloud_fallback": True}
                    ai_out = await advise(context, local_meta, conversation=conversation, on_token=on_token)
                    if ai_out and ai_out.get("type") and ai_out.get("type") != "handoff":
                        print("[Cloud] Local fallback succeeded.")
                        local_fallback_done = True
                except Exception as local_e:
                    print(f"[Cloud] Local fallback failed: {local_e}")

            if not local_fallback_done:
                # Personality-aware cloud error messages
                cloud_error_messages = {
                    "kenyan_babe": (
                        f"Mahn... nilitry ku-reach {cloud_provider} cloud lakini key iko missing ama invalid. "
                        "Weka OPENAI_API_KEY ama XAI_API_KEY kwa env, au uzime cloud-only mode."
                    ),
                    "sage": (
                        f"Tried to reach {cloud_provider} cloud, babes, but the API key is missing or invalid. "
                        "Set OPENAI_API_KEY or XAI_API_KEY, or disable cloud-only mode."
                    ),
                    "martin": (
                        f"Cloud call failed for {cloud_provider}. Missing/invalid API key. "
                        "Set OPENAI_API_KEY or XAI_API_KEY, or disable cloud-only mode."
                    )
                }
                error_text = cloud_error_messages.get(current_personality,
                    (
                        f"I tried to reach {cloud_provider} cloud, but the API key is missing or invalid. "
                        "Set OPENAI_API_KEY or XAI_API_KEY, or disable cloud-only mode."
                    ))

                ai_out = {
                    "type": "suggestion",
                    "text": error_text,
                    "model": "error_fallback"
                }
    
    # Route the AI output
    route_result = normalize_router_result(
        await route(ai_out, evt=event_data, context=context, sage_instance=sage)
    )
    if route_result and route_result.get("suppressed"):
        suppressed_payload = {
            "type": "none",
            "suppressed": True,
            "reason": route_result.get("reason"),
        }
        if event_source == "voice_pipeline":
            return normalize_voice_response(
                suppressed_payload,
                default_intent=event_data.get("intent", event_type),
                default_route="LOCAL",
            )
        return suppressed_payload
    
    # Record response in conversation history and action memory
    response_text = ai_out.get("text", "")
    if response_text:
        # Voice pathway persists conversation in handle_voice_transcript to avoid duplicates.
        if event_source != "voice_pipeline":
            # Add to conversation history
            conversation.add_assistant_message(response_text, {
                "type": ai_out.get("type"),
                "model": ai_out.get("model")
            })
            print(f"[Conversation] Added assistant message ({len(response_text)} chars), history now has {len(conversation.messages)} messages")

            # Record in action memory for self-awareness
            if ai_out.get("type") == "suggestion":
                sage.action_memory.record_suggestion(
                    response_text,
                    intent=summary_packet.get("intent")
                )
            elif ai_out.get("type") == "action_plan":
                # Record action plan actions
                for action in ai_out.get("actions", []):
                    if action.get("action") == "notify":
                        sage.action_memory.record_response(
                            action.get("text", ""),
                            response_type="notification"
                        )
    
    if event_source == "voice_pipeline":
        return normalize_voice_response(
            ai_out,
            default_intent=event_data.get("intent", event_type),
            default_route="LOCAL",
        )
    return ai_out

async def handle_voice_transcript(transcript: str, client):
    """
    Handle voice transcripts from STT service.
    Dispatches to Voice handler and publishes response.

    When STREAM_TTS is enabled, responses are streamed sentence-by-sentence
    for lower perceived latency.
    """
    start_time = time.time()

    # Clear any pending TTS to avoid old responses mixing with new ones
    client.publish("sage/tts/clear", json.dumps({"reason": "new_request"}))

    # Get conversation history for context
    t0 = time.time()
    conversation = get_conversation()
    print(f"[Latency] get_conversation: {int((time.time() - t0) * 1000)}ms")

    # Add user message to conversation history
    t1 = time.time()
    conversation.add_user_message(transcript, {"source": "voice"})
    print(f"[Latency] add_user_message: {int((time.time() - t1) * 1000)}ms")

    t2 = time.time()
    context = {
        "local_hour": datetime.now().hour,
        "day_of_week": datetime.now().weekday(),
        "state": sage.get_snapshot(),
        "conversation": conversation.get_context_summary()  # Include conversation context
    }
    print(f"[Latency] build_context: {int((time.time() - t2) * 1000)}ms")
    
    # Define Streaming Callback
    # We use a mutable list to track state across callbacks
    streaming_state = {"active": True, "window": "", "token_count": 0, "killed_reason": None}
    tts_streamer = TTSStreamer(client) if STREAM_TTS else None
    print(f"[Stream] STREAM_TTS={STREAM_TTS}, tts_streamer={'yes' if tts_streamer else 'no'}")

    async def stream_callback(token):
        if not token: return
        streaming_state["token_count"] += 1

        if not streaming_state["active"]:
            # Log once when stream gets killed
            if streaming_state["token_count"] == 1 or not streaming_state["killed_reason"]:
                pass  # Already logged at kill point
            return

        # Update rolling window (last 50 chars) to detect split delimiters
        streaming_state["window"] = (streaming_state["window"] + token)[-50:]
        window = streaming_state["window"]

        # Stop streaming if we detect the start of a JSON block or code fence
        # Check normalized window for {"type" or {"report" to handle whitespace/newlines
        normalized = window.replace('\n', '').replace(' ', '')

        # Detect JSON start - including incomplete fragments like {"type or just {
        json_indicators = [
            "```",
            '{"type"',
            '{"type',
            '{"report"',
            '{"report',
            '{"action',
            '{type',  # Without quotes
        ]

        # Only kill on actual JSON object start, not stray braces in prose
        if normalized.startswith('{') and '"' in normalized[:15]:
            streaming_state["active"] = False
            streaming_state["killed_reason"] = f"json_brace_quote: {normalized[:30]}"
            print(f"[Stream] KILLED at token #{streaming_state['token_count']}: {streaming_state['killed_reason']}")
            return

        for indicator in json_indicators:
            if indicator in normalized:
                streaming_state["active"] = False
                streaming_state["killed_reason"] = f"indicator '{indicator}' in: {normalized[:40]}"
                print(f"[Stream] KILLED at token #{streaming_state['token_count']}: {streaming_state['killed_reason']}")
                return

        # Log first token and every 20th
        if streaming_state["token_count"] == 1:
            print(f"[Stream] First token received, feeding to TTS streamer")
        elif streaming_state["token_count"] % 20 == 0:
            chunks_so_far = len(tts_streamer.sent_chunks) if tts_streamer else 0
            print(f"[Stream] Token #{streaming_state['token_count']}, TTS chunks sent: {chunks_so_far}")

        # Publish streaming chunk to UI
        client.publish("sage/voice/streaming", json.dumps({"text": token}))

        # True streaming mode: feed chunks directly to TTS sentence buffer.
        if tts_streamer is not None:
            await tts_streamer.feed(token)

    t3 = time.time()
    result = await voice_handler.handle_transcript(transcript, context, on_token=stream_callback)
    result = normalize_voice_response(
        result,
        default_intent="voice",
        default_route="LOCAL",
    )
    handler_ms = int((time.time() - t3) * 1000)
    chunks_sent = len(tts_streamer.sent_chunks) if tts_streamer else 0
    print(
        f"[Latency] voice_handler.handle_transcript: {handler_ms}ms | "
        f"[Stream] tokens={streaming_state['token_count']}, "
        f"tts_chunks={chunks_sent}, active={streaming_state['active']}, "
        f"killed={streaming_state.get('killed_reason', 'no')}"
    )

    response_text = result.get("text", "")

    # Add assistant response to conversation history
    t4 = time.time()
    if response_text:
        conversation.add_assistant_message(response_text, {
            "type": result.get("type"),
            "intent": result.get("intent")
        })

        # Also record in action memory
        sage.action_memory.record_response(response_text, response_type=result.get("type", "voice"))
    print(f"[Latency] save_to_history: {int((time.time() - t4) * 1000)}ms")
    
    if result.get("suppressed") or result.get("type") == "none":
        print(f"[Voice] Suppressed response; skipping publish")
        return

    if STREAM_TTS:
        streamed_chunks = 0

        # Flush any remaining token buffer (even if JSON detector killed active state,
        # sentences may have already been sent during feed()).
        if tts_streamer is not None:
            if streaming_state["active"]:
                await tts_streamer.flush()
            streamed_chunks = len(tts_streamer.sent_chunks)

        # Fallback: if token stream was unusable (e.g., JSON path), stream by sentence
        # from final response text so TTS still gets chunked playback.
        if response_text and tts_streamer is not None and streamed_chunks == 0:
            import re
            sentences = re.split(r'(?<=[.!?])\s+', response_text)
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                await tts_streamer._send_to_tts(sentence)
                await asyncio.sleep(0.03)
            streamed_chunks = len(tts_streamer.sent_chunks)

        # Publish final assistant text for UI/transcript bookkeeping, but do not
        # enqueue another TTS playback (speaker ignores no_tts payloads).
        final_text = response_text or (tts_streamer.get_full_response() if tts_streamer else "")
        if final_text:
            response_payload = json.dumps({
                "text": final_text,
                "type": result.get("type", ""),
                "status": result.get("status", ""),
                "source": "handle_voice_transcript_stream",
                "no_tts": True
            })
            print(f"[Voice] Streaming mode: final UI publish ({streamed_chunks} chunks)")
            t_publish = time.time()
            client.publish("sage/voice/response", response_payload)
            print(f"[Latency] publish: {int((time.time() - t_publish) * 1000)}ms")
    else:
        # Traditional: send full response at once
        response_payload = json.dumps({
            "text": response_text,
            "type": result.get("type", ""),
            "status": result.get("status", ""),
            "source": "handle_voice_transcript"  # Debug: track publish source
        })
        print(f"[Voice] Publishing response from handle_voice_transcript: {response_text[:50]}...")
        t_publish = time.time()
        client.publish("sage/voice/response", response_payload)
        print(f"[Latency] publish: {int((time.time() - t_publish) * 1000)}ms")
    
    elapsed_ms = int((time.time() - start_time) * 1000)
    print(f"[Voice] Response published in {elapsed_ms}ms: {response_text[:100]}...")


async def handle_chat_request(payload: dict, client):
    """
    Handle text chat requests over MQTT without invoking TTS.

    Request topic:  sage/brain/chat/request
    Response topic: sage/brain/chat/response
    """
    request_id = payload.get("request_id") or str(uuid4())
    conversation_id = payload.get("conversation_id") or "default"
    response_topic = payload.get("response_topic") or CHAT_RESPONSE_TOPIC
    user_text = str(payload.get("text", "")).strip()

    try:
        if not user_text:
            client.publish(
                response_topic,
                json.dumps(
                    {
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "success": False,
                        "error": "Missing text in chat request",
                    }
                ),
            )
            return

        reset = bool(payload.get("reset_conversation", False))
        max_turns = int(payload.get("max_history_turns", ConversationHistory.DEFAULT_MAX_TURNS))
        max_turns = max(1, min(max_turns, 50))

        if reset:
            chat_conversations.pop(conversation_id, None)

        conversation = _get_chat_conversation(conversation_id, max_turns=max_turns)
        conversation.max_turns = max_turns

        conversation.add_user_message(user_text, {"source": "chat_api", "request_id": request_id})

        context = {
            "trigger": {"type": "chat_request", "text": user_text},
            "local_hour": datetime.now().hour,
            "day_of_week": datetime.now().weekday(),
            "state": sage.get_snapshot(),
            "conversation": conversation.get_context_summary(),
            "personality": current_personality,
        }

        if payload.get("system_prompt"):
            context["chat_system_prompt"] = payload.get("system_prompt")

        reason = str(payload.get("reason", "user_intent"))
        ai_out = await advise(context, {"reason": reason}, conversation=conversation)
        response_text = (ai_out.get("text", "") or "").strip()

        if not response_text:
            response_text = "I heard you, but I could not generate a response."

        conversation.add_assistant_message(
            response_text,
            {
                "source": "chat_api",
                "request_id": request_id,
                "type": ai_out.get("type"),
                "model": ai_out.get("model"),
            },
        )

        client.publish(
            response_topic,
            json.dumps(
                {
                    "request_id": request_id,
                    "conversation_id": conversation_id,
                    "success": True,
                    "text": response_text,
                    "type": ai_out.get("type", "suggestion"),
                    "model": ai_out.get("model", "brain_runtime"),
                    "personality": current_personality,
                    "ts": int(time.time() * 1000),
                }
            ),
        )
    except Exception as e:
        client.publish(
            response_topic,
            json.dumps(
                {
                    "request_id": request_id,
                    "conversation_id": conversation_id,
                    "success": False,
                    "error": str(e),
                }
            ),
        )


def on_message(client, userdata, msg):
    global current_personality
    try:
        topic = msg.topic
        payload_str = msg.payload.decode()
        
        # Brain Config Handler
        if topic == "sage/brain/config":
            try:
                config = json.loads(payload_str)
                new_personality = config.get("personality")
                if "raw_mode" in config:
                    try:
                        from ai.advisor import set_raw_mode
                        enabled = bool(config.get("raw_mode"))
                        set_raw_mode(enabled)
                        print(f"[Brain] Raw mode set to: {enabled}")
                    except Exception as e:
                        print(f"[Brain] Could not set raw mode: {e}")

                if new_personality:
                    if new_personality != current_personality:
                        current_personality = new_personality
                        print(f"[Brain] Personality switched to: {current_personality}")
                        # Force a core prompt refresh so the new persona takes effect
                        try:
                            conversation = get_conversation()
                            conversation.request_core_prompt_refresh()
                        except Exception as e:
                            print(f"[Brain] Could not refresh persona prompt: {e}")
                    # Broadcast confirmation so UI updates (avoid echo loops)
                    if config.get("source") != "brain":
                        client.publish(
                            "sage/brain/config",
                            json.dumps({
                                "personality": current_personality,
                                "raw_mode": config.get("raw_mode"),
                                "source": "brain"
                            })
                        )
            except Exception as e:
                print(f"[Brain] Config update failed: {e}")
            return
        
        # Brain Command Handler (clear conversation, clear memory, etc.)
        if topic == "sage/brain/command":
            try:
                cmd_data = json.loads(payload_str)
                command = cmd_data.get("command", "")
                
                if command == "clear_conversation":
                    # Clear current conversation (saves to memory first)
                    conversation = get_conversation()
                    conversation.clear(save_to_memory=True)
                    print("[Brain] Conversation cleared (saved to memory)")
                    
                elif command == "clear_memory":
                    # Clear all long-term memory
                    try:
                        from brain.memory.sage_memory import get_memory
                        memory = get_memory()
                        memory.clear_all()
                        print("[Brain] All memory cleared")
                    except ImportError:
                        print("[Brain] Memory module not available")
                    
                elif command == "clear_episodes":
                    # Clear only episodic memories
                    try:
                        from brain.memory.sage_memory import get_memory
                        memory = get_memory()
                        memory.clear_episodes()
                        print("[Brain] Episodes cleared")
                    except ImportError:
                        print("[Brain] Memory module not available")
                        
            except Exception as e:
                print(f"[Brain] Command failed: {e}")
            return

        # Voice transcript handler
        if topic == "sage/voice/transcript":
            print(f"[MQTT] Voice transcript received: '{payload_str[:50]}...'")
            asyncio.run_coroutine_threadsafe(
                handle_voice_transcript(payload_str, client),
                loop
            )
            return

        # Text chat request handler (request/response over MQTT)
        if topic == CHAT_REQUEST_TOPIC:
            try:
                payload = json.loads(payload_str)
                if not isinstance(payload, dict):
                    payload = {"text": str(payload)}
            except Exception:
                payload = {"text": payload_str}

            if "request_id" not in payload:
                payload["request_id"] = str(uuid4())

            asyncio.run_coroutine_threadsafe(
                handle_chat_request(payload, client),
                loop,
            )
            return
        
        # Agent approval handling: when an agent asks for approval and user
        # responds via voice, the next transcript is routed here as approval.
        if topic.startswith("sage/agent/") and topic.endswith("/needs_approval"):
            # Agent is asking for approval — Sage will speak it via the
            # payload already published to sage/voice/response by the agent.
            # Nothing to do here; the agent handles its own TTS publishing.
            return

        if topic.startswith("sage/agent/") and topic.endswith("/status"):
            # Agent status update — log it
            try:
                data = json.loads(payload_str)
                agent_name = data.get("agent", "unknown")
                status = data.get("status", "unknown")
                print(f"[Agent:{agent_name}] Status: {status}")
            except Exception:
                pass
            return

        # 1. Parse raw message (presence sensors)
        raw_event = parse_presence(topic, payload_str)
        if not raw_event:
            return

        # 2. Update state machine and get derived event
        derived = sage.handle_presence_event(raw_event)
        
        # 3. Handle the event
        asyncio.run_coroutine_threadsafe(on_event(derived), loop)
        
    except Exception as e:
        print(f"[MQTT] Error processing message: {e}")

async def main_loop():
    global loop
    loop = asyncio.get_running_loop()
    # ... (Preflight checks)
    cleared = await run_preflight_checks()
    if not cleared:
        print("[Abort] Critical systems offline. Sage cannot take off.")
        return

    print("🧠 Sage Nervous System starting...")
    client = mqtt.Client()
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.publish("sage/brain/status", json.dumps({"status": "starting"}))

        # Subscribe to topics
        client.subscribe("sage/sensors/+/presence")  # Canonical presence sensors
        client.subscribe("sage/presence/+")          # Compatibility presence topic
        client.subscribe("sage/voice/transcript")     # Voice commands from STT
        client.subscribe(CHAT_REQUEST_TOPIC)          # Text chat RPC for API/mobile
        client.subscribe("sage/brain/config")         # Brain configuration
        client.subscribe("sage/brain/command")        # Brain commands (clear memory, etc.)
        client.subscribe("sage/agent/+/needs_approval")  # Agent approval requests
        client.subscribe("sage/agent/+/status")          # Agent status updates
        client.subscribe("sage/agent/+/command")         # Agent commands

        print(
            "[MQTT] Subscribed to: sage/sensors/+/presence, sage/presence/+, "
            f"sage/voice/transcript, {CHAT_REQUEST_TOPIC}, sage/brain/config, sage/agent/+/*"
        )
        client.loop_start()

        # Preload memory system to avoid first-message latency
        print("[Brain] Preloading memory system...")
        preload_start = time.time()
        from brain.memory.sage_memory import get_memory
        _ = get_memory()  # Initialize singleton
        preload_time = int((time.time() - preload_start) * 1000)
        print(f"[Brain] ✓ Memory preloaded in {preload_time}ms")

        # Initialize Agent bridge with live MQTT and brain function
        async def agent_brain_fn(messages):
            """LLM callable for agents — routes through advise or cloud."""
            prompt = messages[-1]["content"] if messages else ""
            if FORCE_CLOUD_REASONING:
                return await cloud_brain.chat_stream(
                    CLOUD_REASONING_PROVIDER, messages,
                    model=CLOUD_REASONING_MODEL,
                )
            result = await advise(
                {"type": "agent_reasoning", "text": prompt},
                meta={"reason": "agent_task"},
            )
            return result.get("text", "") if isinstance(result, dict) else str(result)

        agent_bridge.initialize(
            mqtt_client=client,
            brain_fn=agent_brain_fn,
            architect_bridge=architect_bridge,
        )
        print("[Brain] ✓ Agent system initialized")

        # Announce readiness
        client.publish("sage/brain/status", json.dumps({"status": "ready"}))
        print("[Brain] System Ready. Pulse normal.")
        
        while True:
            now_ms = int(time.time() * 1000)
            
            # 1. Check for quiet and stillness transitions
            transitions = sage.check_transitions(now_ms)
            for evt in transitions:
                await on_event(evt)
            
            # 2. Check for expired timers
            expired_timers = sage.check_timers(now_ms)
            for timer in expired_timers:
                timer_evt = {
                    "type": "timer_expired",
                    "label": timer["label"],
                    "ts": now_ms,
                    "metadata": timer["metadata"]
                }
                await on_event(timer_evt)
            
            # 3. Evaluate Escalation (The Pushiness Knob)
            esc_event = escalator.evaluate_escalation(now_ms)
            if esc_event:
                await on_event(esc_event)
                
            await asyncio.sleep(10)
            
    except Exception as e:
        print(f"[Error] {e}")
    finally:
        # Phase 3: Save personality preferences on shutdown
        try:
            from ai.personality_engine import get_personality_engine
            engine = get_personality_engine()
            engine.save_preferences()
            print("[Brain] Personality preferences saved")
        except Exception as pe:
            print(f"[Brain] Could not save personality preferences: {pe}")

        client.loop_stop()


def shutdown_handler(signum, frame):
    """Handle graceful shutdown on SIGINT/SIGTERM."""
    print(f"\n[Brain] Received signal {signum}, shutting down...")
    # Save personality preferences
    try:
        from ai.personality_engine import get_personality_engine
        engine = get_personality_engine()
        engine.save_preferences()
        print("[Brain] Personality preferences saved")
    except Exception as pe:
        print(f"[Brain] Could not save personality preferences: {pe}")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    asyncio.run(main_loop())