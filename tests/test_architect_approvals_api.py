import importlib
import os
import unittest
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency in test env
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class ArchitectApprovalsAPITests(unittest.TestCase):
    @staticmethod
    def _reload_server_module():
        import architect.api.server as server_module
        return importlib.reload(server_module)

    def _auth_disabled_env(self):
        return {
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
        }

    def test_create_and_list_pending_proposals(self):
        payload = {
            "title": "Switch local model",
            "summary": "Switch LOCAL route from gemma to qwen",
            "source": "sage.research",
            "risk": "high",
            "actions": [
                {
                    "type": "model_switch",
                    "target": "ollama/qwen2.5:14b",
                    "payload": {"route": "LOCAL"},
                }
            ],
            "metadata": {"candidate_id": "cand-001"},
            "expires_in_seconds": 600,
        }

        with patch.dict(os.environ, self._auth_disabled_env(), clear=False):
            server_module = self._reload_server_module()
            with TestClient(server_module.app) as client:
                create_resp = client.post("/approvals/proposals", json=payload)
                pending_resp = client.get("/approvals/pending")

        self.assertEqual(create_resp.status_code, 200)
        self.assertTrue(create_resp.json()["success"])
        self.assertEqual(pending_resp.status_code, 200)
        self.assertGreaterEqual(pending_resp.json()["count"], 1)

    def test_decision_transitions_proposal_out_of_pending(self):
        payload = {
            "title": "Create n8n workflow",
            "summary": "Provision weekly summary workflow",
            "risk": "medium",
            "actions": [{"type": "workflow_create", "target": "weekly-summary", "payload": {}}],
        }
        decision = {
            "decision": "approve",
            "reviewer": "mobile_user",
            "reason": "Looks safe",
        }

        with patch.dict(os.environ, self._auth_disabled_env(), clear=False):
            server_module = self._reload_server_module()
            with TestClient(server_module.app) as client:
                create_resp = client.post("/approvals/proposals", json=payload)
                proposal_id = create_resp.json()["proposal"]["id"]

                decide_resp = client.post(f"/approvals/{proposal_id}/decision", json=decision)
                get_resp = client.get(f"/approvals/{proposal_id}")
                pending_resp = client.get("/approvals/pending")

        self.assertEqual(decide_resp.status_code, 200)
        self.assertEqual(decide_resp.json()["proposal"]["status"], "approved")
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["proposal"]["status"], "approved")
        pending_ids = [item["id"] for item in pending_resp.json()["items"]]
        self.assertNotIn(proposal_id, pending_ids)

    def test_second_decision_on_resolved_proposal_returns_conflict(self):
        payload = {
            "title": "Dangerous action",
            "summary": "Delete old data",
            "risk": "critical",
            "actions": [{"type": "delete", "target": "memory_collection", "payload": {}}],
        }
        decision = {"decision": "deny", "reviewer": "mobile_user"}

        with patch.dict(os.environ, self._auth_disabled_env(), clear=False):
            server_module = self._reload_server_module()
            with TestClient(server_module.app) as client:
                create_resp = client.post("/approvals/proposals", json=payload)
                proposal_id = create_resp.json()["proposal"]["id"]
                first = client.post(f"/approvals/{proposal_id}/decision", json=decision)
                second = client.post(f"/approvals/{proposal_id}/decision", json=decision)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)


if __name__ == "__main__":
    unittest.main()

