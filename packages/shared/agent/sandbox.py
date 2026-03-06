"""
Agent Tool Sandbox Runner
Phase-1 isolation: workspace-bounded file access + guarded subprocess execution.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

from .policy import AgentToolPolicy


class ToolSandbox:
    def __init__(self, policy: AgentToolPolicy):
        self.policy = policy

    def read_text(self, path: str, max_chars: int = 5000) -> str:
        resolved = self.policy.resolve_read_path(path)
        with resolved.open("r", encoding="utf-8") as fh:
            content = fh.read()
        if len(content) > max_chars:
            return content[:max_chars] + f"\n... (truncated, {len(content)} total chars)"
        return content

    def write_text(self, path: str, content: str) -> str:
        resolved = self.policy.resolve_write_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("w", encoding="utf-8") as fh:
            fh.write(content)
        return f"Written {len(content)} chars to {resolved}"

    async def run_command(
        self,
        command: str,
        *,
        cwd: str = ".",
        max_output_chars: int = 4000,
        timeout_sec: int = 300,
    ) -> str:
        blocked = (
            "rm -rf /",
            "shutdown",
            "reboot",
            "mkfs",
            ":(){:|:&};:",
            "dd if=",
        )
        lower = command.lower()
        if any(token in lower for token in blocked):
            return f"BLOCKED by sandbox policy: '{command}'"

        safe_cwd: Path = self.policy.resolve_read_path(cwd)
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(safe_cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            proc.kill()
            return f"FAILED\nCommand timed out after {timeout_sec}s"

        output = stdout.decode(errors="replace")
        if len(output) > max_output_chars:
            output = output[-max_output_chars:]
        status = "SUCCESS" if proc.returncode == 0 else "FAILED"
        return f"{status}\n{output}"
