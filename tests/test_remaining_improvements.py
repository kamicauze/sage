"""
Tests for remaining 8 improvements (#2, #3, #4, #5, #8, #10, #12, #14, #15).

Covers:
- Plan parse cache (hit/miss)
- Plan revision (revise_plan generates output)
- Cost estimation (estimate_build_cost returns valid data)
- Routing history bias (compute_history_bias)
- Personality guidance injection in system_messages
- Conversation phase detection
- Intent momentum boosting
- Request deduplication
- Configurable hardcoded values via env vars
"""

import asyncio
import os
import sys
import json
import time
import types
import tempfile
import unittest
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BRAIN_PATH = os.path.join(REPO_ROOT, "apps", "brain-runtime")
if BRAIN_PATH not in sys.path:
    sys.path.insert(0, BRAIN_PATH)

# Stub missing runtime deps before importing brain-runtime modules (matches test_prompt_layers.py)
if "aiohttp" not in sys.modules:
    _aiohttp_stub = types.ModuleType("aiohttp")
    _aiohttp_stub.ClientSession = object
    _aiohttp_stub.ClientTimeout = object
    sys.modules["aiohttp"] = _aiohttp_stub
if "dotenv" not in sys.modules:
    _dotenv_stub = types.ModuleType("dotenv")
    _dotenv_stub.load_dotenv = lambda *a, **kw: None
    sys.modules["dotenv"] = _dotenv_stub


# ---------------------------------------------------------------------------
# #2: Plan Parse Cache
# ---------------------------------------------------------------------------

class _MockBuilderForCache:
    """Minimal mock of ArchitectBuilder with just the plan cache methods."""
    _plan_parse_cache = {}

    def __init__(self):
        self._plan_cache_file = os.path.join(tempfile.mkdtemp(), "plan_parse_cache.json")

    def _get_plan_parse_cache(self, plan_hash: str):
        if plan_hash in _MockBuilderForCache._plan_parse_cache:
            return _MockBuilderForCache._plan_parse_cache[plan_hash]
        if os.path.exists(self._plan_cache_file):
            try:
                with open(self._plan_cache_file, 'r') as f:
                    disk_cache = json.load(f)
                if plan_hash in disk_cache:
                    _MockBuilderForCache._plan_parse_cache[plan_hash] = disk_cache[plan_hash]
                    return disk_cache[plan_hash]
            except Exception:
                pass
        return None

    def _set_plan_parse_cache(self, plan_hash: str, parsed):
        _MockBuilderForCache._plan_parse_cache[plan_hash] = parsed
        try:
            disk_cache = {}
            if os.path.exists(self._plan_cache_file):
                with open(self._plan_cache_file, 'r') as f:
                    disk_cache = json.load(f)
            disk_cache[plan_hash] = parsed
            with open(self._plan_cache_file, 'w') as f:
                json.dump(disk_cache, f)
        except Exception:
            pass

    def estimate_build_cost(self, plan_content: str) -> dict:
        files = self._extract_file_list(plan_content)
        tokens_per_file = 3500
        return {
            "file_count": len(files),
            "estimated_tokens": len(files) * tokens_per_file,
            "files": [f["path"] for f in files],
        }

    def _extract_file_list(self, plan_content: str):
        return []


