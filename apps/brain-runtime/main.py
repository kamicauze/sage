import paho.mqtt.client as mqtt
import json
import asyncio
import os
import time
import sys
import signal
import socket
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
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
from integrations.smartthings import handle_home_control_request
from integrations.google_workspace import handle_google_workspace_text
from integrations.project_git import handle_project_git_text
try:
    from core.response_contract import normalize_router_result, normalize_voice_response
except ImportError:
    from brain.core.response_contract import normalize_router_result, normalize_voice_response

# Voice & Architect & Agent integration
from voice.handler import VoiceHandler
from voice.streamer import TTSStreamer
from bridges.architect_bridge import ArchitectBridge
from bridges.agent_bridge import AgentBridge
from shared.intent import Intent, classify_intent, get_task_type_from_intent
from text_intent_router import (
    looks_like_architect_text_request,
    parse_text_intent_command,
)

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
CHAT_REQUEST_TOPIC = os.getenv("SAGE_BRAIN_CHAT_REQUEST_TOPIC", "sage/brain/chat/request")
CHAT_RESPONSE_TOPIC = os.getenv("SAGE_BRAIN_CHAT_RESPONSE_TOPIC", "sage/brain/chat/response")
BRAIN_CONFIG_TOPIC = os.getenv("SAGE_BRAIN_CONFIG_TOPIC", "sage/brain/config")
BRAIN_COMMAND_TOPIC = os.getenv("SAGE_BRAIN_COMMAND_TOPIC", "sage/brain/command")
BRAIN_STATUS_TOPIC = os.getenv("SAGE_BRAIN_STATUS_TOPIC", "sage/brain/status")
MQTT_SUBSCRIPTIONS = [
    "sage/sensors/+/presence",   # Canonical presence sensors
    "sage/presence/+",           # Compatibility presence topic
    "sage/vision/+/vlm",         # Vision-language summaries from camera nodes
    "sage/vision/+/metrics",     # Vision latency/queue metrics
    "sage/voice/transcript",     # Voice commands from STT
    CHAT_REQUEST_TOPIC,          # Text chat RPC for API/mobile
    BRAIN_CONFIG_TOPIC,          # Brain configuration
    BRAIN_COMMAND_TOPIC,         # Brain commands (clear memory, etc.)
    "sage/agent/+/needs_approval",
    "sage/agent/+/status",
    "sage/agent/+/command",
]

# Performance: Enable streaming TTS for lower perceived latency
# Disabled by default - can cause duplicate responses if not handled carefully
STREAM_TTS = os.getenv("SAGE_STREAM_TTS", "true").lower() == "true"
VOICE_INPUT_ENABLED = os.getenv("SAGE_VOICE_INPUT_ENABLED", "true").lower() == "true"
VOICE_OUTPUT_ENABLED = os.getenv("SAGE_VOICE_OUTPUT_ENABLED", "true").lower() == "true"
CHAT_MINIMAL_PROMPT_DEFAULT = os.getenv("SAGE_CHAT_MINIMAL_PROMPT_DEFAULT", "false").lower() == "true"


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
MEMORY_PRELOAD_ENABLED = _env_flag("SAGE_MEMORY_PRELOAD", True)

# Approval gate for cloud calls (opt-in)
REQUIRE_CLOUD_APPROVAL = _env_flag("SAGE_REQUIRE_CLOUD_APPROVAL", False)
APPROVAL_TIMEOUT_S = int(os.getenv("SAGE_APPROVAL_TIMEOUT_S", "30"))
ARCHITECT_API_URL = (os.getenv("SAGE_ARCHITECT_API_URL", "http://localhost:8000") or "http://localhost:8000").rstrip("/")

# Request deduplication
_REQUEST_DEDUP_CACHE: Dict[str, float] = {}
DEDUP_WINDOW_SEC = int(os.getenv("SAGE_DEDUP_WINDOW_SEC", "300"))

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
current_raw_mode = os.getenv("SAGE_RAW_MODE", "false").lower() == "true"
chat_conversations: Dict[str, ConversationHistory] = {}
_external_cli_client = None


def _subscribe_all_topics(client: mqtt.Client):
    """Subscribe to all runtime topics (startup + reconnect-safe)."""
    for topic in MQTT_SUBSCRIPTIONS:
        client.subscribe(topic)


