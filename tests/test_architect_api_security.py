import importlib
import os
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency in test env
    TestClient = None


class DummyMemory:
    def ingest(self, manifest, file_path):
        return None


class DummyRouterResult:
    status = "SUCCESS"
    artifacts = []
    summary = "ok"
    details = {"timing": {"duration_ms": 1}}


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class ArchitectAPISecurityTests(unittest.TestCase):
    @staticmethod
    def _reload_server_module():
        import architect.api.server as server_module
        return importlib.reload(server_module)

    def test_auth_required_rejects_unauthenticated_request(self):
        env = {
            "SAGE_ARCHITECT_API_TOKEN": "unit-test-token",
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "true",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }
        with patch.dict(os.environ, env, clear=False):
            server_module = self._reload_server_module()
            with TestClient(server_module.app) as client:
                response = client.get("/stats/usage")

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["error"], "Unauthorized")
        self.assertEqual(body["detail"], "Missing or invalid API token")

    def test_auth_required_accepts_valid_bearer_token(self):
        env = {
            "SAGE_ARCHITECT_API_TOKEN": "unit-test-token",
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "true",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }
        with patch.dict(os.environ, env, clear=False):
            server_module = self._reload_server_module()
            with TestClient(server_module.app) as client:
                response = client.get(
                    "/stats/usage",
                    headers={"Authorization": "Bearer unit-test-token"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Architect-Auth-Required"), "true")

    def test_builds_plan_rejects_manifest_path_traversal(self):
        env = {
            "SAGE_ARCHITECT_API_TOKEN": "",
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }
        with patch.dict(os.environ, env, clear=False):
            server_module = self._reload_server_module()
            with TestClient(server_module.app) as client:
                response = client.post(
                    "/builds/plan",
                    json={
                        "query": "do something",
                        "request_type": "feature",
                        "manifest_path": "../../etc/passwd",
                    },
                )

        self.assertEqual(response.status_code, 400)
        self.assertIn("path traversal", response.json()["error"])

    def test_memory_ingest_rejects_outside_repo_file_path(self):
        env = {
            "SAGE_ARCHITECT_API_TOKEN": "",
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }
        with patch.dict(os.environ, env, clear=False):
            server_module = self._reload_server_module()
            with patch("architect.api.routes.memory.ArchitectMemory", DummyMemory):
                with TestClient(server_module.app) as client:
                    response = client.post(
                        "/memory/ingest",
                        json={
                            "manifest_path": "apps/architect-studio/projects/sage.yaml",
                            "file_paths": ["../../etc/passwd"],
                        },
                    )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["ingested_count"], 0)
        self.assertEqual(body["failed_count"], 1)
        self.assertIn("path traversal", body["failed_files"][0]["error"])

    def test_response_includes_generated_correlation_header(self):
        env = {
            "SAGE_ARCHITECT_API_TOKEN": "",
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }
        with patch.dict(os.environ, env, clear=False):
            server_module = self._reload_server_module()
            with TestClient(server_module.app) as client:
                response = client.get("/stats/health")

        self.assertEqual(response.status_code, 200)
        header_value = response.headers.get("X-Architect-Correlation-Id")
        self.assertTrue(header_value)
        self.assertTrue(header_value.startswith("req_"))

    def test_request_correlation_header_propagates_to_router(self):
        env = {
            "SAGE_ARCHITECT_API_TOKEN": "",
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }
        seen: dict[str, str] = {}

        class DummyRouter:
            def __init__(self, *args, **kwargs):
                pass

            def process_request(self, request):
                seen["correlation_id"] = request.correlation_id
                return DummyRouterResult()

            @property
            def memory(self):
                class _M:
                    @staticmethod
                    def query(*args, **kwargs):
                        return {"documents": [], "metadatas": []}
                return _M()

        with patch.dict(os.environ, env, clear=False):
            server_module = self._reload_server_module()
            with patch("architect.api.routes.builds.ArchitectRouter", DummyRouter):
                with TestClient(server_module.app) as client:
                    response = client.post(
                        "/builds/plan",
                        headers={"X-Architect-Correlation-Id": "cid_unit_test_123"},
                        json={
                            "query": "quick docs tweak",
                            "request_type": "feature",
                            "manifest_path": "apps/architect-studio/projects/sage.yaml",
                        },
                    )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Architect-Correlation-Id"), "cid_unit_test_123")
        self.assertEqual(seen.get("correlation_id"), "cid_unit_test_123")


if __name__ == "__main__":
    unittest.main()
