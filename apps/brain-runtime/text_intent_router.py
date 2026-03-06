from __future__ import annotations

import re
from typing import Optional, Tuple

_COMMAND_PREFIXES = (
    ("/architect-build", "architect_task"),
    ("/architect-plan", "architect_task"),
    ("/architect", "architect_task"),
    ("/agent", "agent_task"),
    ("/home", "home_control"),
    ("/smalltalk", "smalltalk"),
    ("/brain", "brain_query"),
)

_CALENDAR_MARKERS = {
    "calendar",
    "meeting",
    "event",
    "reminder",
    "schedule",
    "appointment",
}

_ACTION_WORDS = {
    "add",
    "create",
    "build",
    "implement",
    "fix",
    "debug",
    "refactor",
    "update",
    "change",
    "edit",
    "remove",
    "delete",
    "adjust",
}

_DEV_TARGET_WORDS = {
    "app",
    "mobile",
    "ui",
    "screen",
    "input",
    "padding",
    "frontend",
    "component",
    "code",
    "repo",
    "project",
    "feature",
    "bug",
    "file",
    "files",
    "path",
    "paths",
    "api",
    "endpoint",
}

_DEV_PHRASES = {
    "sage mobile",
    "mobile app",
    "real file edits",
    "apply to repo",
}


def parse_text_intent_command(text: str) -> Tuple[Optional[str], str]:
    """
    Support explicit text command prefixes for deterministic routing.
    Returns (forced_intent_type, stripped_query).
    """
    cleaned = str(text or "").strip()
    lowered = cleaned.lower()

    for prefix, forced_type in _COMMAND_PREFIXES:
        if lowered == prefix:
            return forced_type, ""
        if lowered.startswith(prefix + " "):
            return forced_type, cleaned[len(prefix):].strip()

    return None, cleaned


def looks_like_architect_text_request(text: str) -> bool:
    """
    Text-chat override for software/editing requests.
    Keeps voice intent behavior unchanged while reducing false positives.
    """
    lowered = str(text or "").lower().strip()
    if not lowered:
        return False

    words = set(re.findall(r"[a-z0-9_]+", lowered))
    if words & _CALENDAR_MARKERS:
        return False

    has_action = bool(words & _ACTION_WORDS)
    has_dev_target = bool(words & _DEV_TARGET_WORDS) or any(
        phrase in lowered for phrase in _DEV_PHRASES
    )
    mentions_architect = "architect" in words or "/architect" in lowered

    return (mentions_architect and has_action) or (has_action and has_dev_target)
