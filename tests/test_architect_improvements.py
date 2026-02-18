import unittest
from unittest.mock import patch
import os
import shutil
import tempfile
import textwrap
import time
from architect.paths import workspace_dir


class ArchitectImprovementsTests(unittest.TestCase):
    def test_manifest_zone_matching_supports_migrated_layout(self):
        from architect.manifest import ProjectManifest

        manifest = ProjectManifest.load("architect/projects/sage.yaml")

        legacy = manifest.get_zone_for_file("brain/core/summary_engine.py")
        migrated = manifest.get_zone_for_file("apps/brain-runtime/core/summary_engine.py")

        self.assertIsNotNone(legacy)
        self.assertIsNotNone(migrated)
        self.assertEqual(legacy.name, "The Truth")
        self.assertEqual(migrated.name, "The Truth")

    def test_tester_sets_pythonpath_in_subprocess_env(self):
        from architect.tester import ArchitectTester

        sandbox = "/tmp/architect_test_sandbox"
        tester = ArchitectTester(sandbox)

        class DummyResult:
            returncode = 0
            stdout = "ok"
            stderr = ""

        with patch("subprocess.run", return_value=DummyResult()) as mock_run:
            result = tester.run_tests()

        self.assertTrue(result.passed)
        kwargs = mock_run.call_args.kwargs
        env = kwargs["env"]
        self.assertIn("PYTHONPATH", env)
        self.assertIn(sandbox, env["PYTHONPATH"])

    def test_builder_heuristic_file_extraction_fallback(self):
        from architect.builder import ArchitectBuilder

        builder = ArchitectBuilder.__new__(ArchitectBuilder)
        plan = """
        1. Update `apps/brain-runtime/main.py` to improve event handling.
        2. Add tests in `tests/test_prompt_layers.py`.
        3. Touch packages/shared/routing.py for score tweak.
        """

        files = builder._extract_file_list_heuristic(plan)
        paths = {item["path"] for item in files}

        self.assertIn("apps/brain-runtime/main.py", paths)
        self.assertIn("tests/test_prompt_layers.py", paths)
        self.assertIn("packages/shared/routing.py", paths)

    def test_router_plan_succeeds_without_memory_for_simple_query(self):
        from architect.router import ArchitectRouter, BuildRequest

        manifest_yaml = textwrap.dedent(
            """
            schema_version: "1.1"
            project:
              id: "architect_test_project"
              name: "Architect Test Project"
              paths:
                repo_path: "."
            memory:
              enabled: true
              zones:
                - name: "Code"
                  role: "truth"
                  paths: ["apps/brain-runtime"]
            policy:
              routing_thresholds:
                hybrid_score: 4
                cloud_score: 8
            """
        ).strip()

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
            tmp.write(manifest_yaml)
            manifest_path = tmp.name

        router = ArchitectRouter(interactive=False, lazy_memory=True)
        request = BuildRequest(
            manifest_path=manifest_path,
            request_type="plan",
            query="quick docs wording tweak"
        )

        try:
            with patch.object(router.llm, "chat", return_value="Plan: update docs wording."):
                result = router.process_request(request)
        finally:
            if os.path.exists(manifest_path):
                os.remove(manifest_path)
            shutil.rmtree("generated/architect/workspaces/architect_test_project", ignore_errors=True)

        self.assertEqual(result.status, "SUCCESS")
        self.assertTrue(result.artifacts)
        self.assertTrue(isinstance(result.details, dict))
        self.assertIn("timing", result.details)
        self.assertGreaterEqual(result.details["timing"]["duration_ms"], 0)

    def test_incremental_cache_skips_unchanged_file(self):
        from architect.builder import ArchitectBuilder
        from architect.manifest import ProjectManifest

        project_id = f"architect_inc_{int(time.time() * 1000)}"
        repo_dir = tempfile.mkdtemp(prefix="architect_repo_")
        source_path = os.path.join(repo_dir, "foo.py")

        # >100 chars to trigger surgical edit path in builder.
        with open(source_path, "w", encoding="utf-8") as f:
            f.write("VALUE = '" + ("a" * 120) + "'\n")

        manifest = ProjectManifest(
            id=project_id,
            name="Incremental Test",
            repo_path=repo_dir,
            zones=[],
            raw={}
        )
        builder = ArchitectBuilder(manifest, incremental=True, parallel=False)
        file_info = {"path": "foo.py", "context": "append comment"}
        plan = "Update foo.py according to requirements."
        sandbox_path = os.path.join(builder.sandbox_dir, "foo.py")

        try:
            with patch.object(builder, "_surgical_edit", return_value="VALUE='v1'\n"):
                builder._generate_file(file_info, plan)

            self.assertTrue(os.path.exists(sandbox_path))
            with open(sandbox_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "VALUE='v1'\n")

            # Same plan + same source: should skip and never call generator.
            with patch.object(builder, "_surgical_edit", side_effect=AssertionError("should have been skipped")):
                builder._generate_file(file_info, plan)

            with open(sandbox_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "VALUE='v1'\n")
            self.assertEqual(builder.files_built.count("foo.py"), 1)
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)
            shutil.rmtree(workspace_dir(project_id), ignore_errors=True)

    def test_incremental_cache_regenerates_when_source_changes(self):
        from architect.builder import ArchitectBuilder
        from architect.manifest import ProjectManifest

        project_id = f"architect_inc_{int(time.time() * 1000)}_chg"
        repo_dir = tempfile.mkdtemp(prefix="architect_repo_")
        source_path = os.path.join(repo_dir, "foo.py")

        with open(source_path, "w", encoding="utf-8") as f:
            f.write("VALUE = '" + ("b" * 120) + "'\n")

        manifest = ProjectManifest(
            id=project_id,
            name="Incremental Change Test",
            repo_path=repo_dir,
            zones=[],
            raw={}
        )
        builder = ArchitectBuilder(manifest, incremental=True, parallel=False)
        file_info = {"path": "foo.py", "context": "append comment"}
        plan = "Update foo.py according to requirements."
        sandbox_path = os.path.join(builder.sandbox_dir, "foo.py")

        try:
            with patch.object(builder, "_surgical_edit", return_value="VALUE='v1'\n"):
                builder._generate_file(file_info, plan)

            # Modify source file -> input signature should change -> regeneration required.
            with open(source_path, "a", encoding="utf-8") as f:
                f.write("# changed source\n")

            with patch.object(builder, "_surgical_edit", return_value="VALUE='v2'\n") as regen_mock:
                builder._generate_file(file_info, plan)
                self.assertEqual(regen_mock.call_count, 1)

            with open(sandbox_path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "VALUE='v2'\n")
            self.assertEqual(builder.files_built.count("foo.py"), 2)
        finally:
            shutil.rmtree(repo_dir, ignore_errors=True)
            shutil.rmtree(workspace_dir(project_id), ignore_errors=True)

    def test_build_result_includes_structured_telemetry(self):
        from architect.router import ArchitectRouter, BuildRequest
        from architect.paths import workspace_plan_path, workspace_dir

        project_id = f"architect_build_{int(time.time() * 1000)}"
        manifest_yaml = textwrap.dedent(
            f"""
            schema_version: "1.1"
            project:
              id: "{project_id}"
              name: "Architect Build Telemetry"
              paths:
                repo_path: "."
            memory:
              enabled: true
              zones:
                - name: "Code"
                  role: "truth"
                  paths: ["apps/brain-runtime"]
            policy:
              routing_thresholds:
                hybrid_score: 4
                cloud_score: 8
            """
        ).strip()

        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tmp:
            tmp.write(manifest_yaml)
            manifest_path = tmp.name

        plan_path = workspace_plan_path(project_id)
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        with open(plan_path, "w", encoding="utf-8") as f:
            f.write("Plan content")

        class DummyBuilder:
            def __init__(self, manifest, interactive=False):
                self.sandbox_dir = str(workspace_dir(project_id) / "sandbox")
                self.files_planned = []
                self.files_built = []
                self.files_skipped = []
                self.files_failed = []

            def build_from_plan(self, _plan_path):
                self.files_planned = ["foo.py", "bar.py"]
                self.files_built = ["foo.py"]
                self.files_skipped = [{"path": "bar.py", "reason": "input_signature_unchanged"}]
                self.files_failed = []

            def generate_tests(self, file_path):
                return f"test_{file_path}"

            def fix_code(self, file_path, error_log):
                return None

        class DummyTester:
            def __init__(self, sandbox_path):
                self.sandbox_path = sandbox_path

            def run_tests(self):
                class R:
                    passed = True
                    output = "ok"
                    error = None
                    failed_tests = []
                return R()

        router = ArchitectRouter(interactive=False, lazy_memory=True)
        request = BuildRequest(
            manifest_path=manifest_path,
            request_type="build",
            query=""
        )

        try:
            with patch("architect.router.ArchitectBuilder", DummyBuilder):
                with patch("architect.router.ArchitectTester", DummyTester):
                    result = router.process_request(request)
        finally:
            if os.path.exists(manifest_path):
                os.remove(manifest_path)
            shutil.rmtree(workspace_dir(project_id), ignore_errors=True)

        self.assertEqual(result.status, "SUCCESS")
        self.assertTrue(isinstance(result.details, dict))
        self.assertEqual(result.details["files"]["planned"], ["foo.py", "bar.py"])
        self.assertEqual(result.details["files"]["built"], ["foo.py"])
        self.assertEqual(result.details["files"]["skipped"][0]["path"], "bar.py")
        self.assertTrue(result.details["tests"]["passed"])
        self.assertEqual(result.details["tests"]["generated"], ["test_foo.py"])
        self.assertEqual(len(result.details["tests"]["attempts"]), 1)
        self.assertIn("timing", result.details)

    def test_llm_external_cli_provider_success(self):
        from architect.llm import LLMClient

        class DummyCompleted:
            returncode = 0
            stdout = "external cli response\n"
            stderr = ""

        with patch.dict(os.environ, {"SAGE_CODEX_CLI_CMD": "fake-codex --stdin"}):
            client = LLMClient()
            with patch.object(client, "_check_budget", return_value=None):
                with patch.object(client, "_log_usage", return_value=None):
                    with patch.object(client, "_update_usage", return_value=None):
                        with patch("subprocess.run", return_value=DummyCompleted()) as mock_run:
                            out = client.chat(
                                [{"role": "user", "content": "hello"}],
                                provider="codex_cli",
                                model="codex"
                            )

        self.assertEqual(out, "external cli response")
        called_cmd = mock_run.call_args.args[0]
        self.assertEqual(called_cmd, ["fake-codex", "--stdin"])

    def test_llm_external_cli_provider_missing_config(self):
        from architect.llm import LLMClient

        with patch.dict(os.environ, {}, clear=True):
            client = LLMClient()
            with patch.object(client, "_check_budget", return_value=None):
                out = client.chat(
                    [{"role": "user", "content": "hello"}],
                    provider="codex_cli",
                    model="codex"
                )

        self.assertIn("SAGE_CODEX_CLI_CMD not configured", out)


if __name__ == "__main__":
    unittest.main()
