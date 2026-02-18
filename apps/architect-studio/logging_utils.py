"""
Structured logging helpers for Architect services.
"""
from __future__ import annotations

import contextlib
import contextvars
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

_LOGGER = logging.getLogger("architect")
_LOGGING_CONFIGURED = False
_CORRELATION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "architect_correlation_id",
    default=None,
)


def configure_logging() -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    level_name = os.getenv("SAGE_ARCHITECT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    _LOGGER.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    _LOGGER.addHandler(handler)
    _LOGGER.setLevel(level)
    _LOGGER.propagate = False

    _LOGGING_CONFIGURED = True


def generate_correlation_id(prefix: str = "req") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def get_correlation_id() -> str | None:
    return _CORRELATION_ID.get()


@contextlib.contextmanager
def correlation_context(correlation_id: str | None) -> Iterator[None]:
    if not correlation_id:
        yield
        return
    token = _CORRELATION_ID.set(correlation_id)
    try:
        yield
    finally:
        _CORRELATION_ID.reset(token)


def _coerce_json(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, dict)):
        return value
    return str(value)


def log_event(
    component: str,
    event: str,
    *,
    level: str = "info",
    correlation_id: str | None = None,
    **fields: Any,
) -> None:
    configure_logging()

    payload: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level.upper(),
        "component": component,
        "event": event,
    }

    cid = correlation_id or get_correlation_id()
    if cid:
        payload["correlation_id"] = cid

    for key, value in fields.items():
        payload[key] = _coerce_json(value)

    line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    log_func = getattr(_LOGGER, level.lower(), _LOGGER.info)
    log_func(line)
