"""
Task history API for Sage agent task queue.

Provides read-only access to the persistent task store for
monitoring agent execution history and status.
"""
from __future__ import annotations

import sys
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

# Ensure shared packages are importable
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.agent.task_store import TaskStore

router = APIRouter(prefix="/tasks", tags=["tasks"])

_store: Optional[TaskStore] = None


def _get_store() -> TaskStore:
    global _store
    if _store is None:
        _store = TaskStore()
    return _store


@router.get("/")
def list_tasks(
    status: Optional[str] = Query(default=None, description="Filter by status: QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED"),
    limit: int = Query(default=20, ge=1, le=100),
) -> Dict[str, Any]:
    """List recent agent tasks."""
    store = _get_store()
    tasks = store.get_recent(limit)
    if status:
        tasks = [t for t in tasks if t.get("status") == status.upper()]
    return {"success": True, "count": len(tasks), "tasks": tasks}


@router.get("/stats")
def task_stats() -> Dict[str, Any]:
    """Get task count by status."""
    store = _get_store()
    stats = store.get_stats()
    return {"success": True, "stats": stats}


@router.get("/{task_id}")
def get_task(task_id: str) -> Dict[str, Any]:
    """Get a single task by ID, including its observations."""
    store = _get_store()
    task = store.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    observations = store.get_observations(task_id)
    return {"success": True, "task": task, "observations": observations}
