from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

_REQUEST_TIMEOUT_SEC = float(os.getenv("SAGE_GOOGLE_TOOL_TIMEOUT_SEC", "10"))
_AUDIT_PATH = Path(
    os.getenv("SAGE_GOOGLE_AUDIT_PATH", ".sage_memory/chat_logs/google_workspace_audit.jsonl")
).expanduser()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_audit(
    *,
    action: str,
    status: str,
    user_text: str,
    response_text: str,
    api_base_url: str,
    latency_ms: int,
    conversation_id: Optional[str],
    request_id: Optional[str],
    error: Optional[str] = None,
) -> None:
    record = {
        "ts": _now_iso(),
        "action": action,
        "status": status,
        "conversation_id": conversation_id,
        "request_id": request_id,
        "api_base_url": api_base_url,
        "latency_ms": latency_ms,
        "user_text": user_text,
        "response_text": response_text,
        "error": error,
    }
    try:
        _AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as exc:  # pragma: no cover - best effort
        print(f"[GoogleWorkspace] Failed to write audit log: {exc}")


def _normalize_api_base(api_base_url: str) -> str:
    normalized = (api_base_url or "").strip().rstrip("/")
    if not normalized:
        raise RuntimeError("SAGE_ARCHITECT_API_URL is not configured.")
    if not normalized.startswith(("http://", "https://")):
        raise RuntimeError("SAGE_ARCHITECT_API_URL must start with http:// or https://")
    return normalized