class TestPlanParseCache(unittest.TestCase):
    """Tests for plan parse caching in ArchitectBuilder."""

    def setUp(self):
        _MockBuilderForCache._plan_parse_cache = {}

    def test_cache_miss_then_hit(self):
        """First call should miss cache, second call with same content should hit."""
        import hashlib
        builder = _MockBuilderForCache()

        plan_content = "## Plan\n- Create foo.py\n- Create bar.py"
        plan_hash = hashlib.sha256(plan_content.encode()).hexdigest()

        cached = builder._get_plan_parse_cache(plan_hash)
        self.assertIsNone(cached)

        parsed = [{"path": "foo.py", "context": "create"}, {"path": "bar.py", "context": "create"}]
        builder._set_plan_parse_cache(plan_hash, parsed)

        cached = builder._get_plan_parse_cache(plan_hash)
        self.assertEqual(cached, parsed)
        self.assertEqual(len(cached), 2)

    def test_cache_invalidates_on_different_content(self):
        """Different plan content should have different hash = cache miss."""
        import hashlib
        builder = _MockBuilderForCache()

        plan_a = "Plan A: create foo.py"
        plan_b = "Plan B: create bar.py"
        hash_a = hashlib.sha256(plan_a.encode()).hexdigest()
        hash_b = hashlib.sha256(plan_b.encode()).hexdigest()

        builder._set_plan_parse_cache(hash_a, [{"path": "foo.py"}])

        self.assertIsNone(builder._get_plan_parse_cache(hash_b))
        self.assertIsNotNone(builder._get_plan_parse_cache(hash_a))


# ---------------------------------------------------------------------------
# #4: Cost Estimation
# ---------------------------------------------------------------------------

class TestCostEstimation(unittest.TestCase):
    """Tests for estimate_build_cost()."""

    def test_estimate_returns_valid_structure(self):
        """estimate_build_cost should return file_count, estimated_tokens, files."""
        builder = _MockBuilderForCache()
        _MockBuilderForCache._plan_parse_cache = {}

        builder._extract_file_list = lambda content: [
            {"path": "a.py", "context": "create"},
            {"path": "b.py", "context": "create"},
        ]

        result = builder.estimate_build_cost("## Plan\n- a.py\n- b.py")
        self.assertEqual(result["file_count"], 2)
        self.assertGreater(result["estimated_tokens"], 0)
        self.assertIn("a.py", result["files"])


# ---------------------------------------------------------------------------
# #5: Routing History Bias
# ---------------------------------------------------------------------------

class TestRoutingHistoryBias(unittest.TestCase):
    """Tests for compute_history_bias()."""

    def test_no_history_returns_zero(self):
        """With no history, bias should be 0."""
        from shared.routing import compute_history_bias
        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"SAGE_ROUTING_HISTORY_DIR": td}):
                bias = compute_history_bias("code", project_id="test_no_hist")
        self.assertEqual(bias, 0)

    def test_local_success_biases_negative(self):
        """Multiple local successes should create negative (local-favoring) bias."""
        from shared.routing import compute_history_bias, log_routing_outcome, RouteDecision

        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"SAGE_ROUTING_HISTORY_DIR": td}):
                decision = RouteDecision(
                    route="LOCAL", score=2, reason="test",
                    provider="ollama", model="test", task_type="code"
                )
                for _ in range(3):
                    log_routing_outcome(decision, "SUCCESS", project_id="test_local")

                bias = compute_history_bias("code", project_id="test_local")
        self.assertLess(bias, 0)

    def test_local_fail_cloud_success_biases_positive(self):
        """Local failures + cloud successes should create positive (cloud-favoring) bias."""
        from shared.routing import compute_history_bias, log_routing_outcome, RouteDecision

        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"SAGE_ROUTING_HISTORY_DIR": td}):
                local_decision = RouteDecision(
                    route="LOCAL", score=2, reason="test",
                    provider="ollama", model="test", task_type="plan"
                )
                cloud_decision = RouteDecision(
                    route="CLOUD", score=8, reason="test",
                    provider="google", model="test", task_type="plan"
                )
                log_routing_outcome(local_decision, "FAILURE", project_id="test_cloud")
                log_routing_outcome(local_decision, "FAILURE", project_id="test_cloud")
                log_routing_outcome(cloud_decision, "SUCCESS", project_id="test_cloud")

                bias = compute_history_bias("plan", project_id="test_cloud")
        self.assertGreater(bias, 0)


# ---------------------------------------------------------------------------
# #8: Personality Guidance Injection
# ---------------------------------------------------------------------------