def _on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[MQTT] Connected to broker")
        _subscribe_all_topics(client)
        print(
            "[MQTT] Subscribed to: sage/sensors/+/presence, sage/presence/+, "
            "sage/vision/+/vlm, sage/vision/+/metrics, "
            f"sage/voice/transcript, {CHAT_REQUEST_TOPIC}, {BRAIN_CONFIG_TOPIC}, sage/agent/+/*"
        )
    else:
        print(f"[MQTT] Connect failed rc={rc}")


def _on_mqtt_disconnect(client, userdata, rc, properties=None):
    if rc == 0:
        print("[MQTT] Disconnected cleanly")
    else:
        print(f"[MQTT] Disconnected unexpectedly rc={rc}; waiting for reconnect")


def _extract_human_text(text: str) -> str:
    """
    Best-effort cleanup for model outputs that accidentally contain JSON blobs.
    Returns plain assistant text when possible.
    """
    if not isinstance(text, str):
        return ""

    cleaned = text.strip()
    if not cleaned:
        return ""

    # Full JSON object output -> extract text field.
    if cleaned.startswith("{"):
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                inner = data.get("text")
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
        except Exception:
            # Partial JSON -> salvage "text": "..." when available.
            match = re.search(r'"text"\s*:\s*"([^"]+)', cleaned, re.DOTALL)
            if match:
                return match.group(1).replace('\\"', '"').strip()

            # If it clearly looks like internal JSON/report noise, drop it.
            if '"type"' in cleaned or '"report"' in cleaned or '"trigger"' in cleaned:
                return ""

    return cleaned


def _publish_brain_status(client: mqtt.Client, status: str = "ready", last_command: Optional[str] = None):
    payload = {
        "status": status,
        "personality": current_personality,
        "raw_mode": bool(current_raw_mode),
        "voice_input_enabled": bool(VOICE_INPUT_ENABLED),
        "voice_output_enabled": bool(VOICE_OUTPUT_ENABLED),
        "last_command": last_command,
        "ts": int(time.time() * 1000),
    }
    client.publish(BRAIN_STATUS_TOPIC, json.dumps(payload), retain=True)


def _get_chat_conversation(conversation_id: str, max_turns: int = ConversationHistory.DEFAULT_MAX_TURNS) -> ConversationHistory:
    conversation = chat_conversations.get(conversation_id)
    if conversation is None:
        conversation = ConversationHistory(max_turns=max_turns)
        chat_conversations[conversation_id] = conversation
    return conversation


def _looks_like_research_text(text: str) -> bool:
    lowered = str(text or "").lower()
    if not lowered:
        return False
    markers = (
        "research",
        "analyze",
        "analysis",
        "deep dive",
        "benchmark",
        "compare",
        "investigate",
        "study",
        "literature",
        "evidence",
    )
    return any(marker in lowered for marker in markers)


def _resolve_cli_override(intent_type: str, text: str) -> Optional[Dict[str, str]]:
    """
    Resolve external CLI routing override from env.

    SAGE_TEXT_CLI_PROVIDER: off|codex_cli|claude_cli
    SAGE_TEXT_CLI_SCOPE: architect,debug,research,all
    SAGE_TEXT_CLI_MODEL: optional model label passed to CLI
    """
    provider = (os.getenv("SAGE_TEXT_CLI_PROVIDER", "off") or "off").strip().lower()
    if provider not in {"codex_cli", "claude_cli"}:
        return None

    scope_raw = (os.getenv("SAGE_TEXT_CLI_SCOPE", "architect,debug,research") or "").strip().lower()
    scope = {part.strip() for part in scope_raw.split(",") if part.strip()}
    if not scope:
        scope = {"architect"}
    if "all" in scope:
        enabled = True
    else:
        lowered = str(text or "").lower()
        debug_markers = {"debug", "fix", "traceback", "stack trace", "failing test"}
        enabled = (
            ("architect" in scope and intent_type == "architect_task")
            or ("debug" in scope and any(marker in lowered for marker in debug_markers))
            or ("research" in scope and _looks_like_research_text(text))
        )

    if not enabled:
        return None

    model = (os.getenv("SAGE_TEXT_CLI_MODEL") or "").strip() or provider
    return {"provider": provider, "model": model}


def _get_external_cli_client():
    global _external_cli_client
    if _external_cli_client is not None:
        return _external_cli_client

    from architect.llm import LLMClient
    _external_cli_client = LLMClient()
    return _external_cli_client


async def _chat_with_external_cli(messages: list, provider: str, model: Optional[str] = None) -> str:
    client = _get_external_cli_client()
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: client.chat(messages, stream=False, provider=provider, model=model),
    )


