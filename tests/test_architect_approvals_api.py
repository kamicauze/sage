import importlib
import os
import tempfile
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

    def _auth_disabled_env(self, store_path: str):
        return {
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
            "SAGE_APPROVALS_STORE_PATH": store_path,
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

        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "approvals-store.json")
            with patch.dict(os.environ, self._auth_disabled_env(store_path), clear=False):
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

        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "approvals-store.json")
            with patch.dict(os.environ, self._auth_disabled_env(store_path), clear=False):
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

        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "approvals-store.json")
            with patch.dict(os.environ, self._auth_disabled_env(store_path), clear=False):
                server_module = self._reload_server_module()
                with TestClient(server_module.app) as client:
                    create_resp = client.post("/approvals/proposals", json=payload)
                    proposal_id = create_resp.json()["proposal"]["id"]
                    first = client.post(f"/approvals/{proposal_id}/decision", json=decision)
                    second = client.post(f"/approvals/{proposal_id}/decision", json=decision)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)

    def test_create_proposal_from_orchestrator_event(self):
        payload = {
            "event_type": "pr_ready",
            "source": "sage.orchestrator",
            "risk": "medium",
            "task_id": "feat-custom-templates",
            "repo": "sage",
            "branch": "feat/custom-templates",
            "pr_number": 341,
            "checks_url": "https://example.invalid/checks/341",
            "estimated_cost_usd": 2.4,
        }

        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "approvals-store.json")
            with patch.dict(os.environ, self._auth_disabled_env(store_path), clear=False):
                server_module = self._reload_server_module()
                with TestClient(server_module.app) as client:
                    event_resp = client.post("/approvals/events", json=payload)
                    pending_resp = client.get("/approvals/pending")

        self.assertEqual(event_resp.status_code, 200)
        body = event_resp.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["created_from"], "orchestrator_event")
        proposal = body["proposal"]
        self.assertEqual(proposal["metadata"]["event_type"], "pr_ready")
        self.assertEqual(proposal["metadata"]["pr_number"], 341)
        self.assertGreaterEqual(len(proposal["actions"]), 1)
        self.assertEqual(pending_resp.status_code, 200)
        self.assertGreaterEqual(pending_resp.json()["count"], 1)

    def test_persists_proposals_across_server_reload(self):
        payload = {
            "title": "Persist me",
            "summary": "Verify proposal survives API restart",
            "source": "sage.test",
            "risk": "low",
            "actions": [{"type": "noop", "target": "proposal", "payload": {}}],
        }

        with tempfile.TemporaryDirectory() as td:
            store_path = os.path.join(td, "approvals-store.json")
            with patch.dict(os.environ, self._auth_disabled_env(store_path), clear=False):
                server_module = self._reload_server_module()
                with TestClient(server_module.app) as client:
                    create_resp = client.post("/approvals/proposals", json=payload)
                    proposal_id = create_resp.json()["proposal"]["id"]

                reloaded = self._reload_server_module()
                with TestClient(reloaded.app) as client:
                    get_resp = client.get(f"/approvals/{proposal_id}")

        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(get_resp.json()["proposal"]["id"], proposal_id)


if __name__ == "__main__":
    unittest.main()
