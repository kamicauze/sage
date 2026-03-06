import importlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class ProjectControlAPITests(unittest.TestCase):
    @staticmethod
    def _reload_server_module():
        import architect.api.server as server_module
        return importlib.reload(server_module)

    def _env(self, temp_dir: str):
        return {
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
            "SAGE_PROJECT_GIT_STORE_PATH": str(Path(temp_dir) / "git_registry.json"),
            "SAGE_PROJECT_CONTROL_CONFIG_PATH": str(Path(temp_dir) / "control_plane.json"),
            "SAGE_PROJECT_MIRROR_QUEUE_PATH": str(Path(temp_dir) / "mirror_queue.json"),
            "SAGE_NODE_ID": "mini",
            "SAGE_CODEX_CLI_CMD": "cat",
            "SAGE_CLAUDE_CLI_CMD": "cat",
        }

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

    def test_catalog_register_and_project_chat(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = self._create_repo(temp_dir)
            with patch.dict(os.environ, self._env(temp_dir), clear=False):
                server_module = self._reload_server_module()
                with TestClient(server_module.app) as client:
                    node_resp = client.post(
                        "/project-control/nodes",
                        json={"node_id": "mini", "transport": "local", "label": "Mini"},
                    )
                    register_resp = client.post(
                        "/project-control/projects/register",
                        json={"project_id": "babish", "repo_path": str(repo), "aliases": ["BaBish"]},
                    )
                    with patch(
                        "architect.api.routes.project_control.get_drive_file_metadata",
                        return_value={
                            "asset_id": "doc_123",
                            "title": "BaBish Spec",
                            "kind": "doc",
                            "url": "https://docs.google.com/document/d/doc_123/edit",
                            "mime_type": "application/vnd.google-apps.document",
                        },
                    ):
                        asset_resp = client.post(
                            "/project-control/projects/babish/google-assets",
                            json={
                                "drive_url": "https://docs.google.com/document/d/doc_123/edit",
                                "role": "spec",
                            },
                        )
                    catalog_resp = client.get("/project-control/catalog")
                    chat_resp = client.post(
                        "/project-control/chat",
                        json={
                            "message": "inspect repo",
                            "project_id": "babish",
                            "preferred_node": "mini",
                            "executor": "codex_cli",
                            "history": [{"role": "user", "content": "earlier"}],
                        },
                    )

        self.assertEqual(node_resp.status_code, 200)
        self.assertEqual(register_resp.status_code, 200)
        self.assertEqual(asset_resp.status_code, 200)
        self.assertEqual(catalog_resp.status_code, 200)
        catalog = catalog_resp.json()
        self.assertTrue(catalog["success"])
        self.assertEqual(catalog["projects"][0]["project_id"], "babish")
        self.assertEqual(catalog["projects"][0]["google_assets"][0]["title"], "BaBish Spec")

        self.assertEqual(chat_resp.status_code, 200)
        body = chat_resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["project_id"], "babish")
        self.assertEqual(body["node_id"], "mini")
        self.assertIn("inspect repo", body["reply"])


if __name__ == "__main__":
    unittest.main()
