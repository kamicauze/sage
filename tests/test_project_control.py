import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ProjectControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        brain_runtime_path = os.path.join(repo_root, "apps", "brain-runtime")
        if brain_runtime_path not in sys.path:
            sys.path.insert(0, brain_runtime_path)

    def _load_modules(self, temp_dir: str):
        env = {
            "SAGE_PROJECT_GIT_STORE_PATH": str(Path(temp_dir) / "git_registry.json"),
            "SAGE_PROJECT_CONTROL_CONFIG_PATH": str(Path(temp_dir) / "control_plane.json"),
            "SAGE_PROJECT_MIRROR_QUEUE_PATH": str(Path(temp_dir) / "mirror_queue.json"),
            "SAGE_NODE_ID": "mini",
            "SAGE_CODEX_CLI_CMD": "cat",
            "SAGE_CLAUDE_CLI_CMD": "cat",
        }
        with patch.dict(os.environ, env, clear=False):
            import shared.project_control as project_control
            import integrations.project_mirror as project_mirror

            return importlib.reload(project_control), importlib.reload(project_mirror), env

    def _create_repo(self, temp_dir: str) -> Path:
        repo = Path(temp_dir) / "repo"
        repo.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
        (repo / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo, check=True, capture_output=True, text=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test User",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-m",
                "initial commit",
            ],
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        )
        return repo

    def test_register_status_and_project_chat(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_control, _, env = self._load_modules(temp_dir)
            repo = self._create_repo(temp_dir)
            with patch.dict(os.environ, env, clear=False):
                project_control.upsert_node("mini", {"transport": "local", "label": "Mini"})
                project = project_control.register_or_update_project("babish", str(repo), aliases=["BaBish"], node_id="mini")
                project_control.upsert_project_google_asset(
                    "babish",
                    {
                        "asset_id": "doc_123",
                        "title": "BaBish Spec",
                        "kind": "doc",
                        "url": "https://docs.google.com/document/d/doc_123/edit",
                        "role": "spec",
                    },
                )

                self.assertEqual(project["project_id"], "babish")
                status = project_control.project_status("babish", "mini")
                self.assertEqual(status["node_id"], "mini")
                self.assertIn(status["branch"], {"main", "master"})
                self.assertIn("initial commit", status["head"])
                self.assertEqual(len(status["google_assets"]), 1)

                chat = project_control.run_project_chat(
                    project_id="babish",
                    preferred_node="mini",
                    provider="codex_cli",
                    message="summarize repo state",
                    history=[{"role": "user", "content": "previous"}],
                )
                self.assertEqual(chat["node_id"], "mini")
                self.assertIn("[PROJECT] babish on mini", chat["reply"])
                self.assertIn("[DOCS]", chat["reply"])
                self.assertIn("BaBish Spec", chat["reply"])
                self.assertIn("summarize repo state", chat["reply"])

    def test_build_chat_prompt_inlines_google_doc_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_control, _, env = self._load_modules(temp_dir)
            repo = self._create_repo(temp_dir)
            with patch.dict(
                os.environ,
                {
                    **env,
                    "SAGE_ARCHITECT_API_URL": "http://127.0.0.1:8000",
                    "SAGE_PROJECT_DOC_INLINE_COUNT": "1",
                    "SAGE_PROJECT_DOC_INLINE_CHARS": "128",
                },
                clear=False,
            ):
                project_control.upsert_node("mini", {"transport": "local", "label": "Mini"})
                project_control.register_or_update_project("babish", str(repo), aliases=["BaBish"], node_id="mini")
                project_control.upsert_project_google_asset(
                    "babish",
                    {
                        "asset_id": "doc_123",
                        "title": "BaBish Spec",
                        "kind": "doc",
                        "url": "https://docs.google.com/document/d/doc_123/edit",
                        "role": "spec",
                        "source": "google_drive",
                    },
                )
                status = project_control.project_status("babish", "mini")

                class _FakeResponse:
                    ok = True

                    @staticmethod
                    def json():
                        return {
                            "success": True,
                            "content_available": True,
                            "content": "This spec says the checkout flow must support emergency hotfixes.",
                        }

                with patch("shared.project_control.requests.get", return_value=_FakeResponse()):
                    prompt = project_control.build_chat_prompt(
                        "what matters here?",
                        history=[{"role": "user", "content": "earlier"}],
                        status=status,
                    )

                self.assertIn("[DOC CONTENT] BaBish Spec role=spec", prompt)
                self.assertIn("checkout flow must support emergency hotfixes", prompt)

    def test_mirror_hook_install_and_queue_on_failure(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_control, project_mirror, env = self._load_modules(temp_dir)
            repo = self._create_repo(temp_dir)
            with patch.dict(os.environ, env, clear=False):
                project_control.upsert_node("mini", {"transport": "local", "label": "Mini"})
                hook_path = project_mirror.install_post_commit_hook(
                    project_id="babish",
                    repo_path=str(repo),
                    source_node="macbook",
                    target_node="mini",
                )
                self.assertTrue(hook_path.exists())
                hook_body = hook_path.read_text(encoding="utf-8")
                self.assertIn("post-commit", hook_body)
                self.assertIn("SAGE_PROJECT_GIT_STORE_PATH", hook_body)

                plist = project_mirror.build_launchd_plist(
                    label="com.sage.project-mirror",
                    interval_seconds=300,
                    source_node="macbook",
                )
                self.assertIn("EnvironmentVariables", plist)
                self.assertIn("SAGE_PROJECT_CONTROL_CONFIG_PATH", plist)

                with patch("integrations.project_mirror.handoff_project", side_effect=RuntimeError("offline")):
                    result = project_mirror.post_commit_mirror(
                        project_id="babish",
                        repo_path=str(repo),
                        source_node="macbook",
                        target_node="mini",
                    )

                self.assertEqual(result["status"], "queued")
                queue = project_control.load_mirror_queue()
                self.assertEqual(len(queue["items"]), 1)

    def test_sync_project_snapshot_from_ssh_node(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_control, _, env = self._load_modules(temp_dir)
            with patch.dict(os.environ, env, clear=False):
                project_control.upsert_node(
                    "macbook",
                    {
                        "transport": "ssh",
                        "ssh_host": "martins-macbook-pro.tail68fc8e.ts.net",
                        "ssh_user": "martinngigi",
                        "ssh_command": "ssh -i ~/.ssh/id_ed25519_sage_tb",
                    },
                )

                def fake_run(node_id, spec, *, argv, repo_path=None, stdin_text=None, timeout_sec=None):
                    command = tuple(argv)
                    outputs = {
                        ("git", "rev-parse", "--is-inside-work-tree"): "true",
                        ("pwd", "-P"): "/Users/martinngigi/Documents/BaBish",
                        ("git", "status", "--short", "--untracked-files=no"): " M app.py\n",
                        ("git", "rev-parse", "--abbrev-ref", "HEAD"): "staging",
                        ("git", "rev-parse", "--short", "HEAD"): "5457d2c",
                        ("git", "log", "-1", "--pretty=%s"): "Initial commit",
                        ("git", "log", "-1", "--pretty=%an"): "martinngigi",
                        ("git", "log", "-1", "--date=iso-strict", "--pretty=%cI"): "2025-04-01T08:32:41+03:00",
                        ("git", "remote", "get-url", "origin"): "git@github.com:kamicauze/BaBish.git",
                    }
                    stdout = outputs.get(command, "")
                    success = command in outputs
                    return {
                        "node_id": node_id,
                        "transport": spec.get("transport"),
                        "argv": list(argv),
                        "returncode": 0 if success else 1,
                        "stdout": stdout,
                        "stderr": "" if success else "unknown command",
                        "success": success,
                    }

                with patch.object(project_control, "run_command_on_node", side_effect=fake_run):
                    project = project_control.sync_project_snapshot(
                        "babish",
                        "~/Documents/BaBish",
                        aliases=["BaBish"],
                        node_id="macbook",
                    )

                snapshot = project["nodes"]["macbook"]
                self.assertEqual(snapshot["path"], "/Users/martinngigi/Documents/BaBish")
                self.assertEqual(snapshot["branch"], "staging")
                self.assertEqual(snapshot["head_sha"], "5457d2c")
                self.assertTrue(snapshot["dirty"])
                self.assertEqual(snapshot["dirty_count"], 1)

    def test_project_status_falls_back_when_dirty_probe_times_out(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project_control, _, env = self._load_modules(temp_dir)
            with patch.dict(os.environ, env, clear=False):
                project_control.upsert_node(
                    "macbook",
                    {
                        "transport": "ssh",
                        "ssh_host": "martins-macbook-pro.tail68fc8e.ts.net",
                        "ssh_user": "martinngigi",
                        "ssh_command": "ssh -i ~/.ssh/id_ed25519_sage_tb",
                    },
                )

                snapshot = {
                    "node_id": "macbook",
                    "path": "/Users/martinngigi/Documents/BaBish",
                    "branch": "staging",
                    "head_sha": "5457d2c",
                    "head_subject": "Initial commit",
                    "head_author": "martinngigi",
                    "head_time": "2025-04-01T08:32:41+03:00",
                    "dirty": True,
                    "dirty_count": 42,
                    "remote_url": "",
                    "last_seen": "2026-03-03T00:00:00+00:00",
                }
                project_control._save_project_snapshot("babish", snapshot, aliases=["BaBish"])

                def fake_run(node_id, spec, *, argv, repo_path=None, stdin_text=None, timeout_sec=None):
                    command = tuple(argv)
                    outputs = {
                        ("/usr/bin/env", "true"): {"success": True, "stdout": "", "stderr": "", "returncode": 0},
                        ("git", "branch", "--show-current"): {"success": True, "stdout": "staging", "stderr": "", "returncode": 0},
                        ("git", "log", "-1", "--pretty=%H%x09%s%x09%cI"): {
                            "success": True,
                            "stdout": "5457d2cde81df1b3b34d7e3815724fdcb28bd1bf\tInitial commit\t2025-04-01T08:32:41+03:00",
                            "stderr": "",
                            "returncode": 0,
                        },
                        ("git", "status", "--short", "--untracked-files=no"): {
                            "success": False,
                            "stdout": "",
                            "stderr": "Command timed out after 5.0s",
                            "returncode": 124,
                            "timeout": True,
                        },
                    }
                    result = outputs[command]
                    return {
                        "node_id": node_id,
                        "transport": spec.get("transport"),
                        "argv": list(argv),
                        **result,
                    }

                with patch.object(project_control, "run_command_on_node", side_effect=fake_run):
                    status = project_control.project_status("babish", "macbook")

                self.assertEqual(status["node_id"], "macbook")
                self.assertEqual(status["dirty_count"], 42)
                self.assertIsNone(status["dirty"])
                self.assertIn("timed out", status["dirty_probe_error"])


if __name__ == "__main__":
    unittest.main()
