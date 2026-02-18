"""
Simple chat endpoints for mobile and web clients.
"""
from __future__ import annotations

import json
import os
from threading import Lock
from threading import Event
from typing import Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from architect.llm import DEFAULT_MODEL, LLMClient

try:
    import paho.mqtt.client as mqtt
except Exception:  # pragma: no cover - optional runtime dependency
    mqtt = None

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1, max_length=12000)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=12000)
    conversation_id: Optional[str] = Field(default=None)
    provider: str = Field(default="ollama")
    model: Optional[str] = Field(default=None)
    system_prompt: Optional[str] = Field(default=None, max_length=12000)
    max_history_turns: int = Field(default=8, ge=1, le=50)


class ChatResponse(BaseModel):
    success: bool
    conversation_id: str
    reply: str
    provider: str
    model: str
    message_count: int


_lock = Lock()
_conversations: Dict[str, List[ChatMessage]] = {}
_llm_client = LLMClient()

_MQTT_REQUEST_TOPIC = os.getenv("SAGE_BRAIN_CHAT_REQUEST_TOPIC", "sage/brain/chat/request")
_MQTT_RESPONSE_TOPIC = os.getenv("SAGE_BRAIN_CHAT_RESPONSE_TOPIC", "sage/brain/chat/response")
_MQTT_TIMEOUT_SEC = float(os.getenv("SAGE_BRAIN_CHAT_TIMEOUT_SEC", "45"))
_MQTT_CONNECT_TIMEOUT_SEC = float(os.getenv("SAGE_BRAIN_CHAT_CONNECT_TIMEOUT_SEC", "5"))


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


def _chat_via_brain_mqtt(request: ChatRequest, conversation_id: str) -> dict:
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
        "text": request.message,
        "max_history_turns": request.max_history_turns,
        "system_prompt": request.system_prompt,
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

    with _lock:
        history = list(_conversations.get(conversation_id, []))

        if request.system_prompt:
            system = ChatMessage(role="system", content=request.system_prompt)
            if history and history[0].role == "system":
                history[0] = system
            else:
                history = [system, *history]

        history.append(ChatMessage(role="user", content=request.message))
        history = _trim_history(history, request.max_history_turns)
        _conversations[conversation_id] = history
        prompt_messages = _model_input(history)

    if provider in {"brain", "sage_brain"}:
        brain_data = _chat_via_brain_mqtt(request, conversation_id)
        assistant_text = (brain_data.get("text") or "").strip()
        response_model = brain_data.get("model") or "brain_runtime"
    else:
        response_text = _llm_client.chat(
            prompt_messages,
            stream=False,
            provider=request.provider,
            model=request.model,
        )

        if isinstance(response_text, str) and response_text.strip().lower().startswith("error"):
            raise HTTPException(status_code=502, detail=response_text)

        assistant_text = response_text.strip() if isinstance(response_text, str) else str(response_text)
        if not assistant_text:
            raise HTTPException(status_code=502, detail="LLM returned an empty response")
        response_model = request.model or DEFAULT_MODEL

    with _lock:
        history = list(_conversations.get(conversation_id, []))
        history.append(ChatMessage(role="assistant", content=assistant_text))
        history = _trim_history(history, request.max_history_turns)
        _conversations[conversation_id] = history

    return ChatResponse(
        success=True,
        conversation_id=conversation_id,
        reply=assistant_text,
        provider=provider,
        model=response_model,
        message_count=len(history),
    )


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
