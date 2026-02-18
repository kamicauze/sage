import importlib
import os
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency in test env
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class ArchitectChatAPITests(unittest.TestCase):
    @staticmethod
    def _reload_server_module():
        import architect.api.server as server_module
        return importlib.reload(server_module)

    def _auth_disabled_env(self):
        return {
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }

    def test_chat_creates_conversation_and_returns_reply(self):
        payload = {"message": "Hello Sage"}

        with patch.dict(os.environ, self._auth_disabled_env(), clear=False):
            server_module = self._reload_server_module()
            with patch("architect.api.routes.chat._llm_client.chat", return_value="Hello human"):
                with TestClient(server_module.app) as client:
                    response = client.post("/chat", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["reply"], "Hello human")
        self.assertTrue(body["conversation_id"])

    def test_chat_history_and_delete(self):
        with patch.dict(os.environ, self._auth_disabled_env(), clear=False):
            server_module = self._reload_server_module()
            with patch("architect.api.routes.chat._llm_client.chat", return_value="First reply"):
                with TestClient(server_module.app) as client:
                    first = client.post("/chat", json={"message": "First"})
                    conversation_id = first.json()["conversation_id"]

            with patch("architect.api.routes.chat._llm_client.chat", return_value="Second reply"):
                with TestClient(server_module.app) as client:
                    second = client.post(
                        "/chat",
                        json={"message": "Second", "conversation_id": conversation_id},
                    )
                    history = client.get(f"/chat/{conversation_id}")
                    delete_resp = client.delete(f"/chat/{conversation_id}")
                    missing = client.get(f"/chat/{conversation_id}")

        self.assertEqual(second.status_code, 200)
        self.assertEqual(history.status_code, 200)
        self.assertGreaterEqual(history.json()["message_count"], 4)
        self.assertEqual(delete_resp.status_code, 200)
        self.assertEqual(missing.status_code, 404)

    def test_chat_brain_provider_uses_mqtt_bridge(self):
        payload = {"message": "Use brain path", "provider": "brain"}
        mock_bridge_response = {
            "success": True,
            "text": "Brain runtime reply",
            "model": "brain_runtime",
        }

        with patch.dict(os.environ, self._auth_disabled_env(), clear=False):
            server_module = self._reload_server_module()
            with patch(
                "architect.api.routes.chat._chat_via_brain_mqtt",
                return_value=mock_bridge_response,
            ):
                with TestClient(server_module.app) as client:
                    response = client.post("/chat", json=payload)

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["provider"], "brain")
        self.assertEqual(body["reply"], "Brain runtime reply")


if __name__ == "__main__":
    unittest.main()
