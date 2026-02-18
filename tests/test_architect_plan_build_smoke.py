import os
import shutil
import tempfile
import textwrap
import time
import unittest
from unittest.mock import patch

from architect.paths import workspace_dir, workspace_plan_path
from architect.router import ArchitectRouter, BuildRequest


class _DummyTestResult:
    passed = True
    output = "ok"
    error = None
    failed_tests = []


class ArchitectPlanBuildSmokeTests(unittest.TestCase):
    def _write_manifest(self, project_id: str, repo_path: str) -> str:
        manifest_yaml = textwrap.dedent(
            f"""
            schema_version: "1.1"
            project:
              id: "{project_id}"
              name: "Architect Smoke Project"
              paths:
                repo_path: "{repo_path}"
            memory:
              enabled: true
              zones:
                - name: "Code"
                  role: "truth"
                  paths: ["."]
            policy:
              routing_thresholds:
                hybrid_score: 4
                cloud_score: 8
            """
        ).strip()
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
            tmp.write(manifest_yaml)
            return tmp.name

    def test_plan_then_build_smoke(self):
        project_id = f"architect_smoke_{int(time.time() * 1000)}"
        repo_dir = tempfile.mkdtemp(prefix="architect_smoke_repo_")
        manifest_path = self._write_manifest(project_id, repo_dir)
        source_file = os.path.join(repo_dir, "foo.py")

        # Keep source content >100 chars to route through surgical edit path.
        with open(source_file, "w", encoding="utf-8") as f:
            f.write("VALUE = '" + ("a" * 120) + "'\n")

        router = ArchitectRouter(interactive=False, lazy_memory=True)

        try:
            with patch.object(router.llm, "chat", return_value="1. Update `foo.py` to set VALUE."):
                plan_result = router.process_request(
                    BuildRequest(
                        manifest_path=manifest_path,
                        request_type="plan",
                        query="quick code tweak",
                    )
                )

            self.assertEqual(plan_result.status, "SUCCESS")
            self.assertTrue(workspace_plan_path(project_id).exists())

            with patch(
                "architect.router.ArchitectBuilder._extract_file_list",
                return_value=[{"path": "foo.py", "context": "set VALUE"}],
            ):
                with patch(
                    "architect.router.ArchitectBuilder._surgical_edit",
                    return_value="VALUE = 'updated'\n",
                ):
                    with patch(
                        "architect.router.ArchitectTester.run_tests",
                        return_value=_DummyTestResult(),
                    ):
                        build_result = router.process_request(
                            BuildRequest(
                                manifest_path=manifest_path,
                                request_type="build",
                                query="",
                            )
                        )

            self.assertEqual(build_result.status, "SUCCESS")
            self.assertIsInstance(build_result.details, dict)
            self.assertIn("foo.py", build_result.details["files"]["built"])
            self.assertTrue(build_result.details["tests"]["passed"])
        finally:
            if os.path.exists(manifest_path):
                os.remove(manifest_path)
            shutil.rmtree(repo_dir, ignore_errors=True)
            shutil.rmtree(workspace_dir(project_id), ignore_errors=True)

    def test_build_fails_when_plan_missing(self):
        project_id = f"architect_smoke_{int(time.time() * 1000)}_missing"
        repo_dir = tempfile.mkdtemp(prefix="architect_smoke_repo_")
        manifest_path = self._write_manifest(project_id, repo_dir)
        router = ArchitectRouter(interactive=False, lazy_memory=True)

        try:
            shutil.rmtree(workspace_dir(project_id), ignore_errors=True)
            result = router.process_request(
                BuildRequest(
                    manifest_path=manifest_path,
                    request_type="build",
                    query="",
                )
            )

            self.assertEqual(result.status, "FAILURE")
            self.assertIn("Plan not found", result.summary)
        finally:
            if os.path.exists(manifest_path):
                os.remove(manifest_path)
            shutil.rmtree(repo_dir, ignore_errors=True)
            shutil.rmtree(workspace_dir(project_id), ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
