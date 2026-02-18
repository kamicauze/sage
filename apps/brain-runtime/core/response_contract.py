"""
Response normalization helpers for the voice pipeline.

These helpers enforce a stable contract between:
  - voice.handler
  - brain.main
  - action.router
"""
from typing import Any, Dict, Mapping


VOICE_TYPES = {"success", "acknowledged", "error", "none"}

VOICE_TYPE_ALIASES = {
    "suggestion": "success",
    "action_plan": "acknowledged",
    "brain_result": "success",
    "home_control_result": "success",
    "architect_result": "acknowledged",
    "failure": "error",
    "failed": "error",
}

VOICE_CORE_KEYS = {
    "type",
    "text",
    "intent",
    "route",
    "status",
    "suppressed",
    "reason",
    "data",
}


def router_result(suppressed: bool, reason: str, **extra) -> Dict[str, Any]:
    payload = {
        "suppressed": bool(suppressed),
        "reason": str(reason or "unknown"),
    }
    payload.update(extra)
    return payload


def normalize_router_result(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return router_result(False, "invalid_router_result", raw=payload)

    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        reason = "unknown"

    normalized = router_result(bool(payload.get("suppressed", False)), reason)
    for key, value in payload.items():
        if key in {"suppressed", "reason"}:
            continue
        normalized[key] = value
    return normalized


def normalize_voice_response(
    payload: Any,
    *,
    default_intent: str = "unknown",
    default_route: str = "LOCAL",
) -> Dict[str, Any]:
    """
    Normalize arbitrary response payloads to a strict voice contract.

    Contract keys:
      - type: success|acknowledged|error|none
      - text: string
      - intent: string
      - route: string
      - status: string
      - suppressed: bool
      - reason: optional string
      - data: dict (extra metadata)
    """
    if not isinstance(payload, Mapping):
        payload = {}

    raw_type = str(payload.get("type") or "").strip().lower()
    mapped_type = VOICE_TYPE_ALIASES.get(raw_type, raw_type)

    text = payload.get("text", "")
    if text is None:
        text = ""
    elif not isinstance(text, str):
        text = str(text)

    suppressed = bool(payload.get("suppressed", False))
    reason = payload.get("reason")
    if reason is not None and not isinstance(reason, str):
        reason = str(reason)

    if not mapped_type:
        mapped_type = "success" if text else "none"
    if mapped_type not in VOICE_TYPES:
        mapped_type = "success" if text else "none"

    if suppressed or mapped_type == "none":
        mapped_type = "none"
        suppressed = True
        text = ""
        if not reason:
            reason = "suppressed"

    if mapped_type == "error" and not text:
        text = "Sorry, something went wrong."

    intent = payload.get("intent")
    if not isinstance(intent, str) or not intent.strip():
        intent = default_intent

    route = payload.get("route")
    if not isinstance(route, str) or not route.strip():
        route = default_route

    status = payload.get("status", "")
    if status is None:
        status = ""
    elif not isinstance(status, str):
        status = str(status)

    normalized = {
        "type": mapped_type,
        "text": text,
        "intent": intent,
        "route": route,
        "status": status,
        "suppressed": suppressed,
        "data": {},
    }

    if reason:
        normalized["reason"] = reason

    # Preserve non-contract metadata under `data`.
    for key, value in payload.items():
        if key in VOICE_CORE_KEYS:
            continue
        normalized["data"][key] = value

    existing_data = payload.get("data")
    if isinstance(existing_data, Mapping):
        for key, value in existing_data.items():
            normalized["data"][key] = value

    return normalized
