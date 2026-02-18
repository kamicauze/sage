"""
Approval queue API for human-in-the-middle decisions.

This provides a lightweight control plane for risky actions:
 - create proposal
 - list pending proposals
 - approve/deny proposal
 - inspect proposal status
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/approvals", tags=["approvals"])


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


def _mark_expired_locked(now: datetime) -> None:
    for record in _approvals.values():
        if record.status != "pending":
            continue
        if datetime.fromisoformat(record.expires_at) <= now:
            record.status = "expired"


@router.post("/proposals")
async def create_proposal(request: ApprovalProposalRequest):
    now = _now_utc()
    expires_at = now + timedelta(seconds=request.expires_in_seconds)
    record = ApprovalRecord(
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

    with _lock:
        _approvals[record.id] = record

    return {"success": True, "proposal": record.model_dump()}


@router.get("/pending")
async def list_pending():
    now = _now_utc()
    with _lock:
        _mark_expired_locked(now)
        pending = [r for r in _approvals.values() if r.status == "pending"]

    pending.sort(key=lambda r: r.created_at, reverse=True)
    return {"success": True, "count": len(pending), "items": [r.model_dump() for r in pending]}


@router.get("/{proposal_id}")
async def get_proposal(proposal_id: str):
    now = _now_utc()
    with _lock:
        _mark_expired_locked(now)
        record = _approvals.get(proposal_id)

    if not record:
        raise HTTPException(status_code=404, detail="Approval proposal not found")

    return {"success": True, "proposal": record.model_dump()}


@router.post("/{proposal_id}/decision")
async def submit_decision(proposal_id: str, request: ApprovalDecisionRequest):
    now = _now_utc()
    with _lock:
        _mark_expired_locked(now)
        record = _approvals.get(proposal_id)
        if not record:
            raise HTTPException(status_code=404, detail="Approval proposal not found")

        if record.status != "pending":
            raise HTTPException(
                status_code=409,
                detail=f"Proposal already resolved with status '{record.status}'",
            )

        record.status = "approved" if request.decision == "approve" else "denied"
        record.decided_at = _to_iso(now)
        record.decided_by = request.reviewer
        record.decision_reason = request.reason

    return {"success": True, "proposal": record.model_dump()}

