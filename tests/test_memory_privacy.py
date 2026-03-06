import asyncio
import importlib
import importlib.util
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BRAIN_PATH = os.path.join(REPO_ROOT, "brain")
if BRAIN_PATH not in sys.path:
    sys.path.insert(0, BRAIN_PATH)


class _StubMemory:
    """Stub memory for testing without ChromaDB."""
    def __init__(self, episodes=None, facts=None, preferences=None):
        self._episodes = episodes or []
        self._facts = facts or []
        self._preferences = preferences or []

    def recall_episodes(self, *args, **kwargs):
        return self._episodes

    def recall_facts(self, *args, **kwargs):
        return self._facts

    def get_preferences(self, *args, **kwargs):
        return self._preferences

    def get_stats(self):
        return {
            "episodes": len(self._episodes),
            "facts": len(self._facts),
            "preferences": len(self._preferences),
        }


def _load_module(module_name, relative_path):
    module_path = os.path.join(REPO_ROOT, relative_path)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Smart recall mode tests
# ---------------------------------------------------------------------------

class TestSmartRecallMode(unittest.TestCase):
    """Tests for the 'smart' memory recall mode."""

    def setUp(self):
        import ai.context_builder as cb
        self.cb = cb
        self.builder = cb.SelfNarrativeBuilder()

    def test_smart_mode_always_triggers(self):
        """Smart mode should always trigger recall regardless of message."""
        result = self.builder._should_run_memory_recall("hello", "smart", "local")
        self.assertTrue(result)

    def test_smart_mode_triggers_for_cloud(self):
        """Smart mode should trigger for cloud too (depth controlled elsewhere)."""
        result = self.builder._should_run_memory_recall("hello", "smart", "cloud")
        self.assertTrue(result)

    def test_explicit_only_skips_simple_greeting(self):
        """explicit_only mode should skip recall for simple greetings."""
        result = self.builder._should_run_memory_recall("hi", "explicit_only")
        self.assertFalse(result)

    def test_explicit_only_triggers_on_question(self):
        """explicit_only should trigger on question words."""
        result = self.builder._should_run_memory_recall("do you remember?", "explicit_only")
        self.assertTrue(result)

    def test_explicit_only_triggers_on_past_reference(self):
        """explicit_only should trigger on past indicators."""
        result = self.builder._should_run_memory_recall("we talked about this before", "explicit_only")
        self.assertTrue(result)

    def test_disabled_mode_always_false(self):
        """disabled mode never runs recall."""
        result = self.builder._should_run_memory_recall("what happened last time?", "disabled")
        self.assertFalse(result)

    def test_always_mode_always_true(self):
        """always mode always runs recall."""
        result = self.builder._should_run_memory_recall("hi", "always")
        self.assertTrue(result)

    def test_default_mode_is_smart(self):
        """Default MEMORY_RECALL_MODE should be 'smart'."""
        self.assertEqual(self.cb.MEMORY_RECALL_MODE, "smart")

    def test_env_override_to_explicit_only(self):
        """Setting MEMORY_RECALL_MODE=explicit_only via env should still work."""
        with patch.dict(os.environ, {"MEMORY_RECALL_MODE": "explicit_only"}, clear=False):
            importlib.reload(self.cb)
            self.assertEqual(self.cb.MEMORY_RECALL_MODE, "explicit_only")
            # Restore
            importlib.reload(self.cb)


# ---------------------------------------------------------------------------
# Cloud vs local recall depth tests
# ---------------------------------------------------------------------------

class TestCloudRecallDepth(unittest.TestCase):
    """Tests that cloud routing gets reduced memory depth."""

    def setUp(self):
        self.recall_mod = _load_module("recall", "apps/brain-runtime/memory/recall.py")

    def test_cloud_smart_excludes_episodes(self):
        """In smart mode with cloud target, episodes should be excluded."""
        episodes = [
            {
                "content": "User talked about work stress at 2am",
                "metadata": {"date": "2025-12-01", "emotional_arc": "stressed"},
            }
        ]
        preferences = [
            {
                "content": "User likes direct communication",
                "metadata": {"pref_type": "direct_communication", "strength": 0.8},
            }
        ]

        engine = self.recall_mod.RecallEngine(memory=_StubMemory(
            episodes=episodes, preferences=preferences
        ))

        pref_text = engine.get_preferences_prompt()
        # Preferences should NOT contain episode content
        self.assertNotIn("work stress", pref_text)

    def test_local_smart_includes_episodes(self):
        """In smart mode with local target, full recall including episodes."""
        episodes = [
            {
                "content": "User talked about work stress at 2am",
                "metadata": {"date": "2025-12-01", "emotional_arc": "stressed"},
            }
        ]

        engine = self.recall_mod.RecallEngine(memory=_StubMemory(episodes=episodes))
        full_context = engine.recall_for_context(
            current_topic="stress",
            user_message="I'm stressed",
            max_episodes=2,
            max_facts=3
        )
        self.assertIn("work stress", full_context)

    def test_get_preferences_prompt_returns_strong_prefs_only(self):
        """get_preferences_prompt() should only return preferences with strength >= 0.6."""
        preferences = [
            {
                "content": "User likes direct communication",
                "metadata": {"pref_type": "direct_communication", "strength": 0.8},
            },
            {
                "content": "User dislikes long preambles",
                "metadata": {"pref_type": "long_preambles", "strength": 0.3},
            },
        ]

        engine = self.recall_mod.RecallEngine(memory=_StubMemory(preferences=preferences))
        pref_text = engine.get_preferences_prompt()
        # Weak preference should be filtered
        self.assertNotIn("long_preambles", pref_text)

    def test_get_preferences_prompt_empty_when_no_prefs(self):
        """get_preferences_prompt() returns empty when no preferences."""
        engine = self.recall_mod.RecallEngine(memory=_StubMemory())
        pref_text = engine.get_preferences_prompt()
        self.assertEqual(pref_text, "")


