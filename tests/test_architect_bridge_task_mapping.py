import sys
import types
import unittest
from unittest.mock import patch

from brain.bridges.architect_bridge import ArchitectBridge


class _DummyResult:
    def __init__(self, status: str, artifacts=None, summary: str = ""):
        self.status = status
        self.artifacts = artifacts or []
        self.summary = summary


class _DummyRouter:
    def __init__(self, plan_status: str = "SUCCESS", build_status: str = "SUCCESS"):
        self.calls = []
        self.plan_status = plan_status
        self.build_status = build_status

    def process_request(self, request):
        self.calls.append((request.request_type, request.query))
        if request.request_type == "plan":
            return _DummyResult(self.plan_status, ["generated/architect/workspaces/sage_brain/plan.md"], "plan ok")
        if request.request_type == "build":
            return _DummyResult(self.build_status, ["generated/architect/workspaces/sage_brain/sandbox/foo.py"], "build ok")
        return _DummyResult("FAILURE", [], f"unexpected request_type={request.request_type}")


class _FakeBuildRequest:
    def __init__(self, manifest_path, request_type, query, context):
        self.manifest_path = manifest_path
        self.request_type = request_type
        self.query = query
        self.context = context


class ArchitectBridgeTaskMappingTests(unittest.TestCase):
    def test_normalize_task_type(self):
        self.assertEqual(ArchitectBridge._normalize_task_type("plan"), "plan")
        self.assertEqual(ArchitectBridge._normalize_task_type("build"), "build")
        self.assertEqual(ArchitectBridge._normalize_task_type("code"), "plan_then_build")
        self.assertEqual(ArchitectBridge._normalize_task_type("fix"), "plan_then_build")
        self.assertEqual(ArchitectBridge._normalize_task_type("test"), "plan_then_build")
        self.assertEqual(ArchitectBridge._normalize_task_type("unknown"), "plan")

    def test_sync_process_plan_then_build_runs_both_steps(self):
        fake_router_module = types.ModuleType("architect.router")
        fake_router_module.BuildRequest = _FakeBuildRequest
        fake_router_module.ArchitectRouter = object

        bridge = ArchitectBridge()
        dummy_router = _DummyRouter(plan_status="SUCCESS", build_status="SUCCESS")
        bridge._get_router = lambda: dummy_router

        with patch.dict(sys.modules, {"architect.router": fake_router_module}):
            result = bridge._sync_process(
                manifest_path="architect/projects/sage.yaml",
                task_type="plan_then_build",
                query="add expense tracking",
                context={}
            )

        self.assertEqual(dummy_router.calls, [("plan", "add expense tracking"), ("build", "")])
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(
            result["artifacts"],
            [
                "generated/architect/workspaces/sage_brain/plan.md",
                "generated/architect/workspaces/sage_brain/sandbox/foo.py",
            ],
        )

    def test_sync_process_plan_then_build_stops_if_plan_fails(self):
        fake_router_module = types.ModuleType("architect.router")
        fake_router_module.BuildRequest = _FakeBuildRequest
        fake_router_module.ArchitectRouter = object

        bridge = ArchitectBridge()
        dummy_router = _DummyRouter(plan_status="FAILURE", build_status="SUCCESS")
        bridge._get_router = lambda: dummy_router

        with patch.dict(sys.modules, {"architect.router": fake_router_module}):
            result = bridge._sync_process(
                manifest_path="architect/projects/sage.yaml",
                task_type="plan_then_build",
                query="add expense tracking",
                context={}
            )

        self.assertEqual(dummy_router.calls, [("plan", "add expense tracking")])
        self.assertEqual(result["status"], "FAILURE")


if __name__ == "__main__":
    unittest.main()