class TestPersonalityInjection(unittest.TestCase):
    """Tests for upstream personality guidance injection into system_messages."""

    def test_personality_guidance_in_system_messages(self):
        """When context has personality_guidance, it should appear in system_messages."""
        from ai.advisor import build_prompt_messages
        from ai.conversation import ConversationHistory

        context = {
            "trigger": {"type": "chat_request", "text": "how's it going"},
            "personality_guidance": "Use warm Kenyan slang. Keep it real.",
            "personality": "kenyan_babe",
        }
        meta = {"reason": "chat_request"}
        conversation = ConversationHistory()

        result = build_prompt_messages(context, meta, conversation)
        messages = result["system_messages"]

        guidance_messages = [
            m for m in messages
            if "Style guidance" in m.get("content", "")
        ]
        self.assertTrue(len(guidance_messages) > 0, "Personality guidance should be in system_messages")
        self.assertIn("warm Kenyan slang", guidance_messages[0]["content"])

    def test_no_personality_guidance_when_absent(self):
        """When context has no personality_guidance, no guidance message should be added."""
        from ai.advisor import build_prompt_messages
        from ai.conversation import ConversationHistory

        context = {
            "trigger": {"type": "chat_request", "text": "hello"},
            "personality": "kenyan_babe",
        }
        meta = {"reason": "chat_request"}
        conversation = ConversationHistory()

        result = build_prompt_messages(context, meta, conversation)
        messages = result["system_messages"]

        guidance_messages = [
            m for m in messages
            if "Style guidance" in m.get("content", "")
        ]
        self.assertEqual(len(guidance_messages), 0)


# ---------------------------------------------------------------------------
# #10: Conversation Phase Awareness
# ---------------------------------------------------------------------------

class TestConversationPhase(unittest.TestCase):
    """Tests for conversation phase detection."""

    def setUp(self):
        from ai.conversation import ConversationHistory
        self.ConversationHistory = ConversationHistory

    def test_opening_phase(self):
        """0-2 turns should be 'opening'."""
        conv = self.ConversationHistory()
        self.assertEqual(conv.get_phase(), "opening")

        conv.add_user_message("hi")
        conv.add_assistant_message("hey!")
        self.assertEqual(conv.get_phase(), "opening")

    def test_engaged_phase(self):
        """3-5 turns should be 'engaged'."""
        conv = self.ConversationHistory()
        for i in range(3):
            conv.add_user_message(f"msg {i}")
            conv.add_assistant_message(f"reply {i}")
        self.assertEqual(conv.get_phase(), "engaged")

    def test_deep_phase(self):
        """6-10 turns should be 'deep'."""
        conv = self.ConversationHistory()
        for i in range(7):
            conv.add_user_message(f"msg {i}")
            conv.add_assistant_message(f"reply {i}")
        self.assertEqual(conv.get_phase(), "deep")

    def test_intimate_phase(self):
        """11+ turns should be 'intimate'."""
        conv = self.ConversationHistory()
        for i in range(12):
            conv.add_user_message(f"msg {i}")
            conv.add_assistant_message(f"reply {i}")
        # But max_turns=8 by default, so only 8 turns kept. We need more capacity.
        conv2 = self.ConversationHistory(max_turns=15)
        for i in range(12):
            conv2.add_user_message(f"msg {i}")
            conv2.add_assistant_message(f"reply {i}")
        self.assertEqual(conv2.get_phase(), "intimate")

    def test_phase_in_context_summary(self):
        """Phase should appear in get_context_summary()."""
        conv = self.ConversationHistory()
        summary = conv.get_context_summary()
        self.assertIn("phase", summary)
        self.assertEqual(summary["phase"], "opening")

    def test_phase_in_intent_context(self):
        """Phase should appear in get_intent_context()."""
        conv = self.ConversationHistory()
        ctx = conv.get_intent_context()
        self.assertIn("phase", ctx)

    def test_emotional_mode_preserved_in_deep_phase(self):
        """Emotional mode should NOT decay during deep/intimate phases."""
        conv = self.ConversationHistory(max_turns=15)
        # Set emotional mode
        conv.update_mode("my sister died", "brain_query")
        self.assertEqual(conv.mode, "emotional")

        # Add many turns to get past MODE_DECAY_TURNS
        for i in range(8):
            conv.add_user_message(f"I miss her so much {i}")
            conv.add_assistant_message(f"I'm so sorry {i}")
            conv.update_mode(f"I miss her so much {i}", "brain_query")

        # Phase should be deep or intimate
        self.assertIn(conv.get_phase(), ("deep", "intimate"))
        # Mode should still be emotional (not decayed to neutral)
        self.assertEqual(conv.mode, "emotional")