def _extract_error_text(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = None

    if isinstance(payload, dict):
        detail = payload.get("detail")
        error = payload.get("error")
        message = payload.get("message")
        for field in (detail, error, message):
            if isinstance(field, str) and field.strip():
                return field.strip()

    body = (response.text or "").strip()
    if body:
        return body[:400]
    return f"HTTP {response.status_code}"


def _request_json(
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response = requests.request(
        method=method,
        url=url,
        params=params,
        json=json_body,
        timeout=_REQUEST_TIMEOUT_SEC,
    )
    if not response.ok:
        raise RuntimeError(_extract_error_text(response))
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    raise RuntimeError("Unexpected API payload.")


def _safe_date_text(value: Optional[str]) -> str:
    raw = (value or "").strip()
    if not raw:
        return "unspecified time"
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        parsed = datetime.fromisoformat(raw)
        return parsed.strftime("%a %d %b %H:%M")
    except Exception:
        return value or "unspecified time"


def _format_calendar_events(items: List[Dict[str, Any]], max_items: int = 5) -> str:
    if not items:
        return "Your calendar looks clear for the requested window."

    lines = ["Upcoming calendar events:"]
    for index, item in enumerate(items[:max_items], start=1):
        summary = str(item.get("summary") or "Untitled event")
        start = item.get("start") or {}
        start_value = start.get("dateTime") or start.get("date")
        when = _safe_date_text(start_value)
        lines.append(f"{index}. {summary} - {when}")
    return "\n".join(lines)


def _format_task_lists(items: List[Dict[str, Any]], max_items: int = 8) -> str:
    if not items:
        return "No Google task lists were found."

    lines = ["Google task lists:"]
    for index, item in enumerate(items[:max_items], start=1):
        title = str(item.get("title") or "Untitled list")
        list_id = str(item.get("id") or "")
        lines.append(f"{index}. {title} (id: {list_id})")
    return "\n".join(lines)


def _format_tasks(items: List[Dict[str, Any]], max_items: int = 12) -> str:
    if not items:
        return "No tasks found in that list."

    lines = ["Tasks:"]
    for index, item in enumerate(items[:max_items], start=1):
        title = str(item.get("title") or "Untitled task")
        status = str(item.get("status") or "needsAction")
        marker = "done" if status.lower() == "completed" else "open"
        due = _safe_date_text(item.get("due"))
        if due == "unspecified time":
            lines.append(f"{index}. [{marker}] {title}")
        else:
            lines.append(f"{index}. [{marker}] {title} - due {due}")
    return "\n".join(lines)


def _looks_like_gmail_query(text: str) -> bool:
    if not text:
        return False
    has_topic = any(marker in text for marker in ("email", "gmail", "mail", "inbox"))
    if not has_topic:
        return False
    return any(
        marker in text
        for marker in ("show", "list", "check", "read", "send", "search", "find", "archive", "unread")
    )


def _format_gmail_messages(items: List[Dict[str, Any]], max_items: int = 5) -> str:
    if not items:
        return "No messages found."

    lines = [f"Found {len(items)} message(s):"]
    for index, item in enumerate(items[:max_items], start=1):
        msg_id = str(item.get("id") or "")
        thread_id = str(item.get("threadId") or "")
        lines.append(f"{index}. id={msg_id} (thread: {thread_id})")
    return "\n".join(lines)


def _looks_like_calendar_query(text: str) -> bool:
    if not text:
        return False
    has_topic = any(marker in text for marker in ("calendar", "schedule", "meeting", "meetings"))
    if not has_topic:
        return False
    return any(
        marker in text
        for marker in ("show", "list", "what", "upcoming", "today", "tomorrow", "next")
    )


def _looks_like_task_query(text: str) -> bool:
    if not text:
        return False
    has_topic = any(marker in text for marker in ("task", "tasks", "todo", "to-do"))
    if not has_topic:
        return False
    return any(
        marker in text
        for marker in ("show", "list", "what", "open", "pending", "today", "tomorrow", "next")
    )


def _extract_add_task_title(text: str) -> Optional[str]:
    pattern = re.compile(r"\b(?:add|create)\s+(?:a\s+)?task\s+(?:to\s+)?(.+)", re.IGNORECASE)
    match = pattern.search(text or "")
    if not match:
        return None
    title = match.group(1).strip().strip(".")
    return title or None


def _first_task_list(base_url: str) -> Dict[str, str]:
    lists_payload = _request_json("GET", f"{base_url}/google/tasks/lists")
    items = lists_payload.get("items", [])
    if not isinstance(items, list) or not items:
        raise RuntimeError("No task lists found. Create a list in Google Tasks first.")
    first = items[0] if isinstance(items[0], dict) else {}
    list_id = str(first.get("id") or "").strip()
    list_title = str(first.get("title") or "My List").strip()
    if not list_id:
        raise RuntimeError("Task list ID is missing from Google Tasks API response.")
    return {"id": list_id, "title": list_title}


def _parse_pipe_parts(text: str) -> List[str]:
    return [part.strip() for part in (text or "").split("|") if part.strip()]


def handle_google_workspace_text(
    *,
    user_text: str,
    api_base_url: str,
    conversation_id: Optional[str] = None,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    text = (user_text or "").strip()
    lowered = text.lower()
    if not text:
        return {"handled": False}

    candidate = lowered.startswith(("/google", "/calendar", "/tasks", "/gmail", "/email"))
    candidate = candidate or _looks_like_calendar_query(lowered)
    candidate = candidate or _looks_like_task_query(lowered)
    candidate = candidate or _looks_like_gmail_query(lowered)
    candidate = candidate or bool(_extract_add_task_title(text))

    if not candidate:
        return {"handled": False}

    started_at = time.perf_counter()
    action = "unknown"
    base_url = _normalize_api_base(api_base_url)

    try:
        if lowered.startswith("/google help"):
            action = "help"
            reply_text = (
                "Google commands:\n"
                "- /google status\n"
                "- /google connect\n"
                "- /google disconnect\n"
                "- /calendar list [count]\n"
                "- /calendar add title | start_iso | end_iso | timezone(optional)\n"
                "- /tasks lists\n"
                "- /tasks list <tasklist_id> [count]\n"
                "- /tasks add title | due_iso(optional) | notes(optional) | tasklist_id(optional)"
            )
        elif lowered.startswith("/google status"):
            action = "status"
            status = _request_json("GET", f"{base_url}/google/status")
            configured = bool(status.get("configured"))
            connected = bool(status.get("connected"))
            redirect_uri = status.get("redirect_uri")
            connected_at = status.get("connected_at")
            scopes = status.get("scopes") or []
            reply_text = (
                f"Google status: configured={configured}, connected={connected}."
                + (f"\nConnected at: {connected_at}" if connected_at else "")
                + (f"\nRedirect URI: {redirect_uri}" if redirect_uri else "")
                + (f"\nScopes: {', '.join(scopes)}" if scopes else "")
            )
        elif lowered.startswith("/google connect"):
            action = "auth_url"
            payload = _request_json("GET", f"{base_url}/google/auth/url")
            auth_url = str(payload.get("auth_url") or "").strip()
            if not auth_url:
                raise RuntimeError("Auth URL was empty.")
            reply_text = (
                "Open this URL to connect Google:\n"
                f"{auth_url}\n\n"
                "After approving, run `/google status`."
            )
        elif lowered.startswith("/google disconnect"):
            action = "disconnect"
            _request_json("POST", f"{base_url}/google/disconnect")
            reply_text = "Google account disconnected from Sage."
        elif lowered.startswith("/calendar add "):
            action = "calendar_create"
            parts = _parse_pipe_parts(text[len("/calendar add "):])
            if len(parts) < 3:
                raise RuntimeError(
                    "Use: /calendar add title | start_iso | end_iso | timezone(optional)"
                )
            request_body: Dict[str, Any] = {
                "summary": parts[0],
                "start": parts[1],
                "end": parts[2],
            }
            if len(parts) >= 4:
                request_body["timezone"] = parts[3]
            created = _request_json("POST", f"{base_url}/google/calendar/events", json_body=request_body)
            event = created.get("event") if isinstance(created.get("event"), dict) else {}
            summary = str(event.get("summary") or parts[0])
            start = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
            reply_text = f"Calendar event created: {summary} - {_safe_date_text(start)}"
        elif lowered.startswith("/calendar list") or _looks_like_calendar_query(lowered):
            action = "calendar_list"
            count_match = re.search(r"(\d+)$", text)
            limit = int(count_match.group(1)) if count_match else 5
            limit = max(1, min(limit, 20))
            payload = _request_json(
                "GET",
                f"{base_url}/google/calendar/events",
                params={"max_results": limit},
            )
            items = payload.get("items", [])
            if not isinstance(items, list):
                items = []
            reply_text = _format_calendar_events(items, max_items=limit)
        elif lowered.startswith("/tasks add "):
            action = "tasks_create"
            parts = _parse_pipe_parts(text[len("/tasks add "):])
            if not parts:
                raise RuntimeError(
                    "Use: /tasks add title | due_iso(optional) | notes(optional) | tasklist_id(optional)"
                )
            title = parts[0]
            due = parts[1] if len(parts) >= 2 else None
            notes = parts[2] if len(parts) >= 3 else None
            tasklist_id = parts[3] if len(parts) >= 4 else None
            if not tasklist_id:
                tasklist = _first_task_list(base_url)
                tasklist_id = tasklist["id"]
                tasklist_title = tasklist["title"]
            else:
                tasklist_title = "selected list"
            body: Dict[str, Any] = {"title": title}
            if due:
                body["due"] = due
            if notes:
                body["notes"] = notes
            created = _request_json(
                "POST",
                f"{base_url}/google/tasks/list/{tasklist_id}",
                json_body=body,
            )
            task = created.get("task") if isinstance(created.get("task"), dict) else {}
            task_title = str(task.get("title") or title)
            reply_text = f"Task added: {task_title} (list: {tasklist_title})."
        elif lowered.startswith("/tasks list "):
            action = "tasks_list"
            remainder = text[len("/tasks list "):].strip()
            if not remainder:
                raise RuntimeError("Use: /tasks list <tasklist_id> [count]")
            parts = remainder.split()
            tasklist_id = parts[0]
            limit = 12
            if len(parts) >= 2 and parts[1].isdigit():
                limit = max(1, min(int(parts[1]), 50))
            payload = _request_json(
                "GET",
                f"{base_url}/google/tasks/list/{tasklist_id}",
                params={"max_results": limit},
            )
            items = payload.get("items", [])
            if not isinstance(items, list):
                items = []
            reply_text = _format_tasks(items, max_items=limit)
        elif lowered.startswith("/tasks lists") or _looks_like_task_query(lowered):
            action = "tasks_lists"
            lists_payload = _request_json("GET", f"{base_url}/google/tasks/lists")
            items = lists_payload.get("items", [])
            if not isinstance(items, list):
                items = []
            reply_text = _format_task_lists(items)
        elif lowered.startswith(("/gmail send ", "/email send ")):
            action = "gmail_send"
            parts = _parse_pipe_parts(text.split("send ", 1)[1] if "send " in text else "")
            if len(parts) < 3:
                raise RuntimeError(
                    "Use: /gmail send to@email.com | Subject | Body"
                )
            body: Dict[str, Any] = {
                "to": parts[0],
                "subject": parts[1],
                "body": parts[2],
            }
            sent = _request_json("POST", f"{base_url}/google/gmail/send", json_body=body)
            msg_id = sent.get("message_id", "unknown")
            reply_text = f"Email sent to {parts[0]} (id: {msg_id})."
        elif lowered.startswith(("/gmail search ", "/email search ", "/gmail find ", "/email find ")):
            action = "gmail_search"
            query_text = re.split(r"\b(?:search|find)\s+", text, maxsplit=1)[-1].strip()
            payload = _request_json(
                "GET",
                f"{base_url}/google/gmail/messages",
                params={"q": query_text, "max_results": 5},
            )
            items = payload.get("messages", [])
            if not isinstance(items, list):
                items = []
            reply_text = _format_gmail_messages(items)
        elif lowered.startswith(("/gmail archive ", "/email archive ")):
            action = "gmail_archive"
            msg_id = text.split("archive ", 1)[1].strip() if "archive " in text else ""
            if not msg_id:
                raise RuntimeError("Use: /gmail archive <message_id>")
            _request_json(
                "POST",
                f"{base_url}/google/gmail/messages/{msg_id}/modify",
                json_body={"remove_labels": ["INBOX"]},
            )
            reply_text = f"Message {msg_id} archived."
        elif (
            lowered.startswith(("/gmail", "/email"))
            or _looks_like_gmail_query(lowered)
        ):
            action = "gmail_list"
            count_match = re.search(r"(\d+)$", text)
            limit = int(count_match.group(1)) if count_match else 5
            limit = max(1, min(limit, 20))
            payload = _request_json(
                "GET",
                f"{base_url}/google/gmail/messages",
                params={"max_results": limit},
            )
            items = payload.get("messages", [])
            if not isinstance(items, list):
                items = []
            reply_text = _format_gmail_messages(items, max_items=limit)
        else:
            task_title = _extract_add_task_title(text)
            if not task_title:
                return {"handled": False}
            action = "tasks_create_nl"
            tasklist = _first_task_list(base_url)
            created = _request_json(
                "POST",
                f"{base_url}/google/tasks/list/{tasklist['id']}",
                json_body={"title": task_title},
            )
            task = created.get("task") if isinstance(created.get("task"), dict) else {}
            created_title = str(task.get("title") or task_title)
            reply_text = f"Task added: {created_title} (list: {tasklist['title']})."

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        _append_audit(
            action=action,
            status="ok",
            user_text=text,
            response_text=reply_text,
            api_base_url=base_url,
            latency_ms=latency_ms,
            conversation_id=conversation_id,
            request_id=request_id,
        )
        return {
            "handled": True,
            "action": action,
            "response_text": reply_text,
            "model": "google_workspace",
            "latency_ms": latency_ms,
        }
    except Exception as exc:
        error_text = str(exc)
        if "not connected" in error_text.lower():
            error_text = (
                f"{error_text}\nRun `/google connect`, open the URL, then retry."
            )
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        _append_audit(
            action=action,
            status="error",
            user_text=text,
            response_text=error_text,
            api_base_url=base_url,
            latency_ms=latency_ms,
            conversation_id=conversation_id,
            request_id=request_id,
            error=error_text,
        )
        return {
            "handled": True,
            "action": action,
            "response_text": f"Google workspace action failed: {error_text}",
            "model": "google_workspace",
            "error": error_text,
            "latency_ms": latency_ms,
        }
