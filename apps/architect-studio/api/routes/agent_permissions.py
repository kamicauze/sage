"""
Agent Permissions API — runtime management of agent tool policies.

Provides CRUD for the AgentToolPolicy, preset profiles (safe/standard/power),
and an append-only audit trail of policy changes.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

# Ensure shared packages are importable
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.agent.tools import Tool

router = APIRouter(prefix="/agent/permissions", tags=["agent-permissions"])

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Storage paths
# ---------------------------------------------------------------------------

_POLICY_PATH = Path(
    os.getenv("SAGE_AGENT_TOOL_POLICY_PATH", ".sage_memory/agent_policy.json").strip()
).expanduser()

_AUDIT_PATH = _POLICY_PATH.parent / "agent_policy_audit.json"

# ---------------------------------------------------------------------------
# Canonical tool catalogue (name → description + built-in approval default)
# ---------------------------------------------------------------------------

_TOOL_CATALOGUE: List[Dict[str, Any]] = [
    {"name": "read_file", "description": "Read file contents (5 000 char limit)", "needs_approval": False},
    {"name": "write_file", "description": "Write content to a file", "needs_approval": True},
    {"name": "run_tests", "description": "Run a test suite", "needs_approval": False},
    {"name": "call_llm", "description": "Query an LLM for reasoning", "needs_approval": False},
    {"name": "ask_user", "description": "Ask the user a question via voice", "needs_approval": False},
    {"name": "report_status", "description": "Speak a status update", "needs_approval": False},
    {"name": "architect_plan", "description": "Create an implementation plan", "needs_approval": False},
    {"name": "architect_build", "description": "Build code from a plan", "needs_approval": True},
    {"name": "web_search", "description": "Search the web for information", "needs_approval": False},
    {"name": "gmail_read", "description": "Search and read Gmail messages", "needs_approval": False},
    {"name": "gmail_send", "description": "Send an email via Gmail", "needs_approval": True},
    {"name": "gmail_archive", "description": "Archive a Gmail message", "needs_approval": True},
    {"name": "browser_navigate", "description": "Navigate to a URL in headless browser", "needs_approval": True},
    {"name": "browser_click", "description": "Click an element in the browser", "needs_approval": True},
    {"name": "browser_extract", "description": "Extract text from browser page", "needs_approval": False},
    {"name": "browser_screenshot", "description": "Take a screenshot of browser page", "needs_approval": False},
    {"name": "deploy", "description": "Deploy a project to production", "needs_approval": True},
    {"name": "write_agent_config", "description": "Create a new agent YAML config", "needs_approval": True},
    {"name": "register_agent", "description": "Load an agent config into registry", "needs_approval": False},
]

# ---------------------------------------------------------------------------
# Profile presets
# ---------------------------------------------------------------------------

_PROFILES: Dict[str, Dict[str, Any]] = {
    "safe": {
        "name": "safe",
        "label": "Safe",
        "description": "Read-only focus. Browser and deploy blocked. All writes need approval.",
        "mode": "safe",
        "deny_tools": ["deploy", "browser_navigate", "browser_click"],
        "force_approval_tools": [
            "write_file", "architect_build", "write_agent_config",
            "register_agent", "gmail_send", "gmail_archive",
        ],
        "allow_write_roots": ["apps", "tests"],
    },
    "standard": {
        "name": "standard",
        "label": "Standard",
        "description": "Balanced defaults. Writes and deploys need approval.",
        "mode": "safe",
        "deny_tools": [],
        "force_approval_tools": [
            "write_file", "deploy", "architect_build",
            "write_agent_config", "register_agent",
        ],
        "allow_write_roots": ["apps", "packages", "tests", "docs", "agents"],
    },
    "power": {
        "name": "power",
        "label": "Power",
        "description": "Most tools auto-approved. Only deploy requires approval.",
        "mode": "power",
        "deny_tools": [],
        "force_approval_tools": ["deploy"],
        "allow_write_roots": ["apps", "packages", "tests", "docs", "agents", "generated"],
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_policy() -> Dict[str, Any]:
    """Load current policy from disk, or return defaults matching 'standard'."""
    with _lock:
        if _POLICY_PATH.exists():
            try:
                data = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return {
        "mode": "safe",
        "deny_tools": [],
        "force_approval_tools": [
            "write_file", "deploy", "architect_build",
            "write_agent_config", "register_agent",
        ],
        "allow_write_roots": ["apps", "packages", "tests", "docs", "agents"],
    }


def _save_policy(data: Dict[str, Any]) -> None:
    with _lock:
        _POLICY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _POLICY_PATH.parent / f"{_POLICY_PATH.name}.tmp"
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(_POLICY_PATH)


def _append_audit(action: str, changes: Dict[str, Any], source: str = "api") -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": action,
        "changes": changes,
        "source": source,
    }
    with _lock:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        entries: list = []
        if _AUDIT_PATH.exists():
            try:
                entries = json.loads(_AUDIT_PATH.read_text(encoding="utf-8"))
                if not isinstance(entries, list):
                    entries = []
            except Exception:
                entries = []
        entries.append(entry)
        # Keep last 200 entries
        entries = entries[-200:]
        _AUDIT_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _detect_active_profile(policy: Dict[str, Any]) -> Optional[str]:
    """Return the profile name if current policy exactly matches a preset."""
    deny = set(policy.get("deny_tools", []))
    approval = set(policy.get("force_approval_tools", []))
    roots = set(policy.get("allow_write_roots", []))
    mode = policy.get("mode", "safe")

    for name, profile in _PROFILES.items():
        if (
            mode == profile["mode"]
            and deny == set(profile["deny_tools"])
            and approval == set(profile["force_approval_tools"])
            and roots == set(profile["allow_write_roots"])
        ):
            return name
    return None


def _build_tool_list(policy: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Enrich the tool catalogue with current policy state."""
    deny = set(policy.get("deny_tools", []))
    approval = set(policy.get("force_approval_tools", []))

    tools = []
    for t in _TOOL_CATALOGUE:
        tools.append({
            "name": t["name"],
            "description": t["description"],
            "needs_approval": t["needs_approval"],
            "denied": t["name"] in deny,
            "force_approval": t["name"] in approval,
        })
    return tools


