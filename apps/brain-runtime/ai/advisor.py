import os
import json
import re
import time
from typing import Callable, Awaitable, Optional, List, Dict
from .model_policy import choose_model
from .local_llm_client import (
    local_chat,
    local_chat_stream,
    get_local_llm_backend,
    get_local_llm_base_url,
)
from .personalities import (
    build_core_identity_prompt,
    build_mode_prompt,
    build_tone_hint,
    classify_tone,
    select_mode,
    RESPONSE_SCHEMA,
)
from .context_builder import build_full_context, build_minimal_context
from .conversation import get_conversation, ConversationHistory
from .personality_engine import get_personality_engine, PersonalityEngine

LOCAL_LLM_BACKEND = get_local_llm_backend()

DEFAULT_PERSONALITY = os.getenv("DEFAULT_PERSONALITY", "kenyan_babe")

# Fast mode: Skip heavy context for voice queries (disabled by default)
FAST_MODE = os.getenv("SAGE_FAST_MODE", "false").lower() == "true"

# Bare mode: Minimize system prompting for raw LLM behavior
BARE_MODE = os.getenv("SAGE_BARE_MODE", "false").lower() == "true"
# Raw mode: No system prompts; use plain chat history
RAW_MODE = os.getenv("SAGE_RAW_MODE", "false").lower() == "true"


def set_raw_mode(enabled: bool) -> None:
    global RAW_MODE
    RAW_MODE = bool(enabled)
    print(f"[RAW MODE] Raw mode {'ENABLED' if RAW_MODE else 'DISABLED'}")

# Self-awareness mode: Enable rich internal context
SELF_AWARE_MODE = os.getenv("SAGE_SELF_AWARE", "true").lower() == "true"


def build_system_prompt_with_awareness(
    context: Dict,
    personality: str = DEFAULT_PERSONALITY,
    conversation: ConversationHistory = None
) -> str:
    """
    Legacy prompt builder (kept for compatibility).
    """
    personality_core = build_core_identity_prompt(personality)
    summary_packet = context.get("summary", {})
    action_memory = context.get("state", {}).get("action_memory", [])

    # Extract user text early for memory recall
    trigger = context.get("trigger") or {}
    trigger_type = trigger.get("type", "periodic_check")
    user_text = trigger.get("text", "")

    if summary_packet:
        self_awareness = build_full_context(
            summary_packet=summary_packet,
            action_memory=action_memory,
            conversation=conversation,
            user_message=user_text  # Pass user message for memory recall
        )
    else:
        self_awareness = _build_fallback_awareness(context)

    return f"""
{personality_core}

=== WHAT I CURRENTLY KNOW ===
{self_awareness}
=== MY TASK ===
You are Sage, the home companion AI. You have genuine awareness of the situation above.
Reference your observations naturally. Don't just dump data - speak from your understanding.

Current trigger: {trigger_type}
{f'User said: "{user_text}"' if user_text else ''}
""".strip()


def _build_fallback_awareness(context: Dict) -> str:
    """Build minimal awareness when summary_packet isn't available."""
    parts = []
    
    local_hour = context.get("local_hour", 12)
    parts.append(f"Time: around {local_hour}:00")
    
    state = context.get("state", {})
    rooms = state.get("rooms", {})
    active_rooms = [name for name, r in rooms.items() if r.get("occupied")]
    if active_rooms:
        parts.append(f"Location: {', '.join(active_rooms)}")
    else:
        parts.append("Location: No one detected")
        
    mode = state.get("mode", "UNKNOWN")
    parts.append(f"Home state: {mode}")
    
    return "\n".join(parts)

def _needs_conversation_context(user_text: str) -> bool:
    if not user_text:
        return False
    lowered = user_text.lower()
    # Short replies and reference-heavy phrases usually need prior context
    if len(lowered.split()) <= 6:
        return True
    reference_terms = [
        "that", "this", "it", "those", "these", "the one", "same",
        "again", "as above", "as we said", "you said", "we said",
        "hiyo", "ile", "story", "iyo"
    ]
    return any(term in lowered for term in reference_terms)

