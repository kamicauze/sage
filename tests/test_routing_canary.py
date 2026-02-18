import os
import tempfile
import unittest
from unittest.mock import patch

from shared.routing import UnifiedRouter


class CanaryRoutingTests(unittest.TestCase):
    @staticmethod
    def _policy():
        return {
            "routing_thresholds": {"hybrid_score": 4, "cloud_score": 8},
            "models": {
                "local": "ollama/gemma3:12b",
                "plan_hybrid": "google/gemini-1.5-pro",
                "plan_cloud": "google/gemini-1.5-pro",
                "code_medium": "anthropic/claude-sonnet-4.5",
                "code_cloud": "anthropic/claude-opus-4.5",
                "chat_cloud": "xai/grok-beta",
            },
        }

    def test_canary_overrides_local_model_at_100_percent(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = {
                "SAGE_LLM_REGISTRY_PATH": os.path.join(tmp_dir, "missing_registry.json"),
                "SAGE_CANARY_ENABLED": "true",
                "SAGE_CANARY_PERCENT": "100",
                "SAGE_CANARY_MODEL": "ollama/qwen2.5:14b",
                "SAGE_CANARY_ROUTES": "LOCAL",
                "SAGE_CANARY_TASK_TYPES": "",
                "SAGE_CANARY_SALT": "test-salt",
            }
            with patch.dict(os.environ, env, clear=False):
                router = UnifiedRouter(self._policy())
                decision = router.route("hello there", task_type="chat", rag_docs=[])

        self.assertEqual(decision.route, "LOCAL")
        self.assertEqual(decision.provider, "ollama")
        self.assertEqual(decision.model, "qwen2.5:14b")
        self.assertIn("canary override", decision.reason.lower())

    def test_canary_respects_route_filter(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = {
                "SAGE_LLM_REGISTRY_PATH": os.path.join(tmp_dir, "missing_registry.json"),
                "SAGE_CANARY_ENABLED": "true",
                "SAGE_CANARY_PERCENT": "100",
                "SAGE_CANARY_MODEL": "ollama/qwen2.5:14b",
                "SAGE_CANARY_ROUTES": "LOCAL",
                "SAGE_CANARY_TASK_TYPES": "",
                "SAGE_CANARY_SALT": "test-salt",
            }
            with patch.dict(os.environ, env, clear=False):
                router = UnifiedRouter(self._policy())
                decision = router.route(
                    "think hard refactor architecture migration redesign",
                    task_type="code",
                    rag_docs=[]
                )

        self.assertEqual(decision.route, "CLOUD")
        self.assertEqual(decision.provider, "anthropic")
        self.assertEqual(decision.model, "claude-opus-4.5")
        self.assertNotIn("canary override", decision.reason.lower())

    def test_canary_respects_task_type_filter(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = {
                "SAGE_LLM_REGISTRY_PATH": os.path.join(tmp_dir, "missing_registry.json"),
                "SAGE_CANARY_ENABLED": "true",
                "SAGE_CANARY_PERCENT": "100",
                "SAGE_CANARY_MODEL": "ollama/qwen2.5:14b",
                "SAGE_CANARY_ROUTES": "LOCAL",
                "SAGE_CANARY_TASK_TYPES": "code",
                "SAGE_CANARY_SALT": "test-salt",
            }
            with patch.dict(os.environ, env, clear=False):
                router = UnifiedRouter(self._policy())
                decision = router.route("hello there", task_type="chat", rag_docs=[])

        self.assertEqual(decision.route, "LOCAL")
        self.assertEqual(decision.provider, "ollama")
        self.assertEqual(decision.model, "gemma3:12b")
        self.assertNotIn("canary override", decision.reason.lower())

    def test_canary_assignment_is_deterministic_for_same_query(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            env = {
                "SAGE_LLM_REGISTRY_PATH": os.path.join(tmp_dir, "missing_registry.json"),
                "SAGE_CANARY_ENABLED": "true",
                "SAGE_CANARY_PERCENT": "50",
                "SAGE_CANARY_MODEL": "ollama/qwen2.5:14b",
                "SAGE_CANARY_ROUTES": "LOCAL",
                "SAGE_CANARY_TASK_TYPES": "",
                "SAGE_CANARY_SALT": "test-salt",
            }
            with patch.dict(os.environ, env, clear=False):
                router = UnifiedRouter(self._policy())
                decision1 = router.route("same query every time", task_type="chat", rag_docs=[])
                decision2 = router.route("same query every time", task_type="chat", rag_docs=[])

        self.assertEqual(decision1.route, decision2.route)
        self.assertEqual(decision1.provider, decision2.provider)
        self.assertEqual(decision1.model, decision2.model)
        self.assertEqual(decision1.reason, decision2.reason)


if __name__ == "__main__":
    unittest.main()
