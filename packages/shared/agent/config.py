"""
Agent Configuration
Serializable agent definitions that can be stored as YAML/JSON.
This is the key to self-spawning: agents create configs, registry loads them.
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class AgentConfig:
    """Defines an agent's identity, capabilities, and constraints."""
    name: str
    goal: str
    tools: List[str] = field(default_factory=list)
    model: str = "local"
    max_iterations: int = 50
    compress_after: int = 8
    needs_approval_to_start: bool = True
    budget_limit_usd: float = 5.0
    mqtt_topic_prefix: str = ""
    schedule: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.mqtt_topic_prefix:
            self.mqtt_topic_prefix = f"sage/agent/{self.name}"

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "name": self.name,
            "goal": self.goal,
            "tools": self.tools,
            "model": self.model,
            "max_iterations": self.max_iterations,
            "compress_after": self.compress_after,
            "needs_approval_to_start": self.needs_approval_to_start,
            "budget_limit_usd": self.budget_limit_usd,
        }
        if self.schedule:
            d["schedule"] = self.schedule
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    def to_yaml(self) -> str:
        try:
            import yaml
            return yaml.dump(self.to_dict(), default_flow_style=False)
        except ImportError:
            import json
            return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_yaml(cls, path: str) -> "AgentConfig":
        try:
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
        except ImportError:
            import json
            with open(path) as f:
                data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentConfig":
        valid_fields = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**filtered)

    def save(self, directory: str = "agents"):
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f"{self.name}.yaml")
        with open(path, "w") as f:
            f.write(self.to_yaml())
        return path