def _publish_mqtt_update() -> None:
    """Best-effort MQTT notification for brain to reload policy."""
    try:
        import paho.mqtt.publish as publish
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", "1883"))
        publish.single(
            "sage/agent/policy/updated",
            payload=json.dumps({"timestamp": time.time()}),
            hostname=host,
            port=port,
        )
    except Exception:
        pass  # MQTT is best-effort; API still succeeds


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------


class PermissionsUpdateRequest(BaseModel):
    mode: Optional[str] = Field(default=None, min_length=1, max_length=20)
    deny_tools: Optional[List[str]] = None
    force_approval_tools: Optional[List[str]] = None
    allow_write_roots: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/")
def get_permissions() -> Dict[str, Any]:
    """Return current agent permission policy with tool catalogue."""
    policy = _load_policy()
    active_profile = _detect_active_profile(policy)
    tools = _build_tool_list(policy)
    return {
        "success": True,
        "mode": policy.get("mode", "safe"),
        "active_profile": active_profile,
        "deny_tools": sorted(policy.get("deny_tools", [])),
        "force_approval_tools": sorted(policy.get("force_approval_tools", [])),
        "allow_write_roots": sorted(policy.get("allow_write_roots", [])),
        "tools": tools,
    }


@router.put("/")
def update_permissions(req: PermissionsUpdateRequest) -> Dict[str, Any]:
    """Partially update the agent permission policy."""
    policy = _load_policy()
    changes: Dict[str, Any] = {}

    if req.mode is not None:
        changes["mode"] = req.mode
        policy["mode"] = req.mode
    if req.deny_tools is not None:
        changes["deny_tools"] = req.deny_tools
        policy["deny_tools"] = req.deny_tools
    if req.force_approval_tools is not None:
        changes["force_approval_tools"] = req.force_approval_tools
        policy["force_approval_tools"] = req.force_approval_tools
    if req.allow_write_roots is not None:
        changes["allow_write_roots"] = req.allow_write_roots
        policy["allow_write_roots"] = req.allow_write_roots

    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update.")

    _save_policy(policy)
    _append_audit("update", changes, source="mobile")
    _publish_mqtt_update()

    active_profile = _detect_active_profile(policy)
    tools = _build_tool_list(policy)
    return {
        "success": True,
        "mode": policy.get("mode", "safe"),
        "active_profile": active_profile,
        "deny_tools": sorted(policy.get("deny_tools", [])),
        "force_approval_tools": sorted(policy.get("force_approval_tools", [])),
        "allow_write_roots": sorted(policy.get("allow_write_roots", [])),
        "tools": tools,
    }


@router.get("/profiles")
def list_profiles() -> Dict[str, Any]:
    """Return the 3 preset permission profiles."""
    return {
        "success": True,
        "profiles": [_PROFILES[name] for name in ("safe", "standard", "power")],
    }


@router.put("/profile/{profile_name}")
def apply_profile(profile_name: str) -> Dict[str, Any]:
    """Apply a named permission profile wholesale."""
    profile = _PROFILES.get(profile_name.lower())
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown profile '{profile_name}'. Available: {', '.join(_PROFILES)}",
        )

    policy = {
        "mode": profile["mode"],
        "deny_tools": list(profile["deny_tools"]),
        "force_approval_tools": list(profile["force_approval_tools"]),
        "allow_write_roots": list(profile["allow_write_roots"]),
    }
    _save_policy(policy)
    _append_audit("apply_profile", {"profile": profile_name}, source="mobile")
    _publish_mqtt_update()

    tools = _build_tool_list(policy)
    return {
        "success": True,
        "mode": policy["mode"],
        "active_profile": profile_name,
        "deny_tools": sorted(policy["deny_tools"]),
        "force_approval_tools": sorted(policy["force_approval_tools"]),
        "allow_write_roots": sorted(policy["allow_write_roots"]),
        "tools": tools,
    }


@router.get("/audit")
def get_audit(
    limit: int = Query(default=20, ge=1, le=200),
) -> Dict[str, Any]:
    """Return recent permission change audit entries."""
    with _lock:
        if not _AUDIT_PATH.exists():
            return {"success": True, "entries": []}
        try:
            entries = json.loads(_AUDIT_PATH.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                entries = []
        except Exception:
            entries = []

    # Return most recent first
    entries = list(reversed(entries[-limit:]))
    return {"success": True, "entries": entries}
