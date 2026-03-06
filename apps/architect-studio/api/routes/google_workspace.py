"""
Google Workspace integration for Sage.

Implements OAuth (authorization code flow) and basic Calendar/Tasks endpoints.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlencode
from uuid import uuid4

import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from shared.project_control import upsert_project_google_asset

router = APIRouter(prefix="/google", tags=["google"])

_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"
_TASKS_BASE = "https://tasks.googleapis.com/tasks/v1"
_DRIVE_BASE = "https://www.googleapis.com/drive/v3"
_REQUEST_TIMEOUT_SEC = float(os.getenv("SAGE_GOOGLE_REQUEST_TIMEOUT_SEC", "10.0"))
_STATE_TTL_SEC = int(os.getenv("SAGE_GOOGLE_STATE_TTL_SEC", "900"))
_SCOPES = (
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
)
_GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1"
_DRIVE_FILE_FIELDS = ",".join(
    [
        "id",
        "name",
        "mimeType",
        "webViewLink",
        "modifiedTime",
        "iconLink",
        "size",
        "parents",
        "owners(displayName,emailAddress)",
    ]
)
_GOOGLE_EXPORT_MIME_TYPES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

_lock = Lock()
_oauth_states: Dict[str, float] = {}


class GoogleAuthUrlResponse(BaseModel):
    auth_url: str
    state: str
    scopes: List[str]


class GoogleStatusResponse(BaseModel):
    configured: bool
    connected: bool
    redirect_uri: Optional[str] = None
    connected_at: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)


class CalendarCreateEventRequest(BaseModel):
    summary: str = Field(..., min_length=1)
    start: str = Field(..., description="ISO datetime, e.g. 2026-02-25T15:00:00+03:00")
    end: str = Field(..., description="ISO datetime, e.g. 2026-02-25T15:30:00+03:00")
    timezone: Optional[str] = Field(default=None, description="IANA timezone, e.g. Africa/Nairobi")
    description: Optional[str] = None
    location: Optional[str] = None


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    notes: Optional[str] = None
    due: Optional[str] = Field(default=None, description="ISO datetime for due date")


class GmailSendRequest(BaseModel):
    to: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    body: str
    cc: Optional[str] = None
    bcc: Optional[str] = None


class GmailModifyRequest(BaseModel):
    add_labels: Optional[List[str]] = None
    remove_labels: Optional[List[str]] = None


class DriveLinkProjectRequest(BaseModel):
    project_id: str = Field(..., min_length=1, max_length=120)
    drive_url: Optional[str] = Field(default=None, max_length=2000)
    file_id: Optional[str] = Field(default=None, max_length=255)
    role: Optional[str] = Field(default=None, max_length=120)


def _resolve_store_path() -> Path:
    raw_path = os.getenv("SAGE_GOOGLE_OAUTH_STORE_PATH", ".sage_memory/google/oauth_tokens.json").strip()
    base = Path(raw_path).expanduser()
    if not base.is_absolute():
        base = Path(os.getcwd()) / base
    return base.resolve()


_STORE_PATH = _resolve_store_path()


def _load_store_locked() -> Dict[str, Any]:
    if not _STORE_PATH.exists():
        return {}
    try:
        payload = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _save_store_locked(data: Dict[str, Any]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _STORE_PATH.parent / f"{_STORE_PATH.name}.tmp"
    tmp_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(_STORE_PATH)


def _clear_store_locked() -> None:
    if _STORE_PATH.exists():
        _STORE_PATH.unlink()


def _google_config() -> Dict[str, str]:
    client_id = (os.getenv("SAGE_GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("SAGE_GOOGLE_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("SAGE_GOOGLE_REDIRECT_URI") or "").strip()

    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(
            status_code=400,
            detail=(
                "Google OAuth is not configured. Set SAGE_GOOGLE_CLIENT_ID, "
                "SAGE_GOOGLE_CLIENT_SECRET, and SAGE_GOOGLE_REDIRECT_URI."
            ),
        )
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
    }


def _prune_states(now_ts: float) -> None:
    expired = [state for state, expires_at in _oauth_states.items() if expires_at <= now_ts]
    for state in expired:
        _oauth_states.pop(state, None)


def _issue_state() -> str:
    now_ts = time.time()
    with _lock:
        _prune_states(now_ts)
        state = uuid4().hex
        _oauth_states[state] = now_ts + _STATE_TTL_SEC
        return state


def _consume_state(state: str) -> bool:
    now_ts = time.time()
    with _lock:
        _prune_states(now_ts)
        expires_at = _oauth_states.pop(state, None)
        return bool(expires_at and expires_at > now_ts)


def _extract_error_text(response: requests.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        payload = None

    if isinstance(payload, dict):
        err = payload.get("error")
        if isinstance(err, dict):
            message = err.get("message")
            if isinstance(message, str) and message.strip():
                return message.strip()
        if isinstance(err, str) and err.strip():
            description = payload.get("error_description")
            if isinstance(description, str) and description.strip():
                return f"{err.strip()}: {description.strip()}"
            return err.strip()

    body = response.text.strip()
    if body:
        return body[:400]
    return f"HTTP {response.status_code}"


def _store_connected_token_payload_locked(
    payload: Dict[str, Any], *, preserve_refresh: Optional[str] = None
) -> None:
    now_ts = int(time.time())
    expires_in = int(payload.get("expires_in") or 0)
    refresh_token = (payload.get("refresh_token") or preserve_refresh or "").strip() or None

    record = _load_store_locked()
    record.update(
        {
            "access_token": payload.get("access_token"),
            "refresh_token": refresh_token,
            "token_type": payload.get("token_type", "Bearer"),
            "scope": payload.get("scope", " ".join(_SCOPES)),
            "expires_at": now_ts + max(0, expires_in),
            "connected_at": record.get("connected_at") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
        }
    )
    _save_store_locked(record)


def _refresh_access_token_locked(config: Dict[str, str], record: Dict[str, Any]) -> Dict[str, Any]:
    refresh_token = (record.get("refresh_token") or "").strip()
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Google account not connected (missing refresh token).")

    response = requests.post(
        _TOKEN_ENDPOINT,
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=_REQUEST_TIMEOUT_SEC,
    )
    if not response.ok:
        raise HTTPException(status_code=401, detail=f"Google token refresh failed: {_extract_error_text(response)}")

    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise HTTPException(status_code=401, detail="Google token refresh response missing access_token.")

    _store_connected_token_payload_locked(payload, preserve_refresh=refresh_token)
    return _load_store_locked()


def _get_valid_access_token(config: Dict[str, str]) -> str:
    with _lock:
        record = _load_store_locked()
        access_token = (record.get("access_token") or "").strip()
        expires_at = int(record.get("expires_at") or 0)
        now_ts = int(time.time())

        if access_token and expires_at > now_ts + 30:
            return access_token

        refreshed = _refresh_access_token_locked(config, record)
        access_token = (refreshed.get("access_token") or "").strip()
        if not access_token:
            raise HTTPException(status_code=401, detail="Google account not connected.")
        return access_token


def _google_request(
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response = _google_request_response(method, url, params=params, json_body=json_body)
    payload = response.json()
    if isinstance(payload, dict):
        return payload
    raise HTTPException(status_code=502, detail="Unexpected Google API response payload.")


def _google_request_response(
    method: str,
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Dict[str, Any]] = None,
) -> requests.Response:
    config = _google_config()
    token = _get_valid_access_token(config)
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.request(
        method,
        url,
        params=params,
        json=json_body,
        headers=headers,
        timeout=_REQUEST_TIMEOUT_SEC,
    )

    if response.status_code == 401:
        with _lock:
            refreshed = _refresh_access_token_locked(config, _load_store_locked())
            token = (refreshed.get("access_token") or "").strip()
        headers["Authorization"] = f"Bearer {token}"
        response = requests.request(
            method,
            url,
            params=params,
            json=json_body,
            headers=headers,
            timeout=_REQUEST_TIMEOUT_SEC,
        )

    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Google API request failed: {_extract_error_text(response)}",
        )

    return response


def _derive_drive_kind(mime_type: str) -> str:
    clean = (mime_type or "").strip()
    if clean == "application/vnd.google-apps.folder":
        return "folder"
    if clean == "application/vnd.google-apps.document":
        return "doc"
    if clean == "application/vnd.google-apps.spreadsheet":
        return "sheet"
    if clean == "application/vnd.google-apps.presentation":
        return "slides"
    if clean == "application/pdf":
        return "pdf"
    return "file"


def _format_drive_file_metadata(payload: Dict[str, Any]) -> Dict[str, Any]:
    owners = []
    for owner in payload.get("owners") or []:
        if isinstance(owner, dict):
            owners.append(
                {
                    "display_name": owner.get("displayName"),
                    "email": owner.get("emailAddress"),
                }
            )
    mime_type = str(payload.get("mimeType") or "")
    return {
        "asset_id": str(payload.get("id") or ""),
        "title": str(payload.get("name") or "Untitled"),
        "mime_type": mime_type,
        "kind": _derive_drive_kind(mime_type),
        "url": str(payload.get("webViewLink") or ""),
        "modified_time": payload.get("modifiedTime"),
        "icon_url": payload.get("iconLink"),
        "size": payload.get("size"),
        "parents": payload.get("parents") if isinstance(payload.get("parents"), list) else [],
        "owners": owners,
    }


def extract_google_drive_file_id(value: str) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    if re.fullmatch(r"[-\w]{20,}", text):
        return text
    for pattern in (
        r"/d/([-\w]{20,})",
        r"/folders/([-\w]{20,})",
        r"[?&]id=([-\w]{20,})",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def get_drive_file_metadata(file_id: str) -> Dict[str, Any]:
    encoded = quote(file_id, safe="")
    payload = _google_request(
        "GET",
        f"{_DRIVE_BASE}/files/{encoded}",
        params={"fields": _DRIVE_FILE_FIELDS},
    )
    return _format_drive_file_metadata(payload)


def _drive_text_content(file_id: str, mime_type: str) -> Dict[str, Any]:
    encoded = quote(file_id, safe="")
    export_mime = _GOOGLE_EXPORT_MIME_TYPES.get(mime_type)
    if export_mime:
        response = _google_request_response(
            "GET",
            f"https://www.googleapis.com/drive/v3/files/{encoded}/export",
            params={"mimeType": export_mime},
        )
        return {
            "content": response.text,
            "content_type": response.headers.get("content-type", export_mime),
            "content_available": True,
        }

    if mime_type.startswith("text/") or mime_type in {
        "application/json",
        "application/ld+json",
        "application/xml",
        "application/x-yaml",
        "application/yaml",
        "application/csv",
    }:
        response = _google_request_response(
            "GET",
            f"{_DRIVE_BASE}/files/{encoded}",
            params={"alt": "media"},
        )
        return {
            "content": response.text,
            "content_type": response.headers.get("content-type", mime_type),
            "content_available": True,
        }

    return {
        "content": "",
        "content_type": mime_type,
        "content_available": False,
    }


@router.get("/auth/url", response_model=GoogleAuthUrlResponse)
def get_auth_url() -> GoogleAuthUrlResponse:
    config = _google_config()
    state = _issue_state()
    params = {
        "client_id": config["client_id"],
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": " ".join(_SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return GoogleAuthUrlResponse(
        auth_url=f"{_AUTH_ENDPOINT}?{urlencode(params)}",
        state=state,
        scopes=list(_SCOPES),
    )


@router.get("/auth/callback", response_class=HTMLResponse)
def auth_callback(
    code: str = Query(..., min_length=1),
    state: str = Query(..., min_length=1),
) -> HTMLResponse:
    if not _consume_state(state):
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    config = _google_config()
    response = requests.post(
        _TOKEN_ENDPOINT,
        data={
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": config["redirect_uri"],
        },
        timeout=_REQUEST_TIMEOUT_SEC,
    )
    if not response.ok:
        raise HTTPException(status_code=400, detail=f"Google OAuth exchange failed: {_extract_error_text(response)}")

    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise HTTPException(status_code=400, detail="Google OAuth exchange response missing access_token.")

    with _lock:
        previous = _load_store_locked()
        preserve_refresh = (previous.get("refresh_token") or "").strip() or None
        _store_connected_token_payload_locked(payload, preserve_refresh=preserve_refresh)

    return HTMLResponse(
        content=(
            "<html><body style='font-family: -apple-system, sans-serif; padding: 24px;'>"
            "<h2>Google connected to Sage</h2>"
            "<p>You can close this tab and return to Sage.</p>"
            "</body></html>"
        ),
        status_code=200,
    )


@router.get("/status", response_model=GoogleStatusResponse)
def get_status() -> GoogleStatusResponse:
    client_id = (os.getenv("SAGE_GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("SAGE_GOOGLE_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("SAGE_GOOGLE_REDIRECT_URI") or "").strip()
    configured = bool(client_id and client_secret and redirect_uri)

    with _lock:
        record = _load_store_locked()
    connected = bool((record.get("refresh_token") or "").strip() or (record.get("access_token") or "").strip())
    raw_scope = (record.get("scope") or "").strip()

    return GoogleStatusResponse(
        configured=configured,
        connected=connected,
        redirect_uri=redirect_uri or None,
        connected_at=record.get("connected_at"),
        scopes=[part for part in raw_scope.split() if part],
    )


@router.post("/disconnect")
def disconnect() -> Dict[str, Any]:
    with _lock:
        _clear_store_locked()
    return {"success": True}


@router.get("/calendar/events")
def list_calendar_events(
    max_results: int = Query(default=10, ge=1, le=50),
    time_min: Optional[str] = Query(default=None, description="Optional ISO lower bound"),
) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": max_results,
    }
    if time_min:
        params["timeMin"] = time_min
    else:
        params["timeMin"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    payload = _google_request(
        "GET",
        f"{_CALENDAR_BASE}/calendars/primary/events",
        params=params,
    )
    items = payload.get("items", [])
    return {
        "success": True,
        "count": len(items) if isinstance(items, list) else 0,
        "items": items if isinstance(items, list) else [],
    }


@router.post("/calendar/events")
def create_calendar_event(request: CalendarCreateEventRequest) -> Dict[str, Any]:
    event_payload: Dict[str, Any] = {
        "summary": request.summary.strip(),
        "start": {"dateTime": request.start},
        "end": {"dateTime": request.end},
    }
    if request.timezone:
        event_payload["start"]["timeZone"] = request.timezone
        event_payload["end"]["timeZone"] = request.timezone
    if request.description:
        event_payload["description"] = request.description
    if request.location:
        event_payload["location"] = request.location

    payload = _google_request(
        "POST",
        f"{_CALENDAR_BASE}/calendars/primary/events",
        json_body=event_payload,
    )
    return {"success": True, "event": payload}


@router.get("/tasks/lists")
def list_task_lists() -> Dict[str, Any]:
    payload = _google_request("GET", f"{_TASKS_BASE}/users/@me/lists")
    items = payload.get("items", [])
    return {
        "success": True,
        "count": len(items) if isinstance(items, list) else 0,
        "items": items if isinstance(items, list) else [],
    }


@router.get("/tasks/list/{tasklist_id}")
def list_tasks(tasklist_id: str, max_results: int = Query(default=50, ge=1, le=100)) -> Dict[str, Any]:
    encoded = quote(tasklist_id, safe="")
    payload = _google_request(
        "GET",
        f"{_TASKS_BASE}/lists/{encoded}/tasks",
        params={"maxResults": max_results},
    )
    items = payload.get("items", [])
    return {
        "success": True,
        "count": len(items) if isinstance(items, list) else 0,
        "items": items if isinstance(items, list) else [],
    }


@router.post("/tasks/list/{tasklist_id}")
def create_task(tasklist_id: str, request: TaskCreateRequest) -> Dict[str, Any]:
    encoded = quote(tasklist_id, safe="")
    task_payload: Dict[str, Any] = {"title": request.title.strip()}
    if request.notes:
        task_payload["notes"] = request.notes
    if request.due:
        task_payload["due"] = request.due

    payload = _google_request(
        "POST",
        f"{_TASKS_BASE}/lists/{encoded}/tasks",
        json_body=task_payload,
    )
    return {"success": True, "task": payload}


# --- Google Drive ---


@router.get("/drive/search")
def search_drive_files(
    q: str = Query(..., min_length=1, max_length=200),
    page_size: int = Query(default=10, ge=1, le=25),
    mime_type: Optional[str] = Query(default=None, max_length=200),
) -> Dict[str, Any]:
    escaped = q.replace("\\", "\\\\").replace("'", "\\'")
    filters = [f"(name contains '{escaped}' or fullText contains '{escaped}')", "trashed = false"]
    if mime_type:
        escaped_mime = mime_type.replace("\\", "\\\\").replace("'", "\\'")
        filters.append(f"mimeType = '{escaped_mime}'")
    payload = _google_request(
        "GET",
        f"{_DRIVE_BASE}/files",
        params={
            "q": " and ".join(filters),
            "pageSize": page_size,
            "fields": f"files({_DRIVE_FILE_FIELDS}),nextPageToken",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
            "corpora": "user",
        },
    )
    files = payload.get("files", [])
    items = [_format_drive_file_metadata(item) for item in files if isinstance(item, dict)]
    return {
        "success": True,
        "count": len(items),
        "items": items,
        "next_page_token": payload.get("nextPageToken"),
    }


@router.get("/drive/files/{file_id}")
def get_drive_file(file_id: str) -> Dict[str, Any]:
    return {"success": True, "file": get_drive_file_metadata(file_id)}


@router.get("/drive/files/{file_id}/content")
def get_drive_file_content(file_id: str, max_chars: int = Query(default=12000, ge=256, le=50000)) -> Dict[str, Any]:
    metadata = get_drive_file_metadata(file_id)
    text_payload = _drive_text_content(file_id, str(metadata.get("mime_type") or ""))
    content = str(text_payload.get("content") or "")
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars]
    return {
        "success": True,
        "file": metadata,
        "content": content,
        "content_type": text_payload.get("content_type"),
        "content_available": bool(text_payload.get("content_available")),
        "truncated": truncated,
    }


@router.post("/drive/link-project")
def link_drive_file_to_project(request: DriveLinkProjectRequest) -> Dict[str, Any]:
    file_id = extract_google_drive_file_id(request.file_id or request.drive_url or "")
    if not file_id:
        raise HTTPException(status_code=400, detail="Could not extract Google Drive file ID from request.")
    metadata = get_drive_file_metadata(file_id)
    result = upsert_project_google_asset(
        request.project_id,
        {
            "asset_id": metadata.get("asset_id"),
            "title": metadata.get("title"),
            "kind": metadata.get("kind"),
            "url": metadata.get("url") or request.drive_url or "",
            "mime_type": metadata.get("mime_type"),
            "role": request.role or "",
            "source": "google_drive",
        },
    )
    return {"success": True, "project_id": request.project_id, "asset": metadata, "google_assets": result["google_assets"]}


# --- Gmail ---


def _build_raw_email(
    to: str,
    subject: str,
    body: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
) -> str:
    """Build base64url-encoded RFC 2822 email for the Gmail send API."""
    import base64
    from email.mime.text import MIMEText

    msg = MIMEText(body)
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")


@router.get("/gmail/messages")
def list_gmail_messages(
    q: str = Query(default="", description="Gmail search query (same syntax as Gmail search box)"),
    max_results: int = Query(default=10, ge=1, le=50),
    label: str = Query(default="INBOX", description="Label ID to filter by"),
) -> Dict[str, Any]:
    """List Gmail messages, optionally filtered by query and label."""
    params: Dict[str, Any] = {"maxResults": max_results, "labelIds": label}
    if q:
        params["q"] = q
    payload = _google_request("GET", f"{_GMAIL_BASE}/users/me/messages", params=params)
    messages = payload.get("messages", [])
    return {
        "success": True,
        "count": len(messages) if isinstance(messages, list) else 0,
        "messages": messages if isinstance(messages, list) else [],
        "next_page_token": payload.get("nextPageToken"),
    }


@router.get("/gmail/messages/{message_id}")
def get_gmail_message(
    message_id: str,
    format: str = Query(default="full", description="full, metadata, minimal, or raw"),
) -> Dict[str, Any]:
    """Get a single Gmail message by ID."""
    encoded = quote(message_id, safe="")
    payload = _google_request(
        "GET",
        f"{_GMAIL_BASE}/users/me/messages/{encoded}",
        params={"format": format},
    )
    return {"success": True, "message": payload}


@router.post("/gmail/send")
def send_gmail(request: GmailSendRequest) -> Dict[str, Any]:
    """Send an email via Gmail."""
    raw = _build_raw_email(
        to=request.to,
        subject=request.subject,
        body=request.body,
        cc=request.cc,
        bcc=request.bcc,
    )
    payload = _google_request(
        "POST",
        f"{_GMAIL_BASE}/users/me/messages/send",
        json_body={"raw": raw},
    )
    return {"success": True, "message_id": payload.get("id")}


@router.post("/gmail/messages/{message_id}/modify")
def modify_gmail_message(
    message_id: str,
    request: GmailModifyRequest,
) -> Dict[str, Any]:
    """Modify labels on a Gmail message (archive, label, etc.)."""
    encoded = quote(message_id, safe="")
    body: Dict[str, Any] = {}
    if request.add_labels:
        body["addLabelIds"] = request.add_labels
    if request.remove_labels:
        body["removeLabelIds"] = request.remove_labels
    payload = _google_request(
        "POST",
        f"{_GMAIL_BASE}/users/me/messages/{encoded}/modify",
        json_body=body,
    )
    return {"success": True, "message": payload}
