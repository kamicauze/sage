"""
Persistent Task Queue
SQLite-backed durable storage for agent task execution.
Survives restarts — incomplete tasks can be resumed on startup.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional


def _resolve_db_path(raw: str = ".sage_memory/agent_tasks.db") -> Path:
    base = Path(raw).expanduser()
    if not base.is_absolute():
        base = Path(os.getcwd()) / base
    return base.resolve()


class TaskStore:
    """SQLite-backed persistent task queue for agent execution."""

    def __init__(self, db_path: str = None):
        raw = db_path or os.getenv("SAGE_TASK_STORE_PATH", ".sage_memory/agent_tasks.db")
        self.db_path = _resolve_db_path(raw)
        self._lock = Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Create tables if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    agent_name TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'QUEUED',
                    config_json TEXT,
                    created_at REAL NOT NULL,
                    started_at REAL,
                    completed_at REAL,
                    error TEXT,
                    result_summary TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    params_json TEXT,
                    result_text TEXT,
                    timestamp REAL NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_observations_task ON observations(task_id)
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def enqueue(self, agent_name: str, goal: str, config_json: str = None) -> str:
        """Add a task to the queue. Returns task_id."""
        task_id = uuid.uuid4().hex[:8]
        now = time.time()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO tasks (id, agent_name, goal, status, config_json, created_at)
                       VALUES (?, ?, ?, 'QUEUED', ?, ?)""",
                    (task_id, agent_name, goal, config_json, now),
                )
        return task_id

    def mark_running(self, task_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE tasks SET status='RUNNING', started_at=? WHERE id=?",
                    (time.time(), task_id),
                )

    def mark_completed(self, task_id: str, summary: str = "") -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE tasks SET status='COMPLETED', completed_at=?, result_summary=? WHERE id=?",
                    (time.time(), summary, task_id),
                )

    def mark_failed(self, task_id: str, error: str = "") -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE tasks SET status='FAILED', completed_at=?, error=? WHERE id=?",
                    (time.time(), error, task_id),
                )

    def mark_cancelled(self, task_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE tasks SET status='CANCELLED', completed_at=? WHERE id=?",
                    (time.time(), task_id),
                )

    def get_pending(self) -> List[Dict[str, Any]]:
        """Get tasks in QUEUED state (for resume on restart)."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status='QUEUED' ORDER BY created_at ASC"
                ).fetchall()
                return [dict(r) for r in rows]

    def get_running(self) -> List[Dict[str, Any]]:
        """Get tasks in RUNNING state (potentially stale after crash)."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status='RUNNING' ORDER BY started_at ASC"
                ).fetchall()
                return [dict(r) for r in rows]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id=?", (task_id,)
                ).fetchone()
                return dict(row) if row else None

    def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get most recent tasks regardless of status."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
                return [dict(r) for r in rows]

    def add_observation(self, task_id: str, tool: str, params: Dict, result: str) -> None:
        """Persist an observation for crash recovery."""
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO observations (task_id, tool, params_json, result_text, timestamp)
                       VALUES (?, ?, ?, ?, ?)""",
                    (task_id, tool, json.dumps(params), result[:4000], time.time()),
                )

    def get_observations(self, task_id: str) -> List[Dict[str, Any]]:
        """Get observations for a task (for resume)."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM observations WHERE task_id=? ORDER BY timestamp ASC",
                    (task_id,),
                ).fetchall()
                return [dict(r) for r in rows]

    def cleanup_stale(self, max_age_hours: int = 72) -> int:
        """Mark old RUNNING tasks as FAILED (crashed). Returns count cleaned."""
        cutoff = time.time() - (max_age_hours * 3600)
        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    """UPDATE tasks SET status='FAILED', completed_at=?, error='Stale: process crashed or restarted'
                       WHERE status='RUNNING' AND started_at < ?""",
                    (time.time(), cutoff),
                )
                return cursor.rowcount

    def get_stats(self) -> Dict[str, int]:
        """Get task count by status."""
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT status, COUNT(*) as count FROM tasks GROUP BY status"
                ).fetchall()
                return {row["status"]: row["count"] for row in rows}
