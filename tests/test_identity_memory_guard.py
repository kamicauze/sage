import os
import sys
import unittest
import importlib.util


class _StubMemory:
    def __init__(self, facts):
        self._facts = facts

    def recall_facts(self, **kwargs):
        return self._facts


class IdentityMemoryGuardTests(unittest.TestCase):
    def setUp(self):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        brain_path = os.path.join(repo_root, "brain")
        if brain_path not in sys.path:
            sys.path.insert(0, brain_path)

    def _load_module(self, module_name: str, relative_path: str):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        module_path = os.path.join(repo_root, relative_path)
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        return module

    def test_distiller_skips_swahili_identity_question(self):
        distiller = self._load_module(
            "test_distiller_module",
            "apps/brain-runtime/memory/distiller.py",
        )

        facts = distiller.extract_identity_realtime("mimi ni nani")
        names = [fact["value"].lower() for fact in facts if fact["type"] == "name"]
        self.assertNotIn("nani", names)

    def test_distiller_keeps_valid_name_disclosure(self):
        distiller = self._load_module(
            "test_distiller_module2",
            "apps/brain-runtime/memory/distiller.py",
        )

        facts = distiller.extract_identity_realtime("my name is Martin Ngigi")
        names = [fact["value"] for fact in facts if fact["type"] == "name"]
        self.assertIn("Martin Ngigi", names)

    def test_distiller_rejects_connector_name_fragment(self):
        distiller = self._load_module(
            "test_distiller_module3",
            "apps/brain-runtime/memory/distiller.py",
        )

        facts = distiller.extract_identity_realtime("my name is Marto or Martin")
        names = [fact["value"].lower() for fact in facts if fact["type"] == "name"]
        self.assertNotIn("marto or", names)

    def test_recall_ignores_invalid_name_fact(self):
        recall = self._load_module(
            "test_recall_module",
            "apps/brain-runtime/memory/recall.py",
        )

        facts = [
            {"content": "User's name is nani", "metadata": {"confidence": 0.95}},
            {"content": "User's name is martin ngigi", "metadata": {"confidence": 0.95}},
        ]

        identity = recall.RecallEngine(memory=_StubMemory(facts)).get_user_identity()
        self.assertEqual(identity.get("name"), "Martin Ngigi")

    def test_recall_ignores_name_with_connector_tokens(self):
        recall = self._load_module(
            "test_recall_module2",
            "apps/brain-runtime/memory/recall.py",
        )

        facts = [
            {"content": "User's name is marto or", "metadata": {"confidence": 0.95}},
            {"content": "User's name is marto", "metadata": {"confidence": 0.95}},
        ]

        identity = recall.RecallEngine(memory=_StubMemory(facts)).get_user_identity()
        self.assertEqual(identity.get("name"), "Marto")

    def test_recall_salvages_first_token_from_legacy_bad_name(self):
        recall = self._load_module(
            "test_recall_module3",
            "apps/brain-runtime/memory/recall.py",
        )

        facts = [
            {"content": "User's name is marto or", "metadata": {"confidence": 1.0}},
        ]

        identity = recall.RecallEngine(memory=_StubMemory(facts)).get_user_identity()
        self.assertEqual(identity.get("name"), "Marto")


if __name__ == "__main__":
    unittest.main()
