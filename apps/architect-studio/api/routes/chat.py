"""
Simple chat endpoints for mobile and web clients.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import time
from difflib import SequenceMatcher
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from threading import Event
from typing import Any, Callable, Dict, List, Literal, Optional
from uuid import uuid4

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from architect.llm import DEFAULT_MODEL, LLMClient

try:
    import paho.mqtt.client as mqtt
    import paho.mqtt.publish as mqtt_publish
except Exception:  # pragma: no cover - optional runtime dependency
    mqtt = None
    mqtt_publish = None

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1, max_length=12000)


class ChatAttachment(BaseModel):
    id: Optional[str] = Field(default=None, max_length=120)
    name: str = Field(..., min_length=1, max_length=260)
    mime_type: str = Field(..., min_length=1, max_length=120)
    size_bytes: int = Field(..., ge=1, le=2 * 1024 * 1024)
    data_base64: str = Field(..., min_length=1, max_length=4_000_000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    conversation_id: Optional[str] = Field(default=None)
    provider: str = Field(default="ollama")
    model: Optional[str] = Field(default=None)
    system_prompt: Optional[str] = Field(default=None, max_length=12000)
    max_history_turns: int = Field(default=8, ge=1, le=50)
    attachments: List[ChatAttachment] = Field(default_factory=list, max_length=4)


class ChatResponse(BaseModel):
    success: bool
    conversation_id: str
    reply: str
    provider: str
    model: str
    message_count: int
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    latency_ms: int = 0


class ChatHealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, Any]
    capabilities: Dict[str, Any]


class VisionLatestResponse(BaseModel):
    success: bool
    location: str
    mqtt_online: bool
    mqtt_error: Optional[str] = None
    frame_available: bool = False
    image_base64: Optional[str] = None
    mime_type: str = "image/jpeg"
    width: Optional[int] = None
    height: Optional[int] = None
    people_count: int = 0
    face_detected: bool = False
    activity: str = "unknown"
    mood: str = "unknown"
    objects: List[str] = Field(default_factory=list)
    scene_description: str = ""
    frame_timestamp: Optional[float] = None
    stale_seconds: Optional[float] = None


class VisionScanRequest(BaseModel):
    location: str = Field(default="office", min_length=1, max_length=40)


class VisionScanResponse(BaseModel):
    success: bool
    location: str
    mqtt_online: bool
    mqtt_error: Optional[str] = None
    topic: str


_lock = Lock()
_conversations: Dict[str, List[ChatMessage]] = {}
_llm_client = LLMClient()

_MQTT_REQUEST_TOPIC = os.getenv("SAGE_BRAIN_CHAT_REQUEST_TOPIC", "sage/brain/chat/request")
_MQTT_RESPONSE_TOPIC = os.getenv("SAGE_BRAIN_CHAT_RESPONSE_TOPIC", "sage/brain/chat/response")
_MQTT_BRAIN_CONFIG_TOPIC = os.getenv("SAGE_BRAIN_CONFIG_TOPIC", "sage/brain/config")
_MQTT_BRAIN_COMMAND_TOPIC = os.getenv("SAGE_BRAIN_COMMAND_TOPIC", "sage/brain/command")
_MQTT_BRAIN_STATUS_TOPIC = os.getenv("SAGE_BRAIN_STATUS_TOPIC", "sage/brain/status")
_MQTT_TIMEOUT_SEC = float(os.getenv("SAGE_BRAIN_CHAT_TIMEOUT_SEC", "180"))
_MQTT_CONNECT_TIMEOUT_SEC = float(os.getenv("SAGE_BRAIN_CHAT_CONNECT_TIMEOUT_SEC", "5"))
_CHAT_LOG_ENABLED = os.getenv("SAGE_CHAT_LOG_ENABLED", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
_CHAT_LOG_PATH = Path(
    os.getenv("SAGE_CHAT_LOG_PATH", ".sage_memory/chat_logs/chat_history.jsonl")
).expanduser()
_MAX_ATTACHMENT_TEXT_CHARS = int(os.getenv("SAGE_CHAT_MAX_ATTACHMENT_TEXT_CHARS", "5000"))
_MAX_CHAT_MESSAGE_CHARS = 12000
_CHAT_DEDUPE_WINDOW_SEC = float(os.getenv("SAGE_CHAT_DEDUPE_WINDOW_SEC", "5"))
_CHAT_LOOP_GUARD_USER_SIMILARITY = float(os.getenv("SAGE_CHAT_LOOP_GUARD_USER_SIMILARITY", "0.9"))
_CHAT_LOOP_GUARD_PREVIEW_CHARS = int(os.getenv("SAGE_CHAT_LOOP_GUARD_PREVIEW_CHARS", "280"))
_recent_turn_cache: Dict[str, Dict[str, Any]] = {}
_CONTROL_AUDIT_ENABLED = os.getenv("SAGE_CONTROL_AUDIT_ENABLED", "true").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
_CONTROL_AUDIT_LOG_PATH = Path(
    os.getenv("SAGE_CONTROL_AUDIT_PATH", ".sage_memory/chat_logs/control_audit.jsonl")
).expanduser()
_brain_control_shadow: Dict[str, Any] = {
    "personality": os.getenv("DEFAULT_PERSONALITY", "kenyan_babe"),
    "raw_mode": os.getenv("SAGE_RAW_MODE", "false").strip().lower() in {"1", "true", "yes", "on"},
    "voice_input_enabled": os.getenv("SAGE_VOICE_INPUT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"},
    "voice_output_enabled": os.getenv("SAGE_VOICE_OUTPUT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"},
    "last_command": None,
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


class BrainControlState(BaseModel):
    personality: str
    raw_mode: bool
    voice_input_enabled: bool
    voice_output_enabled: bool
    last_command: Optional[str] = None
    updated_at: str


class BrainControlStateResponse(BaseModel):
    success: bool
    state: BrainControlState
    mqtt_online: bool
    mqtt_error: Optional[str] = None


class BrainControlConfigRequest(BaseModel):
    personality: Optional[str] = Field(default=None, min_length=1, max_length=80)
    raw_mode: Optional[bool] = None
    voice_input_enabled: Optional[bool] = None
    voice_output_enabled: Optional[bool] = None


class BrainControlCommandRequest(BaseModel):
    command: Literal[
        "clear_conversation",
        "clear_memory",
        "clear_episodes",
        "kill_switch",
        "resume_voice",
    ]


class BrainControlAuditEntry(BaseModel):
    ts: str
    action: str
    source: str
    payload: Dict[str, Any]
    status: str = "ok"
    error: Optional[str] = None


class BrainControlAuditResponse(BaseModel):
    success: bool
    entries: List[BrainControlAuditEntry]


def _decode_attachment_text(attachment: ChatAttachment) -> str:
    mime = (attachment.mime_type or "").lower()
    is_text_like = (
        mime.startswith("text/")
        or "json" in mime
        or "xml" in mime
        or "yaml" in mime
    )
    if not is_text_like:
        return ""

    try:
        raw = base64.b64decode(attachment.data_base64.encode("utf-8"), validate=False)
        text = raw.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""

    if not text:
        return ""
    if len(text) > _MAX_ATTACHMENT_TEXT_CHARS:
        return text[:_MAX_ATTACHMENT_TEXT_CHARS] + "\n...[truncated]"
    return text


def _build_user_message_with_attachments(request: ChatRequest) -> str:
    base_message = request.message.strip()
    if not request.attachments:
        return base_message

    lines: List[str] = [base_message, "", "[Attachments]"]
    for index, attachment in enumerate(request.attachments, start=1):
        lines.append(
            f"{index}. {attachment.name} ({attachment.mime_type}, {attachment.size_bytes} bytes)"
        )
        text_excerpt = _decode_attachment_text(attachment)
        if text_excerpt:
            lines.append(f"Content excerpt:\n{text_excerpt}")
        elif attachment.mime_type.startswith("image/"):
            lines.append(
                "Image attached. Visual parsing is not enabled on this endpoint; ask user for key details if needed."
            )
        else:
            lines.append("Binary attachment received (text extraction unavailable).")

    lines.append("")
    lines.append(
        "Instruction: Use the attachment context above when answering. If content is unavailable, say so clearly."
    )
    merged = "\n".join(lines).strip()
    if len(merged) <= _MAX_CHAT_MESSAGE_CHARS:
        return merged
    truncated = merged[: _MAX_CHAT_MESSAGE_CHARS - 32].rstrip()
    return f"{truncated}\n...[attachment context truncated]"


def _normalize_for_compare(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return " ".join(text.strip().lower().split())


def _text_similarity(a: str, b: str) -> float:
    na = _normalize_for_compare(a)
    nb = _normalize_for_compare(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return SequenceMatcher(a=na, b=nb).ratio()


def _request_signature(provider: str, user_message: str, system_prompt: Optional[str]) -> str:
    key = "|".join(
        [
            _normalize_for_compare(provider),
            _normalize_for_compare(user_message),
            _normalize_for_compare(system_prompt or ""),
        ]
    )
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def _prune_recent_turn_cache(limit: int = 1000) -> None:
    if len(_recent_turn_cache) <= limit:
        return
    oldest = sorted(_recent_turn_cache.items(), key=lambda kv: kv[1].get("ts", 0.0))
    for key, _ in oldest[: len(_recent_turn_cache) - limit]:
        _recent_turn_cache.pop(key, None)


def _get_recent_cached_turn(conversation_id: str, signature: str) -> Optional[Dict[str, Any]]:
    cached = _recent_turn_cache.get(conversation_id)
    if not cached:
        return None
    if cached.get("signature") != signature:
        return None
    age = time.monotonic() - float(cached.get("ts", 0.0))
    if age > _CHAT_DEDUPE_WINDOW_SEC:
        return None
    reply = (cached.get("reply") or "").strip()
    if not reply:
        return None
    return cached


def _set_recent_cached_turn(
    *,
    conversation_id: str,
    signature: str,
    provider: str,
    model: str,
    reply: str,
    message_count: int,
) -> None:
    _recent_turn_cache[conversation_id] = {
        "signature": signature,
        "provider": provider,
        "model": model,
        "reply": reply,
        "message_count": message_count,
        "ts": time.monotonic(),
    }
    _prune_recent_turn_cache()


def _latest_user_and_assistant(messages: List[ChatMessage]) -> tuple[str, str]:
    last_user = ""
    last_assistant = ""
    for msg in reversed(messages):
        if not last_assistant and msg.role == "assistant":
            last_assistant = msg.content
        elif not last_user and msg.role == "user":
            last_user = msg.content
        if last_user and last_assistant:
            break
    return last_user, last_assistant


def _compose_loop_guard_system_prompt(
    *,
    base_system_prompt: Optional[str],
    user_message: str,
    last_user: str,
    last_assistant: str,
) -> Optional[str]:
    if not last_assistant or not last_user:
        return base_system_prompt

    # Only trigger loop guard when user input changed materially.
    if _text_similarity(user_message, last_user) >= _CHAT_LOOP_GUARD_USER_SIMILARITY:
        return base_system_prompt

    preview = " ".join(last_assistant.strip().split())
    if len(preview) > _CHAT_LOOP_GUARD_PREVIEW_CHARS:
        preview = preview[:_CHAT_LOOP_GUARD_PREVIEW_CHARS].rstrip() + "..."

    guard = (
        "Loop guard: The user message has changed. Do not repeat/paraphrase your previous reply. "
        "Respond directly to the current message with fresh wording and concrete value. "
        "If the user just answered your prior question, acknowledge that answer and advance; "
        "do not ask the same or semantically equivalent question again. "
        f'Previous assistant reply to avoid repeating: "{preview}"'
    )

    if base_system_prompt and base_system_prompt.strip():
        return f"{base_system_prompt.strip()}\n\n{guard}"
    return guard


def _trim_history(messages: List[ChatMessage], max_history_turns: int) -> List[ChatMessage]:
    if not messages:
        return []

    system: List[ChatMessage] = []
    rest = messages

    if messages[0].role == "system":
        system = [messages[0]]
        rest = messages[1:]

    max_non_system_messages = max_history_turns * 2
    if len(rest) > max_non_system_messages:
        rest = rest[-max_non_system_messages:]

    return [*system, *rest]


def _model_input(messages: List[ChatMessage]) -> List[dict]:
    return [m.model_dump() for m in messages]


def _append_chat_exchange_log(
    *,
    conversation_id: str,
    provider: str,
    model: str,
    user_message: str,
    assistant_reply: str,
    message_count: int,
) -> None:
    if not _CHAT_LOG_ENABLED:
        return

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "conversation_id": conversation_id,
        "provider": provider,
        "model": model,
        "user_message": user_message,
        "assistant_reply": assistant_reply,
        "message_count": message_count,
    }

    try:
        _CHAT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _CHAT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - best-effort logging
        print(f"[ChatLog] Failed to persist exchange: {exc}")


def _sse_data(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _brain_control_state_payload() -> BrainControlState:
    with _lock:
        return BrainControlState(
            personality=str(_brain_control_shadow.get("personality") or "kenyan_babe"),
            raw_mode=bool(_brain_control_shadow.get("raw_mode", False)),
            voice_input_enabled=bool(_brain_control_shadow.get("voice_input_enabled", True)),
            voice_output_enabled=bool(_brain_control_shadow.get("voice_output_enabled", True)),
            last_command=(
                str(_brain_control_shadow.get("last_command"))
                if _brain_control_shadow.get("last_command") is not None
                else None
            ),
            updated_at=str(_brain_control_shadow.get("updated_at") or datetime.now(timezone.utc).isoformat()),
        )


def _update_brain_control_shadow(**kwargs: Any) -> None:
    with _lock:
        for key, value in kwargs.items():
            if value is None:
                continue
            if key in {"raw_mode", "voice_input_enabled", "voice_output_enabled"}:
                _brain_control_shadow[key] = bool(value)
            else:
                _brain_control_shadow[key] = value
        _brain_control_shadow["updated_at"] = datetime.now(timezone.utc).isoformat()


def _append_control_audit(
    *,
    action: str,
    source: str,
    payload: Dict[str, Any],
    status: str = "ok",
    error: Optional[str] = None,
) -> None:
    if not _CONTROL_AUDIT_ENABLED:
        return

    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "source": source or "unknown",
        "payload": payload,
        "status": status,
        "error": error,
    }

    try:
        _CONTROL_AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _CONTROL_AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - best-effort logging
        print(f"[ControlAudit] Failed to persist audit record: {exc}")


def _audit_entry_matches_filter(
    audit_type: Literal["all", "config", "command", "error"],
    *,
    action: str,
    status: str,
    error: Optional[str],
) -> bool:
    if audit_type == "config":
        return action == "config_update" or "config" in action
    if audit_type == "command":
        return action == "command"
    if audit_type == "error":
        return status == "error" or bool(error)
    return True


def _read_control_audit(
    limit: int = 50,
    audit_type: Literal["all", "config", "command", "error"] = "all",
) -> List[BrainControlAuditEntry]:
    if limit <= 0:
        return []
    if not _CONTROL_AUDIT_LOG_PATH.exists():
        return []

    entries: List[BrainControlAuditEntry] = []
    try:
        with _CONTROL_AUDIT_LOG_PATH.open("r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception:
        return []

    for raw in reversed(lines):
        if len(entries) >= limit:
            break
        line = raw.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if not isinstance(parsed, dict):
            continue
        action = str(parsed.get("action") or "unknown")
        status = str(parsed.get("status") or "ok")
        error = str(parsed.get("error")) if parsed.get("error") is not None else None
        if not _audit_entry_matches_filter(
            audit_type,
            action=action,
            status=status,
            error=error,
        ):
            continue
        try:
            entries.append(
                BrainControlAuditEntry(
                    ts=str(parsed.get("ts") or datetime.now(timezone.utc).isoformat()),
                    action=action,
                    source=str(parsed.get("source") or "unknown"),
                    payload=dict(parsed.get("payload") or {}),
                    status=status,
                    error=error,
                )
            )
        except Exception:
            continue

    return entries


def _publish_mqtt_json(topic: str, payload: Dict[str, Any], *, retain: bool = False) -> None:
    if mqtt_publish is None:
        raise HTTPException(
            status_code=503,
            detail="Brain MQTT bridge unavailable: paho-mqtt is not installed",
        )
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    try:
        mqtt_publish.single(
            topic,
            payload=json.dumps(payload),
            hostname=host,
            port=port,
            retain=retain,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"MQTT publish failed for {topic} via {host}:{port}: {exc}",
        ) from exc


def _fetch_brain_status(timeout_sec: float = 1.25) -> Optional[Dict[str, Any]]:
    if mqtt is None:
        return None

    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    event = Event()
    status_box: Dict[str, Any] = {}

    def on_connect(client, userdata, flags, rc, *args):  # noqa: ANN001
        rc_value = int(getattr(rc, "value", rc))
        if rc_value != 0:
            event.set()
            return
        client.subscribe(_MQTT_BRAIN_STATUS_TOPIC)

    def on_message(client, userdata, message):  # noqa: ANN001
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            status_box.update(payload)
        event.set()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(host, port, 60)
    except Exception:
        return None

    client.loop_start()
    try:
        if event.wait(timeout=timeout_sec):
            return status_box or None
        return None
    finally:
        client.loop_stop()
        client.disconnect()


def _mqtt_broker_online() -> tuple[bool, Optional[str]]:
    if mqtt is None:
        return False, "paho-mqtt not installed"

    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    client = mqtt.Client()
    client.socket_timeout = 2
    try:
        client.connect(host, port, 60)
        client.disconnect()
        return True, None
    except Exception as exc:
        return False, f"{host}:{port} unreachable ({exc})"


def _fetch_mqtt_topic_json(topic: str, timeout_sec: float = 1.25) -> Optional[Dict[str, Any]]:
    if mqtt is None:
        return None

    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    event = Event()
    payload_box: Dict[str, Any] = {}

    def on_connect(client, userdata, flags, rc, *args):  # noqa: ANN001
        rc_value = int(getattr(rc, "value", rc))
        if rc_value != 0:
            event.set()
            return
        client.subscribe(topic)

    def on_message(client, userdata, message):  # noqa: ANN001
        if message.topic != topic:
            return
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except Exception:
            payload = None
        if isinstance(payload, dict):
            payload_box.update(payload)
        event.set()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(host, port, 60)
    except Exception:
        return None

    client.loop_start()
    try:
        if event.wait(timeout=max(0.2, timeout_sec)):
            return payload_box or None
        return None
    finally:
        client.loop_stop()
        client.disconnect()


def _stream_ollama_reply(
    *,
    prompt_messages: List[dict],
    model: str,
) -> Any:
    payload = {
        "model": model,
        "messages": prompt_messages,
        "stream": True,
        "options": {"temperature": 0.2, "num_ctx": 8192},
    }
    response = requests.post(
        _llm_client.base_url,
        json=payload,
        stream=True,
        timeout=_llm_client.request_timeout,
    )
    response.raise_for_status()

    text_chunks: List[str] = []
    output_tokens = 0
    input_tokens = 0
    for line in response.iter_lines():
        if not line:
            continue
        try:
            chunk = json.loads(line)
        except Exception:
            continue

        message = chunk.get("message") or {}
        delta = message.get("content")
        if isinstance(delta, str) and delta:
            text_chunks.append(delta)
            yield delta

        if chunk.get("done", False):
            output_tokens = int(chunk.get("eval_count", 0) or 0)
            input_tokens = int(chunk.get("prompt_eval_count", 0) or 0)
            break

    if output_tokens > 0:
        _llm_client._log_usage("ollama", model, input_tokens, output_tokens, 0.0, "streaming_api")
    _llm_client._update_usage(0.0)


def _chat_via_brain_mqtt(
    request: ChatRequest,
    conversation_id: str,
    *,
    user_message: Optional[str] = None,
    stream: bool = False,
    on_delta: Optional[Callable[[str], None]] = None,
) -> dict:
    if mqtt is None:
        raise HTTPException(
            status_code=503,
            detail="Brain MQTT bridge unavailable: paho-mqtt is not installed",
        )

    request_id = str(uuid4())
    response_event = Event()
    connect_event = Event()
    response_box: Dict[str, dict] = {}
    error_box: Dict[str, str] = {}

    payload = {
        "request_id": request_id,
        "conversation_id": conversation_id,
        "text": (user_message or request.message).strip(),
        "max_history_turns": request.max_history_turns,
        "system_prompt": request.system_prompt,
        "stream": bool(stream),
    }

    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))

    def on_connect(client, userdata, flags, rc, *args):  # noqa: ANN001
        rc_value = int(getattr(rc, "value", rc))
        if rc_value != 0:
            error_box["error"] = f"Could not connect to MQTT broker (rc={rc_value})"
            connect_event.set()
            return

        client.subscribe(_MQTT_RESPONSE_TOPIC)
        result = client.publish(_MQTT_REQUEST_TOPIC, json.dumps(payload))
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            error_box["error"] = "Failed to publish brain chat request"
        connect_event.set()

    def on_message(client, userdata, message):  # noqa: ANN001
        try:
            data = json.loads(message.payload.decode())
        except Exception:
            return

        if data.get("request_id") != request_id:
            return

        if data.get("type") == "delta":
            if on_delta:
                delta = data.get("delta") or data.get("text") or ""
                if isinstance(delta, str) and delta:
                    on_delta(delta)
            return

        response_box["data"] = data
        response_event.set()

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(host, port, 60)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to MQTT broker at {host}:{port}: {exc}",
        ) from exc

    client.loop_start()
    try:
        if not connect_event.wait(timeout=_MQTT_CONNECT_TIMEOUT_SEC):
            raise HTTPException(status_code=504, detail="Timed out waiting for MQTT connection")

        if "error" in error_box:
            raise HTTPException(status_code=502, detail=error_box["error"])

        if not response_event.wait(timeout=_MQTT_TIMEOUT_SEC):
            raise HTTPException(
                status_code=504,
                detail=(
                    "Timed out waiting for brain response. "
                    "Check that `sage brain` is running and subscribed to chat topics."
                ),
            )

        response_data = response_box.get("data") or {}
        if not response_data.get("success", False):
            raise HTTPException(
                status_code=502,
                detail=response_data.get("error", "Brain service returned an error"),
            )

        response_text = (response_data.get("text") or "").strip()
        if not response_text:
            raise HTTPException(status_code=502, detail="Brain returned an empty response")

        return response_data
    finally:
        client.loop_stop()
        client.disconnect()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    conversation_id = request.conversation_id or str(uuid4())
    provider = (request.provider or "ollama").strip().lower()
    user_message = _build_user_message_with_attachments(request)
    signature = _request_signature(provider, user_message, request.system_prompt)

    with _lock:
        cached_turn = _get_recent_cached_turn(conversation_id, signature)
        if cached_turn:
            return ChatResponse(
                success=True,
                conversation_id=conversation_id,
                reply=str(cached_turn.get("reply") or ""),
                provider=str(cached_turn.get("provider") or provider),
                model=str(cached_turn.get("model") or "unknown"),
                message_count=int(cached_turn.get("message_count") or 0),
            )

        history = list(_conversations.get(conversation_id, []))
        last_user, last_assistant = _latest_user_and_assistant(history)
        effective_system_prompt = _compose_loop_guard_system_prompt(
            base_system_prompt=request.system_prompt,
            user_message=user_message,
            last_user=last_user,
            last_assistant=last_assistant,
        )
        effective_request = request.model_copy(update={"system_prompt": effective_system_prompt})

        if effective_request.system_prompt:
            system = ChatMessage(role="system", content=effective_request.system_prompt)
            if history and history[0].role == "system":
                history[0] = system
            else:
                history = [system, *history]

        history.append(ChatMessage(role="user", content=user_message))
        history = _trim_history(history, request.max_history_turns)
        _conversations[conversation_id] = history
        prompt_messages = _model_input(history)

    # Initialise usage accumulators (populated by LLM path, zero for brain/MQTT)
    _result_input_tokens = 0
    _result_output_tokens = 0
    _result_cost = 0.0
    _chat_latency_ms = 0

    if provider in {"brain", "sage_brain"}:
        _brain_start = time.monotonic()
        brain_data = await asyncio.to_thread(
            _chat_via_brain_mqtt,
            effective_request,
            conversation_id,
            user_message=user_message,
        )
        _chat_latency_ms = int((time.monotonic() - _brain_start) * 1000)
        assistant_text = (brain_data.get("text") or "").strip()
        response_model = brain_data.get("model") or "brain_runtime"
    else:
        _chat_start = time.monotonic()
        chat_result = _llm_client.chat(
            prompt_messages,
            stream=False,
            provider=effective_request.provider,
            model=effective_request.model,
        )
        _chat_latency_ms = int((time.monotonic() - _chat_start) * 1000)

        if chat_result.text.strip().lower().startswith("error"):
            raise HTTPException(status_code=502, detail=chat_result.text)

        assistant_text = chat_result.text.strip()
        if not assistant_text:
            raise HTTPException(status_code=502, detail="LLM returned an empty response")
        response_model = chat_result.model or request.model or DEFAULT_MODEL
        _result_input_tokens = chat_result.input_tokens
        _result_output_tokens = chat_result.output_tokens
        _result_cost = chat_result.cost

    with _lock:
        history = list(_conversations.get(conversation_id, []))
        history.append(ChatMessage(role="assistant", content=assistant_text))
        history = _trim_history(history, request.max_history_turns)
        _conversations[conversation_id] = history
        message_count = len(history)
        _set_recent_cached_turn(
            conversation_id=conversation_id,
            signature=signature,
            provider=provider,
            model=response_model,
            reply=assistant_text,
            message_count=message_count,
        )

    _append_chat_exchange_log(
        conversation_id=conversation_id,
        provider=provider,
        model=response_model,
        user_message=user_message,
        assistant_reply=assistant_text,
        message_count=message_count,
    )

    return ChatResponse(
        success=True,
        conversation_id=conversation_id,
        reply=assistant_text,
        provider=provider,
        model=response_model,
        message_count=message_count,
        input_tokens=_result_input_tokens,
        output_tokens=_result_output_tokens,
        cost=_result_cost,
        latency_ms=_chat_latency_ms,
    )


@router.get("/health", response_model=ChatHealthResponse)
async def chat_health() -> ChatHealthResponse:
    mqtt_online, mqtt_error = _mqtt_broker_online()
    brain_ready = mqtt_online and mqtt is not None
    status = "healthy" if brain_ready else "degraded"
    return ChatHealthResponse(
        status=status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services={
            "api": True,
            "chat_store": True,
            "chat_log_enabled": _CHAT_LOG_ENABLED,
            "mqtt_bridge": mqtt is not None,
            "mqtt_broker_online": mqtt_online,
            "mqtt_error": mqtt_error,
            "brain_ready": brain_ready,
            "active_conversations": len(_conversations),
            "brain_control": _brain_control_state_payload().model_dump(),
        },
        capabilities={
            "streaming_sse": True,
            "provider_brain_streaming": "status+final",
            "provider_ollama_streaming": "token",
            "provider_other_streaming": "final",
        },
    )


@router.get("/control", response_model=BrainControlStateResponse)
async def get_brain_control_state() -> BrainControlStateResponse:
    mqtt_online, mqtt_error = _mqtt_broker_online()
    if mqtt_online:
        status = _fetch_brain_status()
        if isinstance(status, dict) and status:
            _update_brain_control_shadow(
                personality=status.get("personality"),
                raw_mode=status.get("raw_mode"),
                voice_input_enabled=status.get("voice_input_enabled"),
                voice_output_enabled=status.get("voice_output_enabled"),
                last_command=status.get("last_command"),
            )

    return BrainControlStateResponse(
        success=True,
        state=_brain_control_state_payload(),
        mqtt_online=mqtt_online,
        mqtt_error=mqtt_error,
    )


@router.get("/control/audit", response_model=BrainControlAuditResponse)
async def get_brain_control_audit(
    limit: int = Query(default=50, ge=1, le=200),
    audit_type: Literal["all", "config", "command", "error"] = Query(default="all", alias="type"),
) -> BrainControlAuditResponse:
    return BrainControlAuditResponse(
        success=True,
        entries=_read_control_audit(limit=limit, audit_type=audit_type),
    )


@router.post("/control/config", response_model=BrainControlStateResponse)
async def update_brain_control_config(request: BrainControlConfigRequest) -> BrainControlStateResponse:
    payload: Dict[str, Any] = {
        "source": "architect_api",
        "ts": int(time.time() * 1000),
    }
    if request.personality is not None:
        payload["personality"] = request.personality.strip()
    if request.raw_mode is not None:
        payload["raw_mode"] = bool(request.raw_mode)
    if request.voice_input_enabled is not None:
        payload["voice_input_enabled"] = bool(request.voice_input_enabled)
    if request.voice_output_enabled is not None:
        payload["voice_output_enabled"] = bool(request.voice_output_enabled)

    if len(payload) == 2:
        raise HTTPException(status_code=400, detail="No control fields provided")

    try:
        _publish_mqtt_json(_MQTT_BRAIN_CONFIG_TOPIC, payload)
    except HTTPException as exc:
        _append_control_audit(
            action="config_update",
            source=str(payload.get("source") or "architect_api"),
            payload=payload,
            status="error",
            error=str(exc.detail),
        )
        raise
    _update_brain_control_shadow(
        personality=payload.get("personality"),
        raw_mode=payload.get("raw_mode"),
        voice_input_enabled=payload.get("voice_input_enabled"),
        voice_output_enabled=payload.get("voice_output_enabled"),
    )
    _append_control_audit(
        action="config_update",
        source=str(payload.get("source") or "architect_api"),
        payload=payload,
        status="ok",
    )
    mqtt_online, mqtt_error = _mqtt_broker_online()
    return BrainControlStateResponse(
        success=True,
        state=_brain_control_state_payload(),
        mqtt_online=mqtt_online,
        mqtt_error=mqtt_error,
    )


@router.post("/control/command", response_model=BrainControlStateResponse)
async def send_brain_control_command(request: BrainControlCommandRequest) -> BrainControlStateResponse:
    payload = {
        "command": request.command,
        "source": "architect_api",
        "ts": int(time.time() * 1000),
    }
    try:
        _publish_mqtt_json(_MQTT_BRAIN_COMMAND_TOPIC, payload)
    except HTTPException as exc:
        _append_control_audit(
            action="command",
            source=str(payload.get("source") or "architect_api"),
            payload=payload,
            status="error",
            error=str(exc.detail),
        )
        raise

    shadow_update: Dict[str, Any] = {"last_command": request.command}
    if request.command == "kill_switch":
        shadow_update["voice_input_enabled"] = False
        shadow_update["voice_output_enabled"] = False
    elif request.command == "resume_voice":
        shadow_update["voice_input_enabled"] = True
        shadow_update["voice_output_enabled"] = True
    _update_brain_control_shadow(**shadow_update)
    _append_control_audit(
        action="command",
        source=str(payload.get("source") or "architect_api"),
        payload=payload,
        status="ok",
    )

    mqtt_online, mqtt_error = _mqtt_broker_online()
    return BrainControlStateResponse(
        success=True,
        state=_brain_control_state_payload(),
        mqtt_online=mqtt_online,
        mqtt_error=mqtt_error,
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    conversation_id = request.conversation_id or str(uuid4())
    provider = (request.provider or "ollama").strip().lower()
    user_message = _build_user_message_with_attachments(request)
    signature = _request_signature(provider, user_message, request.system_prompt)

    with _lock:
        cached_turn = _get_recent_cached_turn(conversation_id, signature)
        if cached_turn:
            async def cached_events():
                cached_provider = str(cached_turn.get("provider") or provider)
                cached_model = str(cached_turn.get("model") or "unknown")
                cached_reply = str(cached_turn.get("reply") or "")
                cached_count = int(cached_turn.get("message_count") or 0)
                yield _sse_data(
                    {
                        "type": "meta",
                        "conversation_id": conversation_id,
                        "provider": cached_provider,
                        "deduped_cached": True,
                    }
                )
                if cached_reply:
                    yield _sse_data({"type": "delta", "text": cached_reply})
                yield _sse_data(
                    {
                        "type": "done",
                        "success": True,
                        "conversation_id": conversation_id,
                        "reply": cached_reply,
                        "provider": cached_provider,
                        "model": cached_model,
                        "message_count": cached_count,
                        "latency_ms": 0,
                        "deduped_cached": True,
                    }
                )

            return StreamingResponse(
                cached_events(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )

        history = list(_conversations.get(conversation_id, []))
        last_user, last_assistant = _latest_user_and_assistant(history)
        effective_system_prompt = _compose_loop_guard_system_prompt(
            base_system_prompt=request.system_prompt,
            user_message=user_message,
            last_user=last_user,
            last_assistant=last_assistant,
        )
        effective_request = request.model_copy(update={"system_prompt": effective_system_prompt})
        if effective_request.system_prompt:
            system = ChatMessage(role="system", content=effective_request.system_prompt)
            if history and history[0].role == "system":
                history[0] = system
            else:
                history = [system, *history]

        history.append(ChatMessage(role="user", content=user_message))
        history = _trim_history(history, request.max_history_turns)
        _conversations[conversation_id] = history
        prompt_messages = _model_input(history)

    async def stream_events():
        started_at = time.monotonic()
        assistant_text = ""
        response_model = request.model or DEFAULT_MODEL
        message_count = len(prompt_messages)
        stream_input_tokens = 0
        stream_output_tokens = 0
        stream_cost = 0.0

        yield _sse_data(
            {
                "type": "meta",
                "conversation_id": conversation_id,
                "provider": provider,
            }
        )

        try:
            if provider in {"brain", "sage_brain"}:
                yield _sse_data({"type": "status", "phase": "waiting_for_brain"})
                delta_queue: asyncio.Queue[str] = asyncio.Queue()
                loop = asyncio.get_running_loop()

                def _on_delta(delta: str) -> None:
                    loop.call_soon_threadsafe(delta_queue.put_nowait, delta)

                brain_task = asyncio.create_task(
                    asyncio.to_thread(
                        _chat_via_brain_mqtt,
                        effective_request,
                        conversation_id,
                        user_message=user_message,
                        stream=True,
                        on_delta=_on_delta,
                    )
                )

                while True:
                    if brain_task.done() and delta_queue.empty():
                        break
                    try:
                        delta = await asyncio.wait_for(delta_queue.get(), timeout=0.25)
                    except asyncio.TimeoutError:
                        continue
                    assistant_text += delta
                    yield _sse_data({"type": "delta", "text": delta})

                brain_data = await brain_task
                response_model = brain_data.get("model") or "brain_runtime"
                final_text = (brain_data.get("text") or "").strip()
                if not assistant_text and final_text:
                    assistant_text = final_text
                    yield _sse_data({"type": "delta", "text": final_text})
            elif provider in {"ollama", ""}:
                response_model = request.model or _llm_client.model
                for delta in _stream_ollama_reply(prompt_messages=prompt_messages, model=response_model):
                    assistant_text += delta
                    yield _sse_data({"type": "delta", "text": delta})
            else:
                yield _sse_data({"type": "status", "phase": "waiting_for_provider"})
                chat_result = await asyncio.to_thread(
                    _llm_client.chat,
                    prompt_messages,
                    False,
                    effective_request.provider,
                    effective_request.model,
                )
                if chat_result.text.strip().lower().startswith("error"):
                    raise HTTPException(status_code=502, detail=chat_result.text)
                assistant_text = chat_result.text.strip()
                response_model = chat_result.model or response_model
                stream_input_tokens = chat_result.input_tokens
                stream_output_tokens = chat_result.output_tokens
                stream_cost = chat_result.cost
                if assistant_text:
                    yield _sse_data({"type": "delta", "text": assistant_text})

            if not assistant_text:
                raise HTTPException(status_code=502, detail="LLM returned an empty response")

            with _lock:
                final_history = list(_conversations.get(conversation_id, []))
                final_history.append(ChatMessage(role="assistant", content=assistant_text))
                final_history = _trim_history(final_history, request.max_history_turns)
                _conversations[conversation_id] = final_history
                message_count = len(final_history)
                _set_recent_cached_turn(
                    conversation_id=conversation_id,
                    signature=signature,
                    provider=provider,
                    model=response_model,
                    reply=assistant_text,
                    message_count=message_count,
                )

            _append_chat_exchange_log(
                conversation_id=conversation_id,
                provider=provider,
                model=response_model,
                user_message=user_message,
                assistant_reply=assistant_text,
                message_count=message_count,
            )

            yield _sse_data(
                {
                    "type": "done",
                    "success": True,
                    "conversation_id": conversation_id,
                    "reply": assistant_text,
                    "provider": provider,
                    "model": response_model,
                    "message_count": message_count,
                    "latency_ms": int((time.monotonic() - started_at) * 1000),
                    "input_tokens": stream_input_tokens,
                    "output_tokens": stream_output_tokens,
                    "cost": stream_cost,
                }
            )
        except HTTPException as exc:
            yield _sse_data(
                {
                    "type": "error",
                    "error": str(exc.detail),
                    "status_code": exc.status_code,
                }
            )
        except Exception as exc:
            yield _sse_data({"type": "error", "error": str(exc)})

    return StreamingResponse(
        stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/vision/latest", response_model=VisionLatestResponse)
async def get_vision_latest(
    location: str = Query(default="office", min_length=1, max_length=40),
) -> VisionLatestResponse:
    room = location.strip().lower()
    mqtt_online, mqtt_error = _mqtt_broker_online()
    if not mqtt_online:
        return VisionLatestResponse(
            success=False,
            location=room,
            mqtt_online=False,
            mqtt_error=mqtt_error,
        )

    payload = _fetch_mqtt_topic_json(f"sage/vision/{room}/frame", timeout_sec=1.5) or {}
    if not isinstance(payload, dict):
        payload = {}

    objects_raw = payload.get("objects")
    objects: List[str] = []
    if isinstance(objects_raw, list):
        for item in objects_raw:
            if isinstance(item, str) and item.strip():
                objects.append(item.strip())

    image_base64 = payload.get("image_base64")
    if not isinstance(image_base64, str) or not image_base64.strip():
        image_base64 = None

    frame_ts = payload.get("timestamp")
    frame_timestamp: Optional[float] = None
    if isinstance(frame_ts, (int, float)):
        frame_timestamp = float(frame_ts)

    stale_seconds: Optional[float] = None
    if frame_timestamp is not None:
        stale_seconds = max(0.0, time.time() - frame_timestamp)

    return VisionLatestResponse(
        success=True,
        location=room,
        mqtt_online=True,
        mqtt_error=None,
        frame_available=image_base64 is not None,
        image_base64=image_base64,
        mime_type=str(payload.get("mime_type") or "image/jpeg"),
        width=int(payload.get("width")) if isinstance(payload.get("width"), (int, float)) else None,
        height=int(payload.get("height")) if isinstance(payload.get("height"), (int, float)) else None,
        people_count=int(payload.get("people_count") or 0),
        face_detected=bool(payload.get("face_detected", False)),
        activity=str(payload.get("activity") or "unknown"),
        mood=str(payload.get("mood") or "unknown"),
        objects=objects,
        scene_description=str(payload.get("scene_description") or ""),
        frame_timestamp=frame_timestamp,
        stale_seconds=stale_seconds,
    )


@router.post("/vision/request", response_model=VisionScanResponse)
async def request_vision_scan(request: VisionScanRequest) -> VisionScanResponse:
    room = request.location.strip().lower()
    topic = f"sage/vision/{room}/request"
    _publish_mqtt_json(
        topic,
        {
            "capture": True,
            "source": "architect_api",
            "ts": int(time.time() * 1000),
        },
    )
    mqtt_online, mqtt_error = _mqtt_broker_online()
    return VisionScanResponse(
        success=True,
        location=room,
        topic=topic,
        mqtt_online=mqtt_online,
        mqtt_error=mqtt_error,
    )


# ── Conversation listing ──────────────────────────────────────────────
class ConversationSummary(BaseModel):
    conversation_id: str
    message_count: int
    first_message: str = ""


@router.get("/conversations")
async def list_conversations(limit: int = Query(default=50, ge=1, le=200)):
    """Return lightweight summaries of active in-memory conversations."""
    with _lock:
        summaries: List[ConversationSummary] = []
        for cid, messages in _conversations.items():
            non_system = [m for m in messages if m.role != "system"]
            first_msg = non_system[0].content[:80] if non_system else ""
            summaries.append(ConversationSummary(
                conversation_id=cid,
                message_count=len(messages),
                first_message=first_msg,
            ))
    # Most-recently-created first (dict insertion order)
    summaries = list(reversed(summaries))[:limit]
    return {"success": True, "conversations": [s.model_dump() for s in summaries]}


# ── Available models registry ────────────────────────────────────────
_AVAILABLE_MODELS: Dict[str, Any] = {
    "brain": {
        "label": "Brain (Local)",
        "models": [
            {"id": "auto", "label": "Auto (Smart Routing)", "tier": "auto"},
        ],
    },
    "ollama": {
        "label": "Ollama (Local)",
        "models": [
            {"id": "gemma3:12b", "label": "Gemma 3 12B", "tier": "mid"},
            {"id": "qwen2.5:3b", "label": "Qwen 2.5 3B", "tier": "fast"},
        ],
    },
    "anthropic": {
        "label": "Anthropic",
        "models": [
            {"id": "claude-sonnet-4.5", "label": "Claude Sonnet 4.5", "tier": "mid"},
            {"id": "claude-opus-4.5", "label": "Claude Opus 4.5", "tier": "deep"},
            {"id": "claude-haiku-4.5", "label": "Claude Haiku 4.5", "tier": "fast"},
        ],
    },
    "openai": {
        "label": "OpenAI",
        "models": [
            {"id": "gpt-4o", "label": "GPT-4o", "tier": "mid"},
            {"id": "gpt-4o-mini", "label": "GPT-4o Mini", "tier": "fast"},
        ],
    },
    "google": {
        "label": "Google",
        "models": [
            {"id": "gemini-3-flash-preview", "label": "Gemini 3 Flash", "tier": "fast"},
            {"id": "gemini-3-pro-preview", "label": "Gemini 3 Pro", "tier": "mid"},
            {"id": "gemini-2.5-pro", "label": "Gemini 2.5 Pro", "tier": "deep"},
        ],
    },
}


@router.get("/models")
async def list_models():
    """Return the static registry of supported providers and their models."""
    return {"success": True, "providers": _AVAILABLE_MODELS}


# ── Single conversation CRUD ─────────────────────────────────────────
@router.get("/{conversation_id}")
async def get_conversation(conversation_id: str):
    with _lock:
        history = _conversations.get(conversation_id)

    if history is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "success": True,
        "conversation_id": conversation_id,
        "messages": _model_input(history),
        "message_count": len(history),
    }


@router.delete("/{conversation_id}")
async def delete_conversation(conversation_id: str):
    with _lock:
        existed = conversation_id in _conversations
        if existed:
            del _conversations[conversation_id]

    if not existed:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"success": True, "conversation_id": conversation_id}
