"""
Approval queue API for human-in-the-middle decisions.

This provides a lightweight control plane for risky actions:
 - create proposal
 - list pending proposals
 - approve/deny proposal
 - inspect proposal status
 - ingest orchestrator events as approval proposals
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/approvals", tags=["approvals"])

_STORE_VERSION = 1


def _resolve_store_path() -> Path:
    raw_path = os.getenv("SAGE_APPROVALS_STORE_PATH", ".sage_memory/approvals/queue.json").strip()
    base = Path(raw_path).expanduser()
    if not base.is_absolute():
        base = Path(os.getcwd()) / base
    return base.resolve()


_STORE_PATH = _resolve_store_path()


class ApprovalAction(BaseModel):
    type: str = Field(..., description="Action type, e.g. model_switch")
    target: Optional[str] = Field(default=None, description="Primary target, e.g. model name")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Action payload")


class ApprovalProposalRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Human-readable approval title")
    summary: str = Field(..., min_length=1, description="What this action will do")
    source: str = Field(default="sage", description="Producer of the approval request")
    risk: Literal["low", "medium", "high", "critical"] = "medium"
    actions: List[ApprovalAction] = Field(
        default_factory=list,
        description="Actions to execute if approved",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    expires_in_seconds: int = Field(
        default=900,
        ge=60,
        le=7 * 24 * 3600,
        description="Expiry TTL in seconds",
    )


class OrchestratorEventRequest(BaseModel):
    event_type: str = Field(..., min_length=1, description="Event type, e.g. pr_ready or ci_failed")
    title: Optional[str] = Field(default=None, description="Optional explicit approval title")
    summary: Optional[str] = Field(default=None, description="Optional explicit summary")
    source: str = Field(default="sage.orchestrator", description="Producer of the event")
    risk: Literal["low", "medium", "high", "critical"] = "medium"
    task_id: Optional[str] = None
    project_id: Optional[str] = None
    repo: Optional[str] = None
    branch: Optional[str] = None
    pr_number: Optional[int] = Field(default=None, ge=1)
    checks_url: Optional[str] = None
    estimated_cost_usd: Optional[float] = Field(default=None, ge=0)
    resource: Optional[str] = None
    alternative_strategy: Optional[str] = None
    actions: List[ApprovalAction] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    expires_in_seconds: int = Field(
        default=6 * 3600,
        ge=60,
        le=7 * 24 * 3600,
        description="Expiry TTL in seconds",
    )


class ApprovalDecisionRequest(BaseModel):
    decision: Literal["approve", "deny"]
    reviewer: str = Field(default="human", description="Who made the decision")
    reason: Optional[str] = Field(default=None, description="Optional decision note")


class ApprovalRecord(BaseModel):
    id: str
    status: Literal["pending", "approved", "denied", "expired"]
    title: str
    summary: str
    source: str
    risk: Literal["low", "medium", "high", "critical"]
    actions: List[ApprovalAction]
    metadata: Dict[str, Any]
    created_at: str
    expires_at: str
    decided_at: Optional[str] = None
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None


_lock = Lock()
_approvals: Dict[str, ApprovalRecord] = {}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _model_validate(model_cls, payload):
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(payload)
    return model_cls.parse_obj(payload)


def _load_store_locked() -> None:
    if not _STORE_PATH.exists():
        return

    try:
        raw = _STORE_PATH.read_text(encoding="utf-8")
        if not raw.strip():
            return
        data = json.loads(raw)
    except Exception:
        return

    items = data.get("approvals", []) if isinstance(data, dict) else []
    if not isinstance(items, list):
        return

    loaded: Dict[str, ApprovalRecord] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            record = _model_validate(ApprovalRecord, item)
            loaded[record.id] = record
        except Exception:
            continue

    _approvals.clear()
    _approvals.update(loaded)


def _save_store_locked() -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "version": _STORE_VERSION,
        "updated_at": _to_iso(_now_utc()),
        "approvals": [
            record.model_dump()
            for record in sorted(_approvals.values(), key=lambda r: r.created_at)
        ],
    }

    tmp_path = _STORE_PATH.parent / f"{_STORE_PATH.name}.tmp"
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp_path.replace(_STORE_PATH)


def _mark_expired_locked(now: datetime) -> bool:
    changed = False
    for record in _approvals.values():
        if record.status != "pending":
            continue
        if datetime.fromisoformat(record.expires_at) <= now:
            record.status = "expired"
            changed = True
    return changed


def _create_record_from_request(request: ApprovalProposalRequest, now: datetime) -> ApprovalRecord:
    expires_at = now + timedelta(seconds=request.expires_in_seconds)
    return ApprovalRecord(
        id=str(uuid4()),
        status="pending",
        title=request.title,
        summary=request.summary,
        source=request.source,
        risk=request.risk,
        actions=request.actions,
        metadata=request.metadata,
        created_at=_to_iso(now),
        expires_at=_to_iso(expires_at),
    )


def _default_event_title(event_type: str) -> str:
    label = event_type.strip().lower()
    mappings = {
        "pr_ready": "PR Ready For Review",
        "merge_ready": "PR Ready To Merge",
        "ci_failed": "CI Failure Needs Triage",
        "task_blocked": "Task Blocked",
        "task_failed": "Task Failed",
        "deploy_ready": "Deploy Approval Needed",
    }
    return mappings.get(label, f"Orchestrator Event: {label.replace('_', ' ').title()}")


def _default_event_summary(request: OrchestratorEventRequest) -> str:
    details: List[str] = []
    if request.repo:
        details.append(f"repo={request.repo}")
    if request.branch:
        details.append(f"branch={request.branch}")
    if request.pr_number:
        details.append(f"pr=#{request.pr_number}")
    if request.task_id:
        details.append(f"task={request.task_id}")
    suffix = f" ({', '.join(details)})" if details else ""
    return f"{request.event_type.strip()} requires human review{suffix}."


def _default_event_action(request: OrchestratorEventRequest) -> ApprovalAction:
    target = None
    if request.pr_number:
        target = f"pr-{request.pr_number}"
    elif request.task_id:
        target = request.task_id

    payload = {
        "event_type": request.event_type,
        "task_id": request.task_id,
        "project_id": request.project_id,
        "repo": request.repo,
        "branch": request.branch,
        "pr_number": request.pr_number,
        "checks_url": request.checks_url,
    }

    clean_payload = {k: v for k, v in payload.items() if v is not None}
    return ApprovalAction(type="orchestrator_event", target=target, payload=clean_payload)


@router.post("/proposals")
async def create_proposal(request: ApprovalProposalRequest):
    now = _now_utc()
    record = _create_record_from_request(request, now)

    with _lock:
        _approvals[record.id] = record
        _save_store_locked()

    return {"success": True, "proposal": record.model_dump()}


@router.post("/events")
async def create_proposal_from_event(request: OrchestratorEventRequest):
    metadata = dict(request.metadata)
    metadata.setdefault("event_type", request.event_type)
    metadata.setdefault("source", request.source)
    if request.task_id:
        metadata.setdefault("task_id", request.task_id)
    if request.project_id:
        metadata.setdefault("project_id", request.project_id)
    if request.repo:
        metadata.setdefault("repo", request.repo)
    if request.branch:
        metadata.setdefault("branch", request.branch)
    if request.pr_number is not None:
        metadata.setdefault("pr_number", request.pr_number)
    if request.checks_url:
        metadata.setdefault("checks_url", request.checks_url)

    if request.estimated_cost_usd is not None:
        metadata.setdefault("estimated_cost_usd", request.estimated_cost_usd)
    metadata.setdefault("resource", request.resource or request.repo or "orchestrator")
    metadata.setdefault(
        "alternative_strategy",
        request.alternative_strategy
        or "Request manual review and re-run with narrowed scope and explicit file targets.",
    )

    proposal = ApprovalProposalRequest(
        title=request.title or _default_event_title(request.event_type),
        summary=(request.summary or _default_event_summary(request)).strip(),
        source=request.source,
        risk=request.risk,
        actions=request.actions or [_default_event_action(request)],
        metadata=metadata,
        expires_in_seconds=request.expires_in_seconds,
    )

    now = _now_utc()
    record = _create_record_from_request(proposal, now)
    with _lock:
        _approvals[record.id] = record
        _save_store_locked()

    return {
        "success": True,
        "proposal": record.model_dump(),
        "created_from": "orchestrator_event",
    }


@router.get("/pending")
async def list_pending():
    now = _now_utc()
    with _lock:
        changed = _mark_expired_locked(now)
        if changed:
            _save_store_locked()
        pending = [r for r in _approvals.values() if r.status == "pending"]

    pending.sort(key=lambda r: r.created_at, reverse=True)
    return {"success": True, "count": len(pending), "items": [r.model_dump() for r in pending]}


@router.get("/{proposal_id}")
async def get_proposal(proposal_id: str):
    now = _now_utc()
    with _lock:
        changed = _mark_expired_locked(now)
        if changed:
            _save_store_locked()
        record = _approvals.get(proposal_id)

    if not record:
        raise HTTPException(status_code=404, detail="Approval proposal not found")

    return {"success": True, "proposal": record.model_dump()}


@router.post("/{proposal_id}/decision")
async def submit_decision(proposal_id: str, request: ApprovalDecisionRequest):
    now = _now_utc()
    with _lock:
        changed = _mark_expired_locked(now)
        record = _approvals.get(proposal_id)
        if not record:
            if changed:
                _save_store_locked()
            raise HTTPException(status_code=404, detail="Approval proposal not found")

        if record.status != "pending":
            if changed:
                _save_store_locked()
            raise HTTPException(
                status_code=409,
                detail=f"Proposal already resolved with status '{record.status}'",
            )

        record.status = "approved" if request.decision == "approve" else "denied"
        record.decided_at = _to_iso(now)
        record.decided_by = request.reviewer
        record.decision_reason = request.reason
        _save_store_locked()

    return {"success": True, "proposal": record.model_dump()}


with _lock:
    _load_store_locked()