def _is_practical_request(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    keywords = [
        "how", "how do", "how to", "steps", "explain",
        "aje", "fanywa", "fanya", "onyesha", "how it's done",
        "exercise", "exercises", "kettlebell", "kb", "workout"
    ]
    return any(k in lowered for k in keywords)

def _is_identity_request(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()

    # User asking about themselves ("who am I"), not Sage's identity.
    self_identity_patterns = [
        "who am i",
        "mimi ni nani",
        "do you know who i am",
        "unajua mimi ni nani",
    ]
    if any(p in lowered for p in self_identity_patterns):
        return False

    direct_identity_patterns = [
        "who are you",
        "what are you",
        "what's your name",
        "what is your name",
        "your name",
        "wewe ni nani",
        "ni wewe nani",
        "jina lako",
    ]
    if any(p in lowered for p in direct_identity_patterns):
        return True

    # Keep personality trigger scoped to assistant-directed phrasing.
    if "personality" in lowered and any(p in lowered for p in ["your", "you", "wewe"]):
        return True

    return False

def _is_grief_disclosure(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    keywords = [
        "died", "death", "passed", "passed away", "suicide", "grief", "lost my",
        "lost his", "lost her", "funeral", "burial", "cancer", "diagnosed",
        "miss my", "miss him", "miss her", "missing my", "sijaheal", "haven't healed",
    ]
    return any(k in lowered for k in keywords)


def _is_brief_followup_message(text: str) -> bool:
    """
    Detect short, non-question follow-up replies like:
    - "chicken salad"
    - "niko fiti"
    - "just chilling"
    """
    if not text:
        return False

    stripped = text.strip()
    if not stripped:
        return False
    if "?" in stripped:
        return False

    words = re.findall(r"[A-Za-z0-9']+", stripped.lower())
    if not words:
        return False

    return len(words) <= 7


def _sanitize_suggestion_text(text: str) -> str:
    """Normalize model text before publishing to voice/UI."""
    if not isinstance(text, str):
        return ""

    cleaned = text.strip()
    if len(cleaned) >= 2 and cleaned[0] in {'"', "'"} and cleaned[-1] == cleaned[0]:
        inner = cleaned[1:-1].strip()
        if inner:
            cleaned = inner

    # Preserve paragraph breaks but normalize noisy spaces.
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()

def build_system_prompt(context, personality=DEFAULT_PERSONALITY):
    rooms = context.get("state", {}).get("rooms", {})
    room_list = ", ".join(rooms.keys()) if rooms else "none"
    trigger = context.get("trigger") or {}
    trigger_type = trigger.get("type", "periodic_check")
    trigger_room = trigger.get("room", "unknown")
    local_hour = context.get("local_hour", 12)
    
    personality_core = build_core_identity_prompt(personality)
    
    return f"""
{personality_core}

CORE TASK:
You are currently acting as the Home Buddy AI. 
Your primary job is to monitor home state and provide suggestions/actions.

Current trigger: {trigger_type} in {trigger_room}.
Known rooms: {room_list}.
Local time: {local_hour}:00.

Allowed schemas:
1) {{"type":"none", "report":object}}
2) {{"type":"suggestion", "text":string, "confidence":number, "report":object}}
3) {{"type":"action_plan", "actions":[{{"action":"notify"|"set_timer","channel":string,"text":string,"duration_minutes":number}}], "safety":{{"requires_confirmation":boolean}}, "report":object}}
4) {{"type":"handoff", "reason":string, "report":object}}

Rules:
- REPORT: Every response MUST include a "report" object. This is your "Situational Report".
- REPORT STRUCTURE:
  {{
    "location": string,
    "presence": "single_person"|"multiple_people"|"none",
    "activity_level": "low"|"medium"|"high",
    "posture_signals": string[],
    "audio_signals": string[],
    "environmental_signals": {{ "lights": string, "temperature": string, "device_usage": string }},
    "mood_inference": string,
    "intensity": number (1-10),
    "recent_patterns": string[],
    "pending_nudges": string[]
  }}
- Match the vibe of the sensor data. If no motion for 30m at 2am, activity_level is "low", posture might be "slouched".
- HANDOFF: Use this if the situation is emotionally complex or requires a long conversation.
- EXPLICIT HANDOFF: If user says "ask Grok", "ask cloud", or "switch to cloud", YOU MUST RETURN "handoff" type.
- TIMER: If user asks for more time/break, use "set_timer".
- EXPIRED: If trigger is "timer_expired", check if the user is still active and be firm but loving.
""".strip()

def _build_minimal_context_legacy(context: dict) -> dict:
    """
    Build a minimal context for fast voice queries (legacy mode).
    Reduces token count significantly for faster inference.
    """
    trigger = context.get("trigger", {})
    state = context.get("state", {})
    
    return {
        "now": context.get("now"),
        "local_hour": context.get("local_hour"),
        "trigger": {
            "type": trigger.get("type"),
            "text": trigger.get("text", "")[:200],  # Truncate long text
        },
        "rooms_active": list(state.get("rooms", {}).keys())[:5],  # Max 5 rooms
    }


def build_prompt_messages(
    context: Dict,
    meta: Dict,
    conversation: ConversationHistory
) -> Dict:
    """
    Build prompt messages with core prompt caching and mode routing.
    """
    minimal_prompt = bool(meta.get("minimal_prompt") or context.get("minimal_prompt"))
    force_plain_text = bool(meta.get("allow_plain_text"))
    active_personality = context.get("personality", DEFAULT_PERSONALITY)
    reason = meta.get("reason", "")
    mode_override = meta.get("mode") or context.get("mode")
    mode = mode_override or select_mode(reason, context)

    prompt_variant = (meta.get("core_prompt") or context.get("core_prompt") or "").lower()
    if not prompt_variant:
        prompt_variant = "full" if mode in ("supportive", "reflective") else "light"
    # Will be updated after we determine skip_json
    allow_plain_text = force_plain_text or minimal_prompt or mode in ("supportive", "reflective")
    trigger = context.get("trigger", {}) if context else {}
    user_text = trigger.get("text", "")
    tone = classify_tone(user_text)
    tone_hint = build_tone_hint(user_text)

    force_refresh = bool(meta.get("force_persona_refresh") or context.get("force_persona_refresh"))
    include_core = force_refresh or conversation.force_core_refresh or not conversation.core_prompt_sent
    core_prompt = build_core_identity_prompt(
        personality=active_personality,
        include_examples=True,
        prompt_variant=prompt_variant,
        minimal=minimal_prompt
    )

    # Skip JSON schema for emotional/conversational contexts - let the model talk naturally
    is_emotional = tone in ("tender", "frustrated") or _is_grief_disclosure(user_text)
    is_conversational = reason in ("smalltalk", "user_intent") and mode == "supportive"
    is_chat_request = trigger.get("type") == "chat_request" or reason == "chat_request"
    skip_json = force_plain_text or is_emotional or is_conversational or is_chat_request

    if skip_json:
        print(
            f"[Prompt] Skipping JSON schema - force_plain_text={force_plain_text}, "
            f"chat_request={is_chat_request}, emotional={is_emotional}, "
            f"conversational={is_conversational}, tone={tone}"
        )
        allow_plain_text = True

    mode_prompt = "" if minimal_prompt else f"{build_mode_prompt(mode, skip_json_schema=skip_json)}\n\n{tone_hint}"

    system_messages = []
    if RAW_MODE:
        return {
            "mode": "raw",
            "tone": "neutral",
            "core_variant": "none",
            "minimal_prompt": True,
            "allow_plain_text": True,
            "include_core": False,
            "core_words": 0,
            "mode_words": 0,
            "system_words": 0,
            "system_messages": [],
        }
    if BARE_MODE:
        return {
            "mode": "bare",
            "tone": "neutral",
            "core_variant": "none",
            "minimal_prompt": True,
            "allow_plain_text": False,
            "include_core": False,
            "core_words": 0,
            "mode_words": len(RESPONSE_SCHEMA.split()),
            "system_words": len(RESPONSE_SCHEMA.split()),
            "system_messages": [{"role": "system", "content": RESPONSE_SCHEMA}],
        }
    if include_core:
        system_messages.append({"role": "system", "content": core_prompt})
        conversation.mark_core_prompt_sent()
        conversation.force_core_refresh = False

    if mode_prompt:
        system_messages.append({"role": "system", "content": mode_prompt})

    if _is_practical_request(user_text):
        system_messages.append({
            "role": "system",
            "content": (
                "This is a practical request. Answer directly with clear steps or instructions first, "
                "then add personality. Do not deflect or ask unnecessary questions."
            )
        })

    if _is_identity_request(user_text):
        system_messages.append({
            "role": "system",
            "content": (
                "The user is asking about your name/personality. Answer clearly with your persona name "
                "and a short, direct description. Your name is Sage. Never invent another name. Do not evade."
            )
        })

    if _is_grief_disclosure(user_text):
        system_messages.append({
            "role": "system",
            "content": "He's sharing something painful. Be with him. Ask about what he's shared, let him lead."
        })

    if is_conversational:
        system_messages.append({
            "role": "system",
            "content": (
                "Natural conversation rule: do not force a follow-up question on every turn. "
                "Questions are optional and only when they move the conversation forward."
            ),
        })

    if _is_brief_followup_message(user_text):
        system_messages.append({
            "role": "system",
            "content": (
                "User gave a short follow-up. Do not echo/paraphrase their words with lines like "
                "\"it sounds like...\". Reply naturally in 1-2 concise sentences. "
                "If useful, offer one concrete tip or next step."
            ),
        })

    core_words = len(core_prompt.split())
    mode_words = len(mode_prompt.split())
    system_words = mode_words + (core_words if include_core else 0)

    return {
        "mode": mode,
        "tone": tone,
        "core_variant": prompt_variant,
        "minimal_prompt": minimal_prompt,
        "allow_plain_text": allow_plain_text,
        "skip_json_schema": skip_json,
        "include_core": include_core,
        "core_words": core_words,
        "mode_words": mode_words,
        "system_words": system_words,
        "system_messages": system_messages,
    }


async def advise(
    context,
    meta=None,
    on_token: Optional[Callable[[str], Awaitable[None]]] = None,
    stream: bool = False,
    conversation: ConversationHistory = None
):
    """
    Get AI advice for the given context.

    Args:
        context: Full context dict
        meta: Metadata (reason, etc.)
        on_token: Optional callback for streaming tokens (for TTS pipelining)
        stream: Whether to use streaming mode
        conversation: Optional conversation history for context continuity

    Returns:
        Parsed AI response dict
    """
    if meta is None: meta = {}

    # Get conversation history if not provided
    if conversation is None:
        conversation = get_conversation()

    if RAW_MODE:
        print(f"[RAW MODE] advise() called - conversation has {len(conversation.messages) if conversation else 0} messages")

    # Phase 2: Process through PersonalityEngine (skip in raw mode)
    personality_state = None
    trigger = context.get("trigger", {}) if context else {}
    user_text = trigger.get("text", "")
    if not RAW_MODE:
        personality_engine = get_personality_engine()
        if user_text:
            personality_state = personality_engine.process_user_message(user_text)
            print(f"[Personality] emotion={personality_state['emotion']}, "
                  f"cultural={personality_state['cultural_mode']}, "
                  f"depth={personality_state['conversation_depth']}")

            # Phase 3+: Real-time identity extraction
            try:
                from brain.memory.distiller import process_message_for_identity
                identity_count = process_message_for_identity(user_text)
                if identity_count > 0:
                    print(f"[Identity] Extracted {identity_count} identity fact(s) from message")
            except Exception as e:
                print(f"[Identity] Error in extraction: {e}")

    policy = choose_model(meta, context)
    model = policy["model"]
    model_tier = policy.get("tier", "mid")
    options = policy["options"]

    # Choose prompt style based on self-aware mode
    reason = meta.get("reason", "")
    force_minimal = bool(meta.get("minimal_prompt"))
    use_minimal = force_minimal or (FAST_MODE and reason in ("user_intent", "smalltalk", "chat_request"))
    if use_minimal and conversation and not conversation.is_empty():
        trigger = context.get("trigger", {}) if context else {}
        user_text = trigger.get("text", "")
        if _needs_conversation_context(user_text):
            use_minimal = False

    t_ctx = time.time()

    # Detect if this is a simple query that doesn't need memory
    trigger = context.get("trigger", {}) if context else {}
    user_text_for_check = (trigger.get("text") or "").lower()
    reason = meta.get("reason", "")
    
    # Factual queries - use fast model, skip memory
    factual_patterns = [
        "what is", "what's", "who is", "who's", "when is", "when's",
        "where is", "where's", "how many", "how much", "define",
        "capital of", "population of", "weather", "time in",
        "convert", "calculate", "translate"
    ]
    is_factual_query = any(p in user_text_for_check for p in factual_patterns)
    
    # Smalltalk/greetings - skip memory for speed
    smalltalk_patterns = [
        "hey", "hi ", "hello", "what's up", "how's it going", "how are you",
        "good morning", "good night", "sup", "yo ", "wassup"
    ]
    is_smalltalk_query = reason == "smalltalk" or any(p in user_text_for_check for p in smalltalk_patterns)
    
    # Skip memory for both factual and smalltalk
    skip_memory = is_factual_query or is_smalltalk_query
    
    # Skip memory for simple queries - huge latency savings on cold start
    identity_prompt = ""
    if not skip_memory and not RAW_MODE:
        try:
            from brain.memory.recall import get_recall_engine
            recall = get_recall_engine()
            identity_prompt = recall.get_identity_prompt()
            if identity_prompt:
                print(f"[Context] Identity loaded: {identity_prompt[:50]}...")
        except Exception as e:
            print(f"[Context] Identity load failed: {e}")
    elif skip_memory:
        skip_reason = "factual" if is_factual_query else "smalltalk"
        print(f"[Context] Skipping memory for {skip_reason} query (latency optimization)")

    if RAW_MODE:
        ctx_to_send = {}
    elif SELF_AWARE_MODE and not use_minimal:
        summary_packet = context.get("summary", {})
        action_memory = context.get("state", {}).get("action_memory", [])
        if summary_packet:
            self_awareness = build_full_context(
                summary_packet=summary_packet,
                action_memory=action_memory,
                conversation=conversation,
                user_message=user_text  # Pass user message for memory recall
            )
        else:
            self_awareness = _build_fallback_awareness(context)
        ctx_to_send = {
            "trigger": context.get("trigger", {}),
            "self_awareness": self_awareness,
            "conversation": conversation.get_context_summary(),
        }
        # Add identity if not already in self_awareness
        if identity_prompt and "Who I'm talking to" not in self_awareness:
            ctx_to_send["user_identity"] = identity_prompt
    else:
        ctx_to_send = _build_minimal_context_legacy(context) if use_minimal else context
        # Always include identity in minimal context
        if identity_prompt:
            ctx_to_send["user_identity"] = identity_prompt

    # Phase 2: Inject personality guidance into context
    if personality_state and not RAW_MODE:
        personality_injection = personality_engine.get_prompt_injection()
        if personality_injection:
            ctx_to_send["personality_guidance"] = personality_injection

    print(f"[Latency] context_build: {int((time.time() - t_ctx) * 1000)}ms")
    
    prompt_meta = build_prompt_messages(context, meta, conversation)
    system_messages = prompt_meta["system_messages"]
    print(
        f"[AI] Mode selected: {prompt_meta['mode']}, "
        f"tone={prompt_meta['tone']}, core_variant={prompt_meta['core_variant']}, "
        f"minimal_prompt={prompt_meta['minimal_prompt']}"
    )

    # Log context sizes for debugging
    system_tokens = prompt_meta["system_words"]
    context_tokens = len(json.dumps(ctx_to_send).split())
    total_input_tokens = system_tokens + context_tokens
    llm_base_url = get_local_llm_base_url(LOCAL_LLM_BACKEND, tier=model_tier)
    print(
        f"[AI] Calling local LLM backend={LOCAL_LLM_BACKEND} host={llm_base_url} "
        f"tier={model_tier} model={model}, reason={reason}, fast={use_minimal}, self_aware={SELF_AWARE_MODE}"
    )
    print(
        f"[AI] Input size: core={prompt_meta['core_words']}w, "
        f"mode={prompt_meta['mode_words']}w, system_sent={system_tokens}w, "
        f"context={context_tokens}w, total={total_input_tokens}w"
    )

    start_time = time.time()
    try:
        if RAW_MODE:
            raw_messages = conversation.get_messages() if conversation else []
            print(f"[RAW MODE] Conversation has {len(raw_messages)} messages")
            if raw_messages:
                for i, msg in enumerate(raw_messages):
                    preview = msg.get("content", "")[:50]
                    print(f"[RAW MODE]   [{i}] {msg.get('role')}: {preview}...")
            if not raw_messages:
                trigger = context.get("trigger", {}) if context else {}
                user_text = trigger.get("text", "")
                raw_messages = [{"role": "user", "content": user_text or ""}]
                print(f"[RAW MODE] Fallback: using trigger text: {user_text[:50]}...")

            # Build minimal context for raw mode (identity + basic state)
            raw_context_parts = []
            if identity_prompt:
                raw_context_parts.append(identity_prompt)

            # Add basic time/state context
            state = context.get("state", {}) if context else {}
            local_hour = context.get("local_hour") if context else None
            if local_hour is not None:
                time_of_day = "morning" if 5 <= local_hour < 12 else "afternoon" if 12 <= local_hour < 17 else "evening" if 17 <= local_hour < 21 else "night"
                raw_context_parts.append(f"It's currently {time_of_day}")

            # Add minimal system message if we have context
            messages = []
            if raw_context_parts:
                raw_system = "Context: " + ". ".join(raw_context_parts) + "."
                messages.append({"role": "system", "content": raw_system})
                print(f"[RAW MODE] Minimal context: {raw_system[:100]}...")

            messages.extend(raw_messages)
            format_json = False
        else:
            skip_json_schema = bool(prompt_meta.get("skip_json_schema", False))
            if skip_json_schema:
                # Conversational path: pass the latest user text directly to avoid
                # awkward "responding to raw JSON" behavior.
                compact_context = {}
                if isinstance(ctx_to_send, dict):
                    for key in ("self_awareness", "user_identity", "personality_guidance", "conversation"):
                        if key in ctx_to_send:
                            compact_context[key] = ctx_to_send[key]
                    trigger_obj = ctx_to_send.get("trigger", {})
                    if isinstance(trigger_obj, dict):
                        compact_context["trigger_meta"] = {
                            "type": trigger_obj.get("type"),
                            "room": trigger_obj.get("room"),
                        }

                latest_user_text = ""
                trigger_obj = ctx_to_send.get("trigger", {}) if isinstance(ctx_to_send, dict) else {}
                if isinstance(trigger_obj, dict):
                    latest_user_text = str(trigger_obj.get("text") or "")
                if not latest_user_text:
                    latest_user_text = str(user_text or "")

                messages = [*system_messages]
                if compact_context:
                    messages.append({
                        "role": "system",
                        "content": (
                            "Internal context JSON (for grounding, do not quote it verbatim to user): "
                            + json.dumps(compact_context)
                        ),
                    })
                messages.append({
                    "role": "user",
                    "content": latest_user_text or json.dumps(ctx_to_send),
                })
                format_json = False
            else:
                messages = [
                    *system_messages,
                    {"role": "user", "content": json.dumps(ctx_to_send)}
                ]
                format_json = True

        # Use streaming if callback provided OR stream flag is True
        if stream or on_token:
            response_text = await local_chat_stream(
                model=model,
                messages=messages,
                options=options,
                on_token=on_token,
                format_json=format_json,
                tier=model_tier,
            )
        else:
            response_text = await local_chat(
                model=model,
                messages=messages,
                format_json=format_json,
                options=options,
                tier=model_tier,
            )
        
        duration = int((time.time() - start_time) * 1000)
        print(f"[Latency] llm_call: {duration}ms")
        print(f"[AI] Local LLM response received in {duration}ms")
    except Exception as e:
        print(f"[AI] local_llm_chat failed: {str(e)}")
        return {"model": model, "type": "none", "error": str(e)}

    try:
        # Clean markdown code blocks if present
        cleaned = response_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]

        # Try to extract text even if JSON is broken
        parsed = None
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as je:
            # JSON was truncated or malformed - try recovery
            print(f"[AI] JSON parse failed, attempting recovery...")

            # Scenario 1: Text followed by incomplete/partial JSON fragment
            # Example: "Hello there {"type" or "Hello {"
            # Remove any trailing incomplete JSON fragments
            text_before_json = re.sub(r'\s*\{[^}]*$', '', cleaned).strip()
            if text_before_json and text_before_json != cleaned:
                text_before_json = _sanitize_suggestion_text(text_before_json)
                print(f"[AI] Removed trailing JSON fragment, extracted text: {text_before_json[:50]}...")
                return {
                    "model": model,
                    "type": "suggestion",
                    "text": text_before_json,
                    "confidence": 0.7,
                    "recovered": True
                }

            # Scenario 2: Complete JSON followed by duplicate text
            # Example: {"type":"suggestion", "text":"Hello"}\nHello
            # Find the FIRST complete JSON object
            json_block_match = re.search(r'^(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', cleaned, re.DOTALL)
            if json_block_match:
                json_str = json_block_match.group(1)
                try:
                    parsed = json.loads(json_str)
                    print(f"[AI] Recovered JSON from hybrid response")
                    # Extract ONLY the text field, ignore any duplicate text after JSON
                    if parsed.get("text"):
                        parsed["text"] = _sanitize_suggestion_text(parsed["text"])
                        return {"model": model, **parsed}
                except:
                    pass # Continue to next recovery attempt

            # Scenario 3: Text followed by complete JSON (Hybrid response)
            # Find the last JSON-like block (greedy match from last { to end)
            json_block_match = re.search(r'(\{[\s\S]*\})\s*$', cleaned)
            if json_block_match:
                json_str = json_block_match.group(1)
                pre_text = cleaned[:json_block_match.start()].strip()
                try:
                    parsed = json.loads(json_str)
                    print(f"[AI] Recovered hybrid response. Text len: {len(pre_text)}")

                    # If parsed has no text but we found pre-text, inject it
                    if not parsed.get("text") and pre_text:
                        parsed["text"] = pre_text
                        if parsed.get("type") == "none":
                            parsed["type"] = "suggestion"

                    if parsed.get("text"):
                        parsed["text"] = _sanitize_suggestion_text(parsed["text"])
                    return {"model": model, **parsed}
                except:
                    pass # Continue to regex fallback

            # Scenario 4: Try to find "text": "..." pattern inside JSON
            text_match = re.search(r'"text"\s*:\s*"([^"]*)', cleaned)
            if text_match:
                extracted_text = _sanitize_suggestion_text(text_match.group(1))
                print(f"[AI] Recovered text: {extracted_text[:50]}...")
                return {
                    "model": model,
                    "type": "suggestion",
                    "text": extracted_text,
                    "confidence": 0.7,
                    "recovered": True
                }
            if prompt_meta.get("allow_plain_text") and cleaned:
                cleaned = _sanitize_suggestion_text(cleaned)
                print(f"[AI] Plain text allowed; using raw response ({len(cleaned)} chars): {cleaned[:80]}...")
                return {
                    "model": model,
                    "type": "suggestion",
                    "text": cleaned,
                    "confidence": 0.7,
                    "recovered": True,
                    "plain_text": True
                }
            raise je
        
        if not parsed or not isinstance(parsed, dict) or "type" not in parsed:
            print("[AI] Invalid or empty response structure from Ollama")
            return {"model": model, "type": "none"}

        # Basic validation & normalization
        if parsed["type"] == "suggestion":
            if not isinstance(parsed.get("text"), str):
                return {"model": model, "type": "none"}

            # Clean the text field - remove any trailing JSON fragments
            text = parsed.get("text", "")
            # Remove trailing JSON-like patterns: {"type, {"report, etc.
            text = re.sub(r'\s*\{["\w]*$', '', text).strip()
            parsed["text"] = _sanitize_suggestion_text(text)

            conf = parsed.get("confidence", 0.7)
            parsed["confidence"] = max(0.0, min(1.0, float(conf)))

        if parsed["type"] == "action_plan":
            actions = parsed.get("actions", [])
            if not isinstance(actions, list): actions = []
            
            # Normalize action keys
            normalized_actions = []
            for a in actions:
                if not isinstance(a, dict): continue
                normalized_a = {
                    "action": a.get("action"),
                    "channel": a.get("channel", "console"),
                    "text": a.get("text", ""),
                    "duration_minutes": a.get("duration_minutes") or a.get("durationMinutes") or 10
                }
                normalized_actions.append(normalized_a)
            parsed["actions"] = normalized_actions

            # Normalize safety keys
            safety = parsed.get("safety", {})
            requires = safety.get("requires_confirmation") or safety.get("requiresConfirmation")
            
            # DEFAULT: requires_confirmation is False for direct user requests (user_intent)
            if requires is None:
                requires = False if meta.get("reason") == "user_intent" else True
            
            parsed["safety"] = {"requires_confirmation": bool(requires)}

        print(f"[AI] Parsed response type: {parsed['type']}")

        # Phase 2: Enrich response with personality markers if needed
        if personality_state and parsed.get("text") and not RAW_MODE:
            original_text = parsed["text"]
            enriched_text = personality_engine.enrich_response(original_text)
            if enriched_text != original_text:
                parsed["text"] = enriched_text
                parsed["enriched"] = True
                print(f"[Personality] Response enriched with personality markers")

        # Phase 3: Learn from this interaction
        if user_text and parsed.get("text") and not RAW_MODE:
            # Check for explicit feedback in user message
            explicit_feedback = personality_engine.detect_user_feedback(user_text)
            if explicit_feedback:
                # This message contains feedback about a PREVIOUS response
                # Learn from the previous exchange
                if personality_engine._last_response:
                    personality_engine.learn_from_interaction(
                        user_message=personality_engine._last_user_message,
                        sage_response=personality_engine._last_response,
                        implicit_signal=explicit_feedback
                    )
            else:
                # No explicit feedback - assume "continued_conversation" is positive
                if personality_engine._last_response and personality_engine.state.turn_count > 1:
                    personality_engine.learn_from_interaction(
                        user_message=personality_engine._last_user_message,
                        sage_response=personality_engine._last_response,
                        implicit_signal="continued_conversation"
                    )

            # Store this response for next turn's learning
            personality_engine._last_response = parsed.get("text", "")

        return {"model": model, **parsed}
    except Exception as e:
        print(f"[AI] Failed to parse Ollama response as JSON: {str(e)}")
        return {"model": model, "type": "none"}
