"""
Sage Agent Framework
Generic, reusable agent loop with think → act → observe cycle.
Supports self-spawning: agents can create new agent definitions dynamically.
"""

from .state import TaskStatus, TaskContext, Observation
from .tools import Tool
from .config import AgentConfig
from .base import Agent
from .registry import AgentRegistry

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentRegistry",
    "Tool",
    "TaskStatus",
    "TaskContext",
    "Observation",
]
