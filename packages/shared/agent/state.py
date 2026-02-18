"""
Agent Task State
Tracks the lifecycle and context of an agent's task execution.
"""

import time
import uuid
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_INPUT = "waiting_input"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Observation:
    """A single tool execution result observed by the agent."""
    tool: str
    params: Dict[str, Any]
    result: Any
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool,
            "params": self.params,
            "result": str(self.result)[:500],
            "timestamp": self.timestamp,
        }


@dataclass
class TaskContext:
    """Full context for an agent's running task."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    goal: str = ""
    status: TaskStatus = TaskStatus.PENDING
    observations: List[Observation] = field(default_factory=list)
    summary: str = ""
    raw_turns: int = 0
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    parent_agent_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def elapsed_seconds(self) -> float:
        end = self.completed_at or time.time()
        return end - self.created_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status.value,
            "observation_count": len(self.observations),
            "summary": self.summary[:200] if self.summary else "",
            "raw_turns": self.raw_turns,
            "elapsed_s": round(self.elapsed_seconds(), 1),
            "parent_agent_id": self.parent_agent_id,
            "metadata": self.metadata,
        }
