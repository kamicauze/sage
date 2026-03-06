import os
import sys
import tempfile
import unittest
from pathlib import Path


class AgentToolPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

    def test_policy_blocks_denied_tool(self):
        from shared.agent.policy import AgentToolPolicy

        policy = AgentToolPolicy(
            mode="safe",
            deny_tools={"deploy"},
            force_approval_tools=set(),
            allow_write_roots={"apps"},
            workspace_root=Path("/tmp"),
        )
        self.assertFalse(policy.is_tool_allowed("deploy"))
        self.assertTrue(policy.is_tool_allowed("read_file"))

    def test_policy_write_path_restricted_to_allow_roots(self):
        from shared.agent.policy import AgentToolPolicy

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            policy = AgentToolPolicy(
                mode="safe",
                deny_tools=set(),
                force_approval_tools=set(),
                allow_write_roots={"apps"},
                workspace_root=root,
            )
            ok = policy.resolve_write_path("apps/demo/file.txt")
            self.assertTrue(str(ok).startswith(str(root)))
            with self.assertRaises(PermissionError):
                policy.resolve_write_path("secrets/file.txt")

    def test_tool_sandbox_blocks_dangerous_shell(self):
        from shared.agent.policy import AgentToolPolicy
        from shared.agent.sandbox import ToolSandbox

        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            policy = AgentToolPolicy(
                mode="safe",
                deny_tools=set(),
                force_approval_tools=set(),
                allow_write_roots={"apps"},
                workspace_root=root,
            )
            sandbox = ToolSandbox(policy)
            result = asyncio_run(sandbox.run_command("rm -rf /", cwd="."))
            self.assertIn("BLOCKED", result)


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)


if __name__ == "__main__":
    unittest.main()
