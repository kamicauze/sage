"""
Webhook ingestion for Sage.

Allows external services (GitHub, CI/CD, IFTTT, etc.) to trigger
agent actions or brain queries via authenticated HTTP POST.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_lock = Lock()


# --- Pydantic models ---


class WebhookActionConfig(BaseModel):
    type: str = Field(..., description="start_agent, brain_query, or mqtt_publish")
    agent: Optional[str] = Field(default=None, description="Agent config name (for start_agent)")
    goal_template: Optional[str] = Field(
        default=None,
        description="Goal string with {field} placeholders filled from payload",
    )
    topic: Optional[str] = Field(default=None, description="MQTT topic (for mqtt_publish)")
    text_template: Optional[str] = Field(
        default=None,
        description="Text template for brain_query or mqtt payload",
    )


class WebhookRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Human-readable webhook name")
    source: str = Field(default="generic", description="github, gitlab, generic, etc.")
    secret: Optional[str] = Field(default=None, description="HMAC secret for signature validation")
    action: WebhookActionConfig
    enabled: bool = True


# --- Storage ---


def _resolve_store_path() -> Path:
    raw = os.getenv("SAGE_WEBHOOKS_STORE_PATH", ".sage_memory/webhooks/config.json").strip()
    base = Path(raw).expanduser()
    if not base.is_absolute():
        base = Path(os.getcwd()) / base
    return base.resolve()


_STORE_PATH = _resolve_store_path()


def _load_config() -> Dict[str, Any]:
    if not _STORE_PATH.exists():
        return {"version": 1, "hooks": []}
    try:
        payload = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    return {"version": 1, "hooks": []}


def _save_config(data: Dict[str, Any]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _STORE_PATH.parent / f"{_STORE_PATH.name}.tmp"
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(_STORE_PATH)


def _find_hook(hook_id: str) -> Optional[Dict[str, Any]]:
    config = _load_config()
    for hook in config.get("hooks", []):
        if hook.get("id") == hook_id:
            return hook
    return None


# --- Signature validation ---


def _validate_signature(hook: Dict[str, Any], headers: Dict[str, str], body: bytes) -> bool:
    """Validate webhook signature. Returns True if valid or no secret configured."""
    secret = (hook.get("secret") or "").strip()
    if not secret:
        return True

    source = hook.get("source", "generic")

    if source == "github":
        sig_header = headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig_header, expected)

    if source == "gitlab":
        token_header = headers.get("x-gitlab-token", "")
        return hmac.compare_digest(token_header, secret)

    # Generic: check X-Webhook-Signature header
    sig_header = headers.get("x-webhook-signature", "")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sig_header, expected)


# --- Dispatch ---


def _render_template(template: str, payload: Dict[str, Any]) -> str:
    """Render a template string with payload fields. Missing keys left as-is."""
    result = template
    for key, value in payload.items():
        if isinstance(value, str):
            result = result.replace(f"{{{key}}}", value)
    return result


def _dispatch_action(action: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the webhook action. Returns result dict."""
    action_type = action.get("type", "")

    if action_type == "start_agent":
        agent_name = action.get("agent", "")
        goal_template = action.get("goal_template", "Webhook triggered task")
        goal = _render_template(goal_template, payload)
        # We can't start async agents from sync context, so publish via MQTT
        try:
            import paho.mqtt.publish as mqtt_publish
            mqtt_publish.single(
                "sage/agent/webhook/start",
                payload=json.dumps({"agent": agent_name, "goal": goal}),
                hostname=os.getenv("MQTT_HOST", "localhost"),
                port=int(os.getenv("MQTT_PORT", "1883")),
            )
            return {"dispatched": True, "agent": agent_name, "goal": goal}
        except Exception as exc:
            return {"dispatched": False, "error": str(exc)}

    elif action_type == "brain_query":
        text_template = action.get("text_template", "Webhook event: {event}")
        text = _render_template(text_template, payload)
        try:
            import paho.mqtt.publish as mqtt_publish
            mqtt_publish.single(
                os.getenv("SAGE_BRAIN_CHAT_REQUEST_TOPIC", "sage/brain/chat/request"),
                payload=json.dumps({"text": text, "source": "webhook"}),
                hostname=os.getenv("MQTT_HOST", "localhost"),
                port=int(os.getenv("MQTT_PORT", "1883")),
            )
            return {"dispatched": True, "text": text}
        except Exception as exc:
            return {"dispatched": False, "error": str(exc)}

    elif action_type == "mqtt_publish":
        topic = action.get("topic", "sage/webhook/event")
        try:
            import paho.mqtt.publish as mqtt_publish
            mqtt_publish.single(
                topic,
                payload=json.dumps(payload),
                hostname=os.getenv("MQTT_HOST", "localhost"),
                port=int(os.getenv("MQTT_PORT", "1883")),
            )
            return {"dispatched": True, "topic": topic}
        except Exception as exc:
            return {"dispatched": False, "error": str(exc)}

    return {"dispatched": False, "error": f"Unknown action type: {action_type}"}


