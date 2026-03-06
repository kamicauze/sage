"""
Agent Tool Policy
Centralized allow/deny and approval policy for tool execution.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Set


def _csv_set(raw: str) -> Set[str]:
    return {part.strip() for part in (raw or "").split(",") if part.strip()}


@dataclass
class AgentToolPolicy:
    mode: str = "safe"
    deny_tools: Set[str] = field(default_factory=set)
    force_approval_tools: Set[str] = field(default_factory=set)
    allow_write_roots: Set[str] = field(default_factory=lambda: {"apps", "packages", "tests", "docs", "agents"})
    workspace_root: Path = field(default_factory=lambda: Path(os.getenv("SAGE_WORKSPACE_ROOT", os.getcwd())).resolve())

    @classmethod
    def from_env(cls) -> "AgentToolPolicy":
        mode = (os.getenv("SAGE_AGENT_TOOLS_MODE", "safe") or "safe").strip().lower()
        deny = _csv_set(os.getenv("SAGE_AGENT_TOOLS_DENY", ""))
        force_approval = _csv_set(
            os.getenv(
                "SAGE_AGENT_TOOLS_FORCE_APPROVAL",
                "write_file,deploy,architect_build,write_agent_config,register_agent",
            )
        )
        allow_roots = _csv_set(
            os.getenv("SAGE_AGENT_TOOLS_ALLOW_WRITE_ROOTS", "apps,packages,tests,docs,agents")
        )
        workspace_root = Path(os.getenv("SAGE_WORKSPACE_ROOT", os.getcwd())).resolve()

        policy = cls(
            mode=mode,
            deny_tools=deny,
            force_approval_tools=force_approval,
            allow_write_roots=allow_roots or {"apps"},
            workspace_root=workspace_root,
        )

        file_path = (os.getenv("SAGE_AGENT_TOOL_POLICY_PATH") or "").strip()
        if file_path:
            policy = policy.apply_file(Path(file_path).expanduser())
        return policy

    def apply_file(self, path: Path) -> "AgentToolPolicy":
        if not path.exists():
            return self
        data = self._load_policy_file(path)
        if not isinstance(data, dict):
            return self

        mode = str(data.get("mode", self.mode)).strip().lower()
        deny = set(data.get("deny_tools", [])) | self.deny_tools
        force_approval = set(data.get("force_approval_tools", [])) | self.force_approval_tools
        allow_roots = set(data.get("allow_write_roots", [])) or self.allow_write_roots
        workspace = Path(str(data.get("workspace_root", self.workspace_root))).expanduser().resolve()
        return AgentToolPolicy(
            mode=mode,
            deny_tools={str(t).strip() for t in deny if str(t).strip()},
            force_approval_tools={str(t).strip() for t in force_approval if str(t).strip()},
            allow_write_roots={str(t).strip() for t in allow_roots if str(t).strip()},
            workspace_root=workspace,
        )

    @staticmethod
    def _load_policy_file(path: Path) -> Optional[Dict]:
        try:
            if path.suffix.lower() in {".yaml", ".yml"}:
                import yaml

                with path.open("r", encoding="utf-8") as fh:
                    return yaml.safe_load(fh) or {}
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    def is_tool_allowed(self, tool_name: str) -> bool:
        if tool_name in self.deny_tools:
            return False
        if self.mode == "safe" and tool_name in {"deploy"} and "deploy" in self.deny_tools:
            return False
        return True

    def requires_approval(self, tool_name: str, tool_default: bool) -> bool:
        if tool_name in self.force_approval_tools:
            return True
        return bool(tool_default)

    def resolve_read_path(self, raw_path: str) -> Path:
        path = Path(raw_path).expanduser()
        resolved = (self.workspace_root / path).resolve() if not path.is_absolute() else path.resolve()
        resolved.relative_to(self.workspace_root)
        return resolved

    def resolve_write_path(self, raw_path: str) -> Path:
        resolved = self.resolve_read_path(raw_path)
        try:
            rel = resolved.relative_to(self.workspace_root)
        except Exception as e:
            raise PermissionError(f"Path outside workspace: {raw_path}") from e

        top = rel.parts[0] if rel.parts else ""
        if top not in self.allow_write_roots:
            raise PermissionError(
                f"Writes are blocked for '{raw_path}'. Allowed roots: {sorted(self.allow_write_roots)}"
            )
        return resolved
