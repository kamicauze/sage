import importlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ProjectGitIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        brain_runtime_path = os.path.join(repo_root, "apps", "brain-runtime")
        if brain_runtime_path not in sys.path:
            sys.path.insert(0, brain_runtime_path)

    def _load_module(self, store_path: str, node_id: str):
        with patch.dict(
            os.environ,
            {
                "SAGE_PROJECT_GIT_STORE_PATH": store_path,
                "SAGE_NODE_ID": node_id,
            },
            clear=False,
        ):
            import integrations.project_git as project_git

            return importlib.reload(project_git)

    def _create_repo(self, temp_dir: str, message: str) -> Path:
        repo_path = Path(temp_dir) / "demo_repo"
        repo_path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True, text=True)
        (repo_path / "README.md").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True, capture_output=True, text=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=Test User",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-m",
                message,
            ],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return repo_path

    def test_register_and_query_last_commit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = str(Path(temp_dir) / "git_registry.json")
            repo_path = self._create_repo(temp_dir, "initial commit")
            project_git = self._load_module(store_path, "macbook")
            with patch.dict(
                os.environ,
                {
                    "SAGE_PROJECT_GIT_STORE_PATH": store_path,
                    "SAGE_NODE_ID": "macbook",
                },
                clear=False,
            ):
                register_result = project_git.handle_project_git_text(
                    user_text=f"/git register autolist | {repo_path} | auto list, shopping app"
                )
                self.assertTrue(register_result["handled"])
                self.assertEqual(register_result["action"], "register")
                self.assertIn("Registered autolist on macbook", register_result["response_text"])

                query_result = project_git.handle_project_git_text(
                    user_text="what was my last commit on auto list on macbook?"
                )
                self.assertTrue(query_result["handled"])
                self.assertEqual(query_result["action"], "last_commit")
                self.assertIn("initial commit", query_result["response_text"])
                self.assertIn("autolist on macbook", query_result["response_text"])

    def test_sync_updates_snapshot_after_new_commit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = str(Path(temp_dir) / "git_registry.json")
            repo_path = self._create_repo(temp_dir, "initial commit")
            project_git = self._load_module(store_path, "macbook")
            with patch.dict(
                os.environ,
                {
                    "SAGE_PROJECT_GIT_STORE_PATH": store_path,
                    "SAGE_NODE_ID": "macbook",
                },
                clear=False,
            ):
                project_git.register_project("autolist", str(repo_path), aliases=["auto list"])

                (repo_path / "README.md").write_text("hello again\n", encoding="utf-8")
                subprocess.run(["git", "add", "README.md"], cwd=repo_path, check=True, capture_output=True, text=True)
                subprocess.run(
                    [
                        "git",
                        "-c",
                        "user.name=Test User",
                        "-c",
                        "user.email=test@example.com",
                        "commit",
                        "-m",
                        "second commit",
                    ],
                    cwd=repo_path,
                    check=True,
                    capture_output=True,
                    text=True,
                )

                sync_result = project_git.handle_project_git_text(user_text="/git sync autolist")
                self.assertTrue(sync_result["handled"])
                self.assertEqual(sync_result["action"], "sync")
                self.assertIn("second commit", sync_result["response_text"])

                last_result = project_git.handle_project_git_text(
                    user_text="what was my latest commit on autolist?"
                )
                self.assertIn("second commit", last_result["response_text"])

    def test_non_git_text_is_not_handled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store_path = str(Path(temp_dir) / "git_registry.json")
            project_git = self._load_module(store_path, "macbook")
            with patch.dict(
                os.environ,
                {
                    "SAGE_PROJECT_GIT_STORE_PATH": store_path,
                    "SAGE_NODE_ID": "macbook",
                },
                clear=False,
            ):
                result = project_git.handle_project_git_text(
                    user_text="tell me about my calendar tomorrow"
                )
                self.assertFalse(result["handled"])


if __name__ == "__main__":
    unittest.main()