def _apply_architect_artifacts_to_repo(
    *,
    architect_bridge: ArchitectBridge,
    project_hint: Optional[str],
    artifacts: list,
) -> Dict[str, Any]:
    """
    Copy generated artifacts from Architect workspace sandbox into repo files.
    This is opt-in from text commands to support real file edits.
    """
    if not artifacts:
        return {
            "copied_count": 0,
            "skipped_count": 0,
            "copied": [],
            "skipped": [{"path": "", "reason": "no_artifacts"}],
        }

    manifest_path = architect_bridge._resolve_manifest(project_hint) if architect_bridge else None
    if not manifest_path:
        return {
            "copied_count": 0,
            "skipped_count": len(artifacts),
            "copied": [],
            "skipped": [{"path": str(p), "reason": "manifest_not_found"} for p in artifacts],
        }

    from architect.manifest import ProjectManifest
    from architect.paths import workspace_sandbox_path

    manifest = ProjectManifest.load(str(manifest_path))
    sandbox_root = Path(workspace_sandbox_path(manifest.id)).resolve()
    repo_root = Path(manifest.repo_path).resolve()

    copied = []
    skipped = []

    for rel_path in artifacts:
        rel_str = str(rel_path or "").strip()
        if not rel_str:
            continue

        src = (sandbox_root / rel_str).resolve()
        if not src.exists() or not src.is_file():
            skipped.append({"path": rel_str, "reason": "source_missing"})
            continue

        dst = (repo_root / rel_str).resolve()
        try:
            dst.relative_to(repo_root)
        except Exception:
            skipped.append({"path": rel_str, "reason": "unsafe_destination"})
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel_str)

    return {
        "copied_count": len(copied),
        "skipped_count": len(skipped),
        "copied": copied,
        "skipped": skipped,
    }