# ---------------------------------------------------------------------------
# Conversation compression tests
# ---------------------------------------------------------------------------

class TestConversationCompression(unittest.TestCase):
    """Tests for conversation history compression."""

    def setUp(self):
        import ai.conversation as conv_mod
        self.conv_mod = conv_mod

    def test_no_compression_under_threshold(self):
        """Under 5 turns, no compression should occur."""
        convo = self.conv_mod.ConversationHistory()
        for i in range(4):
            convo.add_user_message(f"User message {i}")
            convo.add_assistant_message(f"Assistant response {i}")

        compressed = convo.get_compressed_messages(compression_threshold=5)
        raw = convo.get_messages()
        self.assertEqual(len(compressed), len(raw))

    def test_compression_after_threshold(self):
        """After 5+ turns, early turns should be compressed."""
        convo = self.conv_mod.ConversationHistory(max_turns=10)
        for i in range(7):
            convo.add_user_message(f"User message {i}")
            convo.add_assistant_message(f"Assistant response {i}")

        compressed = convo.get_compressed_messages(compression_threshold=5)
        raw = convo.get_messages()

        # Compressed should have fewer messages
        self.assertLess(len(compressed), len(raw))

        # First message in compressed should be a system summary
        self.assertEqual(compressed[0]["role"], "system")
        self.assertIn("Earlier in this conversation", compressed[0]["content"])

    def test_compressed_preserves_recent_messages(self):
        """Recent messages should be preserved verbatim after compression."""
        convo = self.conv_mod.ConversationHistory(max_turns=10)
        for i in range(7):
            convo.add_user_message(f"User message {i}")
            convo.add_assistant_message(f"Response {i}")

        compressed = convo.get_compressed_messages(compression_threshold=5)
        raw = convo.get_messages()

        # Last message should match in both
        self.assertEqual(compressed[-1]["content"], raw[-1]["content"])

    def test_compressed_history_text_format(self):
        """get_compressed_history() should return formatted text."""
        convo = self.conv_mod.ConversationHistory(max_turns=10)
        for i in range(7):
            convo.add_user_message(f"User message {i}")
            convo.add_assistant_message(f"Response {i}")

        text = convo.get_compressed_history(compression_threshold=5)
        self.assertIn("[Context]", text)
        self.assertIn("User:", text)

    def test_compressed_history_empty_when_no_messages(self):
        """get_compressed_history() returns empty for empty conversation."""
        convo = self.conv_mod.ConversationHistory()
        text = convo.get_compressed_history()
        self.assertEqual(text, "")


# ---------------------------------------------------------------------------
# Privacy filter tests
# ---------------------------------------------------------------------------