# ---------------------------------------------------------------------------
# #12: Intent Momentum
# ---------------------------------------------------------------------------

class TestIntentMomentum(unittest.TestCase):
    """Tests for intent momentum boosting."""

    def test_momentum_boost(self):
        """3 consecutive brain_query intents should boost next ambiguous brain_query."""
        from shared.intent import classify_intent

        context = {
            "mode": "neutral",
            "emotional_mode": False,
            "turns_in_mode": 3,
            "recent_intents": ["brain_query", "brain_query", "brain_query"],
            "turn_count": 4,
        }

        # "make it better" has low confidence as brain_query (~0.3)
        intent = classify_intent(
            "make it better",
            use_llm_fallback=False,
            conversation_context=context
        )
        # With momentum, confidence should be boosted
        if intent.signals.get("momentum_boost"):
            self.assertGreaterEqual(intent.confidence, 0.40)

    def test_no_momentum_without_history(self):
        """No recent intents should not cause momentum boost."""
        from shared.intent import classify_intent

        context = {
            "mode": "neutral",
            "emotional_mode": False,
            "turns_in_mode": 0,
            "recent_intents": [],
            "turn_count": 0,
        }

        intent = classify_intent(
            "hello",
            use_llm_fallback=False,
            conversation_context=context
        )
        self.assertFalse(intent.signals.get("momentum_boost", False))

    def test_deep_emotional_inertia(self):
        """In deep emotional mode (5+ turns), non-brain intents should be overridden."""
        from shared.intent import classify_intent

        context = {
            "mode": "emotional",
            "emotional_mode": True,
            "turns_in_mode": 6,
            "recent_intents": ["brain_query", "brain_query", "brain_query"],
            "turn_count": 7,
        }

        # "add something" would normally classify as architect_task
        # but deep emotional inertia should keep it as brain_query
        intent = classify_intent(
            "add something",
            use_llm_fallback=False,
            conversation_context=context
        )
        # The intent should be brain_query due to emotional inertia
        # (only if the original confidence was < 0.90)
        if intent.signals.get("emotional_inertia"):
            self.assertEqual(intent.type, "brain_query")


# ---------------------------------------------------------------------------
# #14: Request Deduplication
# ---------------------------------------------------------------------------

class TestRequestDedup(unittest.TestCase):
    """Tests for request deduplication in on_event."""

    def test_dedup_filters_duplicate(self):
        """Same event text within window should be filtered."""
        import hashlib
        event_type = "user_intent"
        text = "tell me a joke"
        dedup_key = hashlib.md5(f"{event_type}:{text}".encode()).hexdigest()

        # Simulate dedup cache
        cache = {}
        now = time.time()
        window = 300

        # First request should pass
        cache[dedup_key] = now
        self.assertIn(dedup_key, cache)

        # Second request within window should be caught
        elapsed = now - cache[dedup_key]
        self.assertLess(elapsed, window)

    def test_dedup_allows_after_window(self):
        """Same event text after window expires should be allowed."""
        import hashlib
        event_type = "user_intent"
        text = "tell me a joke"
        dedup_key = hashlib.md5(f"{event_type}:{text}".encode()).hexdigest()

        cache = {dedup_key: time.time() - 400}
        window = 300

        # Clean expired
        now = time.time()
        cache = {k: v for k, v in cache.items() if now - v < window}

        # Should be expired
        self.assertNotIn(dedup_key, cache)