async def on_event(event_data, on_token=None):
    """
    Handles derived events (occupied, quiet, escalation, etc.)
    """
    global _REQUEST_DEDUP_CACHE

    if not event_data:
        return

    event_type = event_data.get("type")
    event_source = event_data.get("source")

    # Request deduplication: skip duplicate queries within the window
    user_text_dedup = event_data.get("text", "")
    if user_text_dedup and DEDUP_WINDOW_SEC > 0:
        import hashlib as _hl
        dedup_key = _hl.md5(f"{event_type}:{user_text_dedup}".encode()).hexdigest()
        now = time.time()
        _REQUEST_DEDUP_CACHE = {
            k: v for k, v in _REQUEST_DEDUP_CACHE.items() if now - v < DEDUP_WINDOW_SEC
        }
        if dedup_key in _REQUEST_DEDUP_CACHE:
            elapsed = now - _REQUEST_DEDUP_CACHE[dedup_key]
            print(f"[Dedup] Skipping duplicate request (seen {elapsed:.1f}s ago)")
            return {"type": "none", "dedup": True}
        _REQUEST_DEDUP_CACHE[dedup_key] = now

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
    
    skip_router = False
    ai_out = None

    if user_text_original and event_type in ("user_intent", "smalltalk"):
        project_git_result = handle_project_git_text(user_text=user_text_original)
        if project_git_result.get("handled"):
            ai_out = {
                "type": "suggestion",
                "text": project_git_result.get("response_text", ""),
                "confidence": 1.0,
                "model": "project_git",
                "report": summary_packet,
            }

    if event_type == "home_control":
        smartthings_result = await handle_home_control_request(user_text_original)
        if smartthings_result.get("handled"):
            skip_router = True
            success = bool(smartthings_result.get("success"))
            ai_out = {
                "type": "suggestion",
                "text": smartthings_result.get("text", "Done."),
                "confidence": 1.0 if success else 0.5,
                "model": "smartthings",
                "report": summary_packet,
            }

    # FAST PATH: Skip local LLM if user explicitly asked for cloud,
    # or if global cloud-only reasoning mode is enabled.
    if ai_out is None:
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

    # --- Confidence-based smart escalation ---
    if ai_out and ai_out.get("type") not in ("handoff", "none", None):
        from ai.escalation import should_escalate_to_cloud
        should_escalate, escalation_reason = should_escalate_to_cloud(
            ai_out, event_type, meta.get("reason", "") if meta else "",
            user_text_original, cloud_provider=CLOUD_REASONING_PROVIDER
        )
        if should_escalate:
            original_conf = ai_out.get("confidence", "N/A")
            original_model = ai_out.get("model", "unknown")
            print(
                f"[Escalation] Triggering cloud handoff: reason={escalation_reason}, "
                f"confidence={original_conf}, model={original_model}"
            )
            ai_out["_local_fallback"] = {
                "text": ai_out.get("text", ""),
                "model": original_model,
                "confidence": original_conf,
            }
            ai_out["type"] = "handoff"
            ai_out["reason"] = "low_confidence"
            ai_out["escalation_detail"] = escalation_reason
        else:
            if ai_out.get("confidence") is not None:
                print(
                    f"[Escalation] No escalation: reason={escalation_reason}, "
                    f"confidence={ai_out.get('confidence')}"
                )

    # --- Handoff to Grok/Cloud ---
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

            # Simplified summary for fast path - include recent conversation (compressed)
            convo_context = ""
            try:
                if conversation and not conversation.is_empty():
                    convo_context = conversation.get_compressed_history()
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

        # Generate privacy-safe behavioral hint from memory
        behavioral_hint = ""
        try:
            from ai.context_builder import build_privacy_safe_context
            behavioral_hint = await build_privacy_safe_context(
                summary_packet=summary_packet,
                conversation=conversation,
                user_message=user_text_original
            )
        except Exception as e:
            print(f"[Privacy] Could not generate behavioral hint: {e}")

        # Use minimal personality prompt for cloud (strips verbose boilerplate)
        system_prompt = build_core_identity_prompt(
            current_personality, include_examples=False, minimal=True
        )
        messages = [{"role": "system", "content": system_prompt}]

        # Inject behavioral hint from privacy filter
        if behavioral_hint:
            messages.append({
                "role": "system",
                "content": f"Behavioral context (from prior interactions): {behavioral_hint}"
            })

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

        # --- Approval gate (opt-in) ---
        proceed_with_cloud = True
        if REQUIRE_CLOUD_APPROVAL and not direct_handoff:
            from ai.escalation import request_cloud_approval
            approval_reason = ai_out.get("escalation_detail", handoff_reason)
            approved, approval_detail = await request_cloud_approval(
                user_text_original, cloud_provider, approval_reason,
                api_url=ARCHITECT_API_URL, timeout_s=APPROVAL_TIMEOUT_S
            )
            if not approved:
                proceed_with_cloud = False
                approval_messages = {
                    "kenyan_babe": f"Cloud request haikupitishwa ({approval_detail}). Nitajibu locally.",
                    "sage": f"Cloud call wasn't approved ({approval_detail}). I'll answer locally, babes.",
                    "martin": f"Cloud request not approved ({approval_detail}). Using local response.",
                }
                fallback_notice = approval_messages.get(
                    current_personality,
                    f"Cloud request not approved ({approval_detail}). Using local response."
                )

                local_fallback_text = ai_out.get("_local_fallback", {}).get("text", "")
                if local_fallback_text:
                    ai_out = {
                        "type": "suggestion",
                        "text": f"{fallback_notice}\n\n{local_fallback_text}",
                        "model": ai_out.get("_local_fallback", {}).get("model", "local"),
                        "confidence": ai_out.get("_local_fallback", {}).get("confidence", 0.5),
                        "approval_status": approval_detail,
                        "report": summary_packet,
                    }
                else:
                    local_meta = {"reason": event_type, "cloud_approval_denied": True}
                    ai_out = await advise(context, local_meta, conversation=conversation, on_token=on_token)
                    if ai_out.get("text"):
                        ai_out["text"] = f"{fallback_notice}\n\n{ai_out['text']}"
                    ai_out["approval_status"] = approval_detail

        if proceed_with_cloud:
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
                error_str = str(e)
                is_timeout = "timeout" in error_str.lower() or "timed out" in error_str.lower()
                print(f"[Cloud] Failed to reach cloud provider: {e}. Falling back to local suggestion.")

                # Provide explicit user feedback before fallback
                timeout_feedback = {
                    "kenyan_babe": (
                        "Cloud iko slow kidogo... wacha nicheki locally."
                        if is_timeout else
                        "Cloud haiku-respond... wacha nitumie local model."
                    ),
                    "sage": (
                        "Taking longer than usual from cloud... checking locally, babes."
                        if is_timeout else
                        "Cloud isn't responding... let me handle this locally."
                    ),
                    "martin": (
                        "Cloud call timed out. Routing locally."
                        if is_timeout else
                        "Cloud unavailable. Falling back to local."
                    ),
                }
                fallback_notice = timeout_feedback.get(
                    current_personality,
                    "Taking longer than usual, checking locally..."
                    if is_timeout else "Cloud unavailable, checking locally..."
                )

                if on_token:
                    try:
                        await on_token(fallback_notice + " ")
                    except Exception:
                        pass

                # If cloud-only mode is enabled but cloud failed, gracefully fall back
                # to local reasoning instead of repeating API-key errors to the user.
                local_fallback_done = False
                if handoff_reason == "forced_cloud_mode":
                    try:
                        print("[Cloud] Forced cloud mode failed; retrying this turn with local reasoning.")
                        local_meta = {"reason": event_type, "cloud_fallback": True}
                        ai_out = await advise(context, local_meta, conversation=conversation, on_token=on_token)
                        if ai_out and ai_out.get("type") and ai_out.get("type") != "handoff":
                            if ai_out.get("text"):
                                ai_out["text"] = f"{fallback_notice}\n\n{ai_out['text']}"
                            ai_out["cloud_fallback"] = True
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
    if not skip_router:
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

    # Clear any pending TTS only when voice output is enabled.
    if VOICE_OUTPUT_ENABLED:
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
    tts_streamer = TTSStreamer(client) if (STREAM_TTS and VOICE_OUTPUT_ENABLED) else None
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
        if tts_streamer is not None and VOICE_OUTPUT_ENABLED:
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

    response_text = _extract_human_text(result.get("text", ""))
    result["text"] = response_text

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
            "source": "handle_voice_transcript",  # Debug: track publish source
            "no_tts": not VOICE_OUTPUT_ENABLED,
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

        # Text intent routing: classify the incoming chat message and dispatch
        # architect/agent intents before falling back to the brain advisor.
        conversation_context = conversation.get_intent_context()
        forced_intent_type, forced_query = parse_text_intent_command(user_text)
        if not forced_intent_type and looks_like_architect_text_request(user_text):
            forced_intent_type = "architect_task"
            forced_query = user_text
        intent: Optional[Intent] = None

        try:
            if forced_intent_type:
                hinted = classify_intent(
                    forced_query or user_text,
                    conversation_context=conversation_context
                )
                intent = Intent(
                    type=forced_intent_type,
                    project=hinted.project,
                    query=(forced_query or hinted.query or user_text).strip(),
                    original=user_text,
                    confidence=1.0,
                    method="text_command",
                    signals={**hinted.signals, "forced_text_command": True},
                )
            else:
                intent = classify_intent(user_text, conversation_context=conversation_context)
        except Exception as e:
            print(f"[Chat] Intent classification failed: {e}")
            intent = Intent(
                type="brain_query",
                project=None,
                query=user_text,
                original=user_text,
                confidence=0.0,
                method="fallback",
                signals={"intent_error": str(e)},
            )

        conversation.update_mode(user_text, intent.type)
        conversation.add_user_message(
            user_text,
            {
                "source": "chat_api",
                "request_id": request_id,
                "intent": intent.type,
                "intent_method": intent.method,
                "intent_confidence": intent.confidence,
            },
        )

        print(
            f"[Chat] Intent: type={intent.type}, project={intent.project}, "
            f"method={intent.method}, confidence={intent.confidence:.2f}"
        )

        context = {
            "trigger": {"type": "chat_request", "text": intent.query or user_text},
            "local_hour": datetime.now().hour,
            "day_of_week": datetime.now().weekday(),
            "state": sage.get_snapshot(),
            "conversation": conversation.get_context_summary(),
            "personality": current_personality,
        }

        if payload.get("system_prompt"):
            context["chat_system_prompt"] = payload.get("system_prompt")

        async def _publish_chat_delta(token: str):
            if not token:
                return
            client.publish(
                response_topic,
                json.dumps(
                    {
                        "request_id": request_id,
                        "conversation_id": conversation_id,
                        "success": True,
                        "type": "delta",
                        "delta": token,
                        "ts": int(time.time() * 1000),
                    }
                ),
            )

        stream = bool(payload.get("stream", False))
        ai_out: Dict = {}
        response_text = ""

        project_git_result = handle_project_git_text(
            user_text=user_text,
            conversation_id=conversation_id,
            request_id=request_id,
        )
        if project_git_result.get("handled"):
            response_text = _extract_human_text(
                str(project_git_result.get("response_text") or "")
            )
            ai_out = {
                "type": "error" if project_git_result.get("error") else "suggestion",
                "intent": "project_git",
                "model": "project_git",
                "action": project_git_result.get("action"),
            }
        else:
            google_tool_result = handle_google_workspace_text(
                user_text=user_text,
                api_base_url=ARCHITECT_API_URL,
                conversation_id=conversation_id,
                request_id=request_id,
            )
            if google_tool_result.get("handled"):
                response_text = _extract_human_text(
                    str(google_tool_result.get("response_text") or "")
                )
                ai_out = {
                    "type": "error" if google_tool_result.get("error") else "suggestion",
                    "intent": "google_workspace",
                    "model": google_tool_result.get("model", "google_workspace"),
                    "action": google_tool_result.get("action"),
                    "latency_ms": google_tool_result.get("latency_ms"),
                }
            elif intent.type == "architect_task":
                if not architect_bridge:
                    ai_out = {"type": "error", "intent": "architect_task", "model": "architect_bridge"}
                    response_text = "Architect service is not available."
                else:
                    cli_override = _resolve_cli_override(intent.type, intent.query or user_text)
                    lowered_original = user_text.lower()
                    lowered_query = (intent.query or "").lower()
                    build_prefix = lowered_original.startswith("/architect-build")
                    explicit_execute = build_prefix
                    explicit_execute = explicit_execute or any(
                        marker in lowered_query
                        for marker in (
                            "build now",
                            "run build",
                            "apply changes",
                            "execute changes",
                            "implement now",
                            "make the changes",
                            "ship it",
                        )
                    )
                    if lowered_query.startswith(("build ", "execute ", "apply ")):
                        explicit_execute = True

                    apply_to_repo = lowered_original.startswith("/architect-build")
                    apply_to_repo = apply_to_repo or any(
                        marker in lowered_query
                        for marker in (
                            "apply to repo",
                            "write to repo",
                            "real file edits",
                            "edit real files",
                        )
                    )

                    if build_prefix and not (intent.query or "").strip():
                        ai_out = {
                            "type": "error",
                            "intent": "architect_task",
                            "status": "INVALID_REQUEST",
                            "model": "architect_bridge",
                            "artifacts": [],
                        }
                        response_text = (
                            "Missing build task. Use '/architect-build <what to change>'. "
                            "Example: /architect-build update apps/sage-mobile/README.md with a short note."
                        )
                        conversation.add_assistant_message(
                            response_text,
                            {
                                "source": "chat_api",
                                "request_id": request_id,
                                "type": ai_out.get("type"),
                                "model": ai_out.get("model"),
                                "intent": intent.type,
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
                                    "type": ai_out.get("type", "error"),
                                    "intent": intent.type,
                                    "done": True,
                                    "model": ai_out.get("model", "brain_runtime"),
                                    "personality": current_personality,
                                    "ts": int(time.time() * 1000),
                                }
                            ),
                        )
                        return

                    # Text chat defaults to plan mode. "/architect-build" always executes
                    # plan+build even when wording would otherwise classify as plan.
                    if build_prefix:
                        task_type = "code"
                    elif explicit_execute:
                        task_type = get_task_type_from_intent(intent)
                    else:
                        task_type = "plan"
                    result = await architect_bridge.dispatch(
                        project_id=intent.project,
                        query=intent.query,
                        task_type=task_type,
                        routing_hint=None,
                        llm_override=cli_override,
                    )
                    result = result if isinstance(result, dict) else {}
                    status = str(result.get("status", "UNKNOWN")).upper()
                    summary = str(result.get("summary", "") or "").strip()
                    artifacts = result.get("artifacts", []) or []

                    if status == "SUCCESS":
                        if summary:
                            response_text = summary
                        elif artifacts:
                            artifact_preview = ", ".join(str(path) for path in artifacts[:3])
                            response_text = f"Architect task completed. Artifacts: {artifact_preview}"
                        else:
                            response_text = "Architect task completed."

                        if explicit_execute and apply_to_repo:
                            apply_result = _apply_architect_artifacts_to_repo(
                                architect_bridge=architect_bridge,
                                project_hint=intent.project,
                                artifacts=artifacts,
                            )
                            copied = apply_result.get("copied_count", 0)
                            skipped = apply_result.get("skipped_count", 0)
                            if copied > 0:
                                preview = ", ".join(apply_result.get("copied", [])[:3])
                                response_text = (
                                    f"{response_text}\n\n"
                                    f"Applied {copied} file(s) to repo ({preview})."
                                    + (f" Skipped {skipped}." if skipped else "")
                                )
                            else:
                                response_text = (
                                    f"{response_text}\n\n"
                                    "Build ran, but no files were applied to repo. "
                                    "Check manifest paths/artifacts."
                                )
                        if task_type == "plan":
                            response_text = (
                                f"{response_text}\n\n"
                                "Say '/architect-build ...' (or include 'build now') when you want me to execute changes."
                            )
                        ai_out = {
                            "type": "acknowledged",
                            "intent": "architect_task",
                            "status": status,
                            "model": "architect_bridge",
                            "artifacts": artifacts,
                        }
                    else:
                        response_text = summary or "Architect task failed."
                        if explicit_execute and apply_to_repo and artifacts:
                            apply_result = _apply_architect_artifacts_to_repo(
                                architect_bridge=architect_bridge,
                                project_hint=intent.project,
                                artifacts=artifacts,
                            )
                            copied = apply_result.get("copied_count", 0)
                            skipped = apply_result.get("skipped_count", 0)
                            response_text = (
                                f"{response_text}\n\n"
                                f"Warning: build reported failure, but applied {copied} file(s) to repo"
                                + (f" and skipped {skipped}." if skipped else ".")
                            )
                        ai_out = {
                            "type": "error",
                            "intent": "architect_task",
                            "status": status,
                            "model": "architect_bridge",
                            "artifacts": artifacts,
                        }
            elif intent.type == "agent_task":
                if not agent_bridge:
                    ai_out = {"type": "error", "intent": "agent_task", "model": "agent_bridge"}
                    response_text = "Agent system is not available."
                else:
                    result = await agent_bridge.dispatch(intent.query)
                    result = result if isinstance(result, dict) else {}
                    ai_out = {**result, "intent": "agent_task", "model": "agent_bridge"}
                    response_text = _extract_human_text(result.get("text", "") or "")
            else:
                if intent.type == "smalltalk":
                    reason = "smalltalk"
                elif intent.type == "home_control":
                    reason = "home_control"
                else:
                    reason = str(payload.get("reason", "chat_request"))

                chat_meta = {
                    "reason": reason,
                    "minimal_prompt": bool(payload.get("minimal_prompt", CHAT_MINIMAL_PROMPT_DEFAULT)),
                    "allow_plain_text": bool(payload.get("allow_plain_text", True)),
                    "intent_type": intent.type,
                }
                if intent.type == "home_control":
                    smartthings_result = await handle_home_control_request(intent.query or user_text)
                    if smartthings_result.get("handled"):
                        ai_out = {
                            "type": "suggestion",
                            "intent": intent.type,
                            "model": "smartthings",
                        }
                        response_text = smartthings_result.get("text", "Done.")
                        chat_meta = None

                cli_override = _resolve_cli_override(intent.type, intent.query or user_text)
                use_cli = bool(
                    cli_override
                    and (
                        intent.type in {"agent_task", "architect_task"}
                        or _looks_like_research_text(intent.query or user_text)
                    )
                )

                if chat_meta is None:
                    pass
                elif use_cli:
                    prompt_messages = []
                    system_prompt = context.get("chat_system_prompt")
                    if isinstance(system_prompt, str) and system_prompt.strip():
                        prompt_messages.append({"role": "system", "content": system_prompt.strip()})
                    prompt_messages.append({"role": "user", "content": intent.query or user_text})
                    cli_text = await _chat_with_external_cli(
                        prompt_messages,
                        provider=cli_override["provider"],
                        model=cli_override.get("model"),
                    )
                    response_text = _extract_human_text(cli_text)
                    ai_out = {
                        "type": "suggestion",
                        "intent": intent.type,
                        "model": f"{cli_override['provider']}:{cli_override.get('model')}",
                    }
                else:
                    ai_out = await advise(
                        context,
                        chat_meta,
                        conversation=conversation,
                        on_token=_publish_chat_delta if stream else None,
                        stream=stream,
                    )
                    response_text = _extract_human_text(ai_out.get("text", "") or "")

        if not response_text:
            response_text = "I heard you, but I could not generate a response."

        conversation.add_assistant_message(
            response_text,
            {
                "source": "chat_api",
                "request_id": request_id,
                "type": ai_out.get("type"),
                "model": ai_out.get("model"),
                "intent": intent.type,
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
                    "intent": intent.type,
                    "done": True,
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
    global current_personality, current_raw_mode, VOICE_INPUT_ENABLED, VOICE_OUTPUT_ENABLED
    try:
        topic = msg.topic
        payload_str = msg.payload.decode()
        
        # Brain Config Handler
        if topic == BRAIN_CONFIG_TOPIC:
            try:
                config = json.loads(payload_str)
                new_personality = config.get("personality")
                if "raw_mode" in config:
                    try:
                        from ai.advisor import set_raw_mode
                        enabled = bool(config.get("raw_mode"))
                        set_raw_mode(enabled)
                        current_raw_mode = enabled
                        print(f"[Brain] Raw mode set to: {enabled}")
                    except Exception as e:
                        print(f"[Brain] Could not set raw mode: {e}")
                if "voice_input_enabled" in config:
                    VOICE_INPUT_ENABLED = bool(config.get("voice_input_enabled"))
                    print(f"[Brain] Voice input enabled: {VOICE_INPUT_ENABLED}")
                if "voice_output_enabled" in config:
                    VOICE_OUTPUT_ENABLED = bool(config.get("voice_output_enabled"))
                    print(f"[Brain] Voice output enabled: {VOICE_OUTPUT_ENABLED}")

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
                            BRAIN_CONFIG_TOPIC,
                            json.dumps({
                                "personality": current_personality,
                                "raw_mode": current_raw_mode,
                                "voice_input_enabled": VOICE_INPUT_ENABLED,
                                "voice_output_enabled": VOICE_OUTPUT_ENABLED,
                                "source": "brain"
                            })
                        )
                _publish_brain_status(client, status="ready")
            except Exception as e:
                print(f"[Brain] Config update failed: {e}")
            return
        
        # Brain Command Handler (clear conversation, clear memory, etc.)
        if topic == BRAIN_COMMAND_TOPIC:
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
                elif command == "kill_switch":
                    VOICE_INPUT_ENABLED = False
                    VOICE_OUTPUT_ENABLED = False
                    print("[Brain] Kill switch enabled: voice input/output disabled")
                elif command == "resume_voice":
                    VOICE_INPUT_ENABLED = True
                    VOICE_OUTPUT_ENABLED = True
                    print("[Brain] Voice input/output resumed")
                _publish_brain_status(client, status="ready", last_command=command)
                        
            except Exception as e:
                print(f"[Brain] Command failed: {e}")
            return

        # Voice transcript handler
        if topic == "sage/voice/transcript":
            if not VOICE_INPUT_ENABLED:
                print("[Voice] Input disabled; ignoring transcript")
                return
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

        # Vision summaries + metrics are context inputs for routing/memory.
        if topic.startswith("sage/vision/") and topic.endswith("/vlm"):
            try:
                data = json.loads(payload_str) if payload_str else {}
            except Exception:
                data = {}
            location = topic.split("/")[2] if len(topic.split("/")) > 2 else "unknown"
            event = {
                "type": "vision_vlm",
                "room": location,
                "source": "vision",
                "activity": data.get("activity"),
                "mood": data.get("mood"),
                "text": data.get("description", ""),
                "latency_ms": data.get("latency_ms"),
                "queue_wait_ms": data.get("queue_wait_ms"),
                "provider": data.get("provider"),
                "model": data.get("model"),
                "ts": int(time.time() * 1000),
            }
            buffer.push(event)
            print(
                f"[Vision] {location}: {str(event.get('activity') or 'unknown')} / "
                f"{str(event.get('mood') or 'unknown')} ({event.get('provider')})"
            )
            return

        if topic.startswith("sage/vision/") and topic.endswith("/metrics"):
            try:
                data = json.loads(payload_str) if payload_str else {}
                provider = data.get("provider", "unknown")
                total_ms = data.get("total_ms")
                queue_ms = data.get("queue_wait_ms")
                print(f"[VisionMetrics] provider={provider} queue={queue_ms} total={total_ms}")
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
    client.on_connect = _on_mqtt_connect
    client.on_disconnect = _on_mqtt_disconnect
    client.on_message = on_message

    try:
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        _publish_brain_status(client, status="starting")

        # Subscribe immediately on first boot; _on_mqtt_connect re-subscribes after reconnects.
        _subscribe_all_topics(client)
        client.loop_start()

        # Preload memory system to avoid first-message latency.
        # Keep startup resilient when memory dependencies are intentionally absent.
        if MEMORY_PRELOAD_ENABLED:
            print("[Brain] Preloading memory system...")
            preload_start = time.time()
            try:
                from brain.memory.sage_memory import get_memory
                _ = get_memory()  # Initialize singleton
                preload_time = int((time.time() - preload_start) * 1000)
                print(f"[Brain] ✓ Memory preloaded in {preload_time}ms")
            except ImportError as e:
                print(f"[Brain] Memory preload unavailable ({e}); continuing without long-term memory")
            except Exception as e:
                print(f"[Brain] Memory preload failed ({e}); continuing")
        else:
            print("[Brain] Memory preload disabled via SAGE_MEMORY_PRELOAD=false")

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
        _publish_brain_status(client, status="ready")
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