# --- Audit ---


_AUDIT_PATH = Path(
    os.getenv("SAGE_WEBHOOKS_AUDIT_PATH", ".sage_memory/chat_logs/webhooks_audit.jsonl")
).expanduser()


def _append_audit(hook_id: str, action: str, status: str, payload_preview: str) -> None:
    record = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hook_id": hook_id,
        "action": action,
        "status": status,
        "payload_preview": payload_preview[:400],
    }
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


# --- Endpoints ---


@router.post("/register")
def register_webhook(request: WebhookRegisterRequest) -> Dict[str, Any]:
    """Register a new webhook endpoint."""
    hook_id = f"wh_{uuid4().hex[:12]}"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    hook = {
        "id": hook_id,
        "name": request.name,
        "source": request.source,
        "secret": request.secret,
        "action": request.action.model_dump(),
        "enabled": request.enabled,
        "created_at": now,
        "last_triggered": None,
        "trigger_count": 0,
    }

    with _lock:
        config = _load_config()
        config["hooks"].append(hook)
        _save_config(config)

    return {
        "success": True,
        "id": hook_id,
        "url": f"/webhooks/trigger/{hook_id}",
    }


@router.get("/")
def list_webhooks() -> Dict[str, Any]:
    """List all registered webhooks."""
    with _lock:
        config = _load_config()
    hooks = config.get("hooks", [])
    # Strip secrets from response
    safe_hooks = []
    for h in hooks:
        safe = {k: v for k, v in h.items() if k != "secret"}
        safe["has_secret"] = bool((h.get("secret") or "").strip())
        safe_hooks.append(safe)
    return {"success": True, "count": len(safe_hooks), "hooks": safe_hooks}


@router.delete("/{hook_id}")
def delete_webhook(hook_id: str) -> Dict[str, Any]:
    """Delete a registered webhook."""
    with _lock:
        config = _load_config()
        before = len(config.get("hooks", []))
        config["hooks"] = [h for h in config.get("hooks", []) if h.get("id") != hook_id]
        if len(config["hooks"]) == before:
            raise HTTPException(status_code=404, detail=f"Webhook {hook_id} not found.")
        _save_config(config)
    return {"success": True, "deleted": hook_id}


@router.post("/trigger/{hook_id}")
async def trigger_webhook(hook_id: str, request: Request) -> Dict[str, Any]:
    """Receive an external webhook trigger."""
    body = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    with _lock:
        hook = _find_hook(hook_id)
    if not hook:
        raise HTTPException(status_code=404, detail=f"Webhook {hook_id} not found.")

    if not hook.get("enabled", True):
        raise HTTPException(status_code=403, detail="Webhook is disabled.")

    # Validate signature
    if not _validate_signature(hook, headers, body):
        _append_audit(hook_id, "trigger", "invalid_signature", body.decode("utf-8", errors="replace"))
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    # Parse payload
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        payload = {"raw": body.decode("utf-8", errors="replace")}

    # Dispatch action
    action = hook.get("action", {})
    result = _dispatch_action(action, payload)

    # Update trigger stats
    with _lock:
        config = _load_config()
        for h in config.get("hooks", []):
            if h.get("id") == hook_id:
                h["trigger_count"] = h.get("trigger_count", 0) + 1
                h["last_triggered"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                break
        _save_config(config)

    _append_audit(hook_id, action.get("type", "unknown"), "ok", json.dumps(payload)[:400])

    return {
        "accepted": True,
        "hook_id": hook_id,
        "action_type": action.get("type"),
        "result": result,
    }