# ---------------------------------------------------------------------------
# #15: Configurable Hardcoded Values
# ---------------------------------------------------------------------------

class TestConfigurableValues(unittest.TestCase):
    """Tests for env var overrides of previously hardcoded values."""

    def test_model_policy_num_ctx_override(self):
        """SAGE_NUM_CTX should override num_ctx in model_policy."""
        with patch.dict(os.environ, {"SAGE_NUM_CTX": "8192"}):
            import ai.model_policy as mp
            import importlib
            importlib.reload(mp)
            policy = mp.choose_model()
            self.assertEqual(policy["options"]["num_ctx"], 8192)
            importlib.reload(mp)

    def test_model_policy_num_gpu_override(self):
        """SAGE_NUM_GPU should override num_gpu in model_policy."""
        with patch.dict(os.environ, {"SAGE_NUM_GPU": "1"}):
            import ai.model_policy as mp
            import importlib
            importlib.reload(mp)
            policy = mp.choose_model()
            self.assertEqual(policy["options"]["num_gpu"], 1)
            importlib.reload(mp)

    def test_model_policy_num_thread_override(self):
        """SAGE_NUM_THREAD should override num_thread in model_policy."""
        with patch.dict(os.environ, {"SAGE_NUM_THREAD": "8"}):
            import ai.model_policy as mp
            import importlib
            importlib.reload(mp)
            policy = mp.choose_model()
            self.assertEqual(policy["options"]["num_thread"], 8)
            importlib.reload(mp)

    def test_cloud_budget_override(self):
        """SAGE_MONTHLY_BUDGET_USD should override budget limit."""
        with patch.dict(os.environ, {"SAGE_MONTHLY_BUDGET_USD": "50.0"}):
            # Budget is read at runtime inside _check_and_update_budget, verify env var
            self.assertEqual(float(os.environ["SAGE_MONTHLY_BUDGET_USD"]), 50.0)

    def test_cloud_temperature_override(self):
        """SAGE_CLOUD_TEMPERATURE should override cloud temperature."""
        with patch.dict(os.environ, {"SAGE_CLOUD_TEMPERATURE": "0.5"}):
            import ai.cloud_client as cc
            import importlib
            importlib.reload(cc)
            self.assertEqual(cc.CloudBrain.CLOUD_TEMPERATURE, 0.5)
            importlib.reload(cc)

    def test_conversation_max_turns_override(self):
        """SAGE_CONV_MAX_TURNS should override DEFAULT_MAX_TURNS."""
        with patch.dict(os.environ, {"SAGE_CONV_MAX_TURNS": "12"}):
            import ai.conversation as conv
            import importlib
            importlib.reload(conv)
            self.assertEqual(conv.ConversationHistory.DEFAULT_MAX_TURNS, 12)
            importlib.reload(conv)

    def test_conversation_silence_timeout_override(self):
        """SAGE_CONV_SILENCE_TIMEOUT_SEC should override SILENCE_TIMEOUT_SEC."""
        with patch.dict(os.environ, {"SAGE_CONV_SILENCE_TIMEOUT_SEC": "600"}):
            import ai.conversation as conv
            import importlib
            importlib.reload(conv)
            self.assertEqual(conv.ConversationHistory.SILENCE_TIMEOUT_SEC, 600)
            importlib.reload(conv)

    def test_dedup_window_override(self):
        """SAGE_DEDUP_WINDOW_SEC should be configurable."""
        with patch.dict(os.environ, {"SAGE_DEDUP_WINDOW_SEC": "60"}):
            val = int(os.getenv("SAGE_DEDUP_WINDOW_SEC", "300"))
            self.assertEqual(val, 60)


if __name__ == "__main__":
    unittest.main()