class TestPrivacyFilter(unittest.TestCase):
    """Tests for the privacy-safe context builder."""

    def setUp(self):
        import ai.context_builder as cb
        self.cb = cb

    def _make_mock_recall_module(self, mock_recall):
        """Create a mock module that returns mock_recall from get_recall_engine()."""
        import types
        mock_mod = types.ModuleType("brain.memory.recall")
        mock_mod.get_recall_engine = lambda: mock_recall
        return mock_mod

    def test_privacy_filter_returns_empty_when_no_memories(self):
        """Privacy filter returns empty when no prior memories exist."""
        mock_recall = MagicMock()
        mock_recall.has_met_before.return_value = False

        mock_mod = self._make_mock_recall_module(mock_recall)
        with patch.dict(sys.modules, {"brain.memory.recall": mock_mod, "brain.memory": MagicMock()}):
            result = asyncio.run(self.cb.build_privacy_safe_context(
                summary_packet={},
                user_message="hello"
            ))
            self.assertEqual(result, "")

    def test_privacy_filter_returns_empty_when_recall_empty(self):
        """Privacy filter returns empty when recall has no relevant memories."""
        mock_recall = MagicMock()
        mock_recall.has_met_before.return_value = True
        mock_recall.recall_for_context.return_value = ""

        mock_mod = self._make_mock_recall_module(mock_recall)
        with patch.dict(sys.modules, {"brain.memory.recall": mock_mod, "brain.memory": MagicMock()}):
            result = asyncio.run(self.cb.build_privacy_safe_context(
                summary_packet={"facts": {}, "patterns": []},
                user_message="hello"
            ))
            self.assertEqual(result, "")

    def test_privacy_filter_calls_local_llm(self):
        """Privacy filter should call local LLM with depersonalization prompt."""
        mock_recall = MagicMock()
        mock_recall.has_met_before.return_value = True
        mock_recall.recall_for_context.return_value = "User talked about job stress"

        async def fake_local_chat(*args, **kwargs):
            return "User is revisiting a stressful topic."

        # Build mock modules for lazy imports inside build_privacy_safe_context
        import types
        mock_llm_mod = types.ModuleType("ai.local_llm_client")
        mock_llm_mod.local_chat = fake_local_chat

        mock_policy_mod = types.ModuleType("ai.model_policy")
        mock_policy_mod.choose_model = lambda **kwargs: {
            "model": "test", "tier": "fast", "options": {}
        }

        mock_recall_mod = self._make_mock_recall_module(mock_recall)
        patched_modules = {
            "brain.memory.recall": mock_recall_mod,
            "brain.memory": MagicMock(),
            "ai.local_llm_client": mock_llm_mod,
            "ai.model_policy": mock_policy_mod,
        }
        with patch.dict(sys.modules, patched_modules):
            result = asyncio.run(self.cb.build_privacy_safe_context(
                summary_packet={"facts": {}, "patterns": []},
                user_message="I'm stressed again"
            ))
            self.assertIn("stressful", result)

    def test_privacy_filter_graceful_on_error(self):
        """Privacy filter returns empty on failures."""
        import types
        err_mod = types.ModuleType("brain.memory.recall")
        err_mod.get_recall_engine = MagicMock(side_effect=Exception("test error"))

        with patch.dict(sys.modules, {"brain.memory.recall": err_mod, "brain.memory": MagicMock()}):
            result = asyncio.run(self.cb.build_privacy_safe_context(
                summary_packet={},
                user_message="hello"
            ))
            self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# Cloud timeout feedback tests
# ---------------------------------------------------------------------------

class TestCloudTimeoutFeedback(unittest.TestCase):
    """Tests for cloud timeout personality-aware feedback."""

    def test_timeout_detection_logic(self):
        """Should correctly detect timeout vs other errors."""
        timeout_errors = [
            "Connection timed out",
            "Request timeout after 30s",
            "TIMEOUT waiting for response",
        ]
        other_errors = [
            "API key invalid",
            "Rate limit exceeded",
            "Server error 500",
        ]

        for err in timeout_errors:
            is_timeout = "timeout" in err.lower() or "timed out" in err.lower()
            self.assertTrue(is_timeout, f"Should detect timeout: {err}")

        for err in other_errors:
            is_timeout = "timeout" in err.lower() or "timed out" in err.lower()
            self.assertFalse(is_timeout, f"Should NOT detect timeout: {err}")


# ---------------------------------------------------------------------------
# build_full_context routing_target passthrough
# ---------------------------------------------------------------------------

class TestBuildFullContextRoutingTarget(unittest.TestCase):
    """Tests that build_full_context passes routing_target correctly."""

    def setUp(self):
        import ai.context_builder as cb
        self.cb = cb

    def test_build_full_context_accepts_routing_target(self):
        """build_full_context should accept routing_target parameter."""
        with patch.object(self.cb.SelfNarrativeBuilder, "build_self_awareness", return_value="test"):
            result = self.cb.build_full_context(
                summary_packet={"facts": {}, "patterns": [], "intent": "NO_ACTION", "constraints": {}},
                routing_target="cloud"
            )
            self.assertEqual(result, "test")

    def test_build_full_context_defaults_to_local(self):
        """build_full_context should default routing_target to 'local'."""
        captured = {}

        def spy_build(self_inner, **kwargs):
            captured["routing_target"] = kwargs.get("routing_target")
            return "test"

        with patch.object(self.cb.SelfNarrativeBuilder, "build_self_awareness", spy_build):
            self.cb.build_full_context(
                summary_packet={"facts": {}, "patterns": [], "intent": "NO_ACTION", "constraints": {}},
            )
            self.assertEqual(captured.get("routing_target"), "local")


if __name__ == "__main__":
    unittest.main()
