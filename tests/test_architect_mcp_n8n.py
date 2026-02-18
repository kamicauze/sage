import importlib
import os
import unittest
from unittest.mock import AsyncMock, patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency in test env
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class ArchitectMCPN8NTests(unittest.TestCase):
    @staticmethod
    def _reload_server_module():
        import architect.api.server as server_module
        return importlib.reload(server_module)

    def test_create_workflow_requires_explicit_confirmation(self):
        env = {
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }
        payload = {
            "name": "Daily Briefing",
            "nodes": [{"id": "1", "name": "Manual Trigger"}],
            "connections": {},
            "active": False,
            "confirm_create": False,
        }

        with patch.dict(os.environ, env, clear=False):
            server_module = self._reload_server_module()
            with TestClient(server_module.app) as client:
                response = client.post("/mcp/n8n/workflows/create", json=payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn("confirm_create=true", response.json()["error"])

    def test_create_workflow_calls_n8n_client_when_confirmed(self):
        env = {
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }
        payload = {
            "name": "Daily Briefing",
            "nodes": [{"id": "1", "name": "Manual Trigger"}],
            "connections": {},
            "active": True,
            "confirm_create": True,
        }
        mocked_result = {"success": True, "workflow_id": "wf_123"}

        with patch.dict(os.environ, env, clear=False):
            server_module = self._reload_server_module()
            with patch(
                "architect.api.routes.mcp.mcp.n8n.create_workflow",
                new=AsyncMock(return_value=mocked_result),
            ) as create_mock:
                with TestClient(server_module.app) as client:
                    response = client.post("/mcp/n8n/workflows/create", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mocked_result)
        create_mock.assert_awaited_once_with(
            "Daily Briefing",
            [{"id": "1", "name": "Manual Trigger"}],
            {},
            active=True,
        )

    def test_execute_workflow_by_id_uses_n8n_client(self):
        env = {
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }
        payload = {
            "workflow_id": "wf_123",
            "data": {"topic": "daily_briefing"},
        }
        mocked_result = {"success": True, "execution_id": "exec_456"}

        with patch.dict(os.environ, env, clear=False):
            server_module = self._reload_server_module()
            with patch(
                "architect.api.routes.mcp.mcp.n8n.trigger_workflow_by_id",
                new=AsyncMock(return_value=mocked_result),
            ) as trigger_mock:
                with TestClient(server_module.app) as client:
                    response = client.post("/mcp/n8n/workflows/execute", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), mocked_result)
        trigger_mock.assert_awaited_once_with("wf_123", {"topic": "daily_briefing"})


if __name__ == "__main__":
    unittest.main()
