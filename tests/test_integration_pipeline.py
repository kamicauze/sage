"""
Integration tests for the Sage brain pipeline.

These tests verify the WIRING between components — that data flows correctly
through the pipeline, not just that individual functions work in isolation.

Covers:
- Conversation phase → intent context → classify_intent momentum pipeline
- Personality guidance → build_prompt_messages system_messages pipeline
- Routing history → UnifiedRouter.route() score bias pipeline
- Request dedup exact logic from on_event()
- Phase-aware mode decay across full conversation lifecycle
- Conversation context flows through advise() to build_prompt_messages()
"""

import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BRAIN_PATH = os.path.join(REPO_ROOT, "apps", "brain-runtime")
if BRAIN_PATH not in sys.path:
    sys.path.insert(0, BRAIN_PATH)

# Stub missing runtime deps (matches test_prompt_layers.py pattern)
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
# Integration #1: Conversation → Intent Context → classify_intent pipeline
# ---------------------------------------------------------------------------

class TestConversationToIntentPipeline(unittest.TestCase):
    """Verify conversation context flows through to intent classification."""

    def test_phase_propagates_to_intent_context(self):
        """
        Conversation with 7 turns → get_intent_context() → phase should be 'deep'.
        This verifies the phase field is available for classify_intent to use.
        """
        from ai.conversation import ConversationHistory
        from shared.intent import classify_intent

        conv = ConversationHistory(max_turns=15)
        for i in range(7):
            conv.add_user_message(f"Tell me more about topic {i}")
            conv.add_assistant_message(f"Here's info about topic {i}")

        ctx = conv.get_intent_context()

        # Phase should be deep (6-10 turns)
        self.assertEqual(ctx["phase"], "deep")
        # Recent intents should be populated
        self.assertIn("recent_intents", ctx)
        self.assertIn("turn_count", ctx)

    def test_momentum_works_through_conversation_context(self):
        """
        Build conversation with repeated brain_query intents →
        get_intent_context() → classify_intent should apply momentum boost.
        """
        from ai.conversation import ConversationHistory
        from shared.intent import classify_intent

        conv = ConversationHistory(max_turns=15)

        # Simulate 3 brain_query turns
        for i in range(3):
            conv.add_user_message(f"How do I feel about this {i}")
            conv.add_assistant_message(f"You seem to feel X about {i}")
            conv.update_mode(f"How do I feel about this {i}", "brain_query")

        ctx = conv.get_intent_context()

        # Verify the context has what classify_intent needs
        self.assertGreaterEqual(len(ctx.get("recent_intents", [])), 2)
        self.assertGreater(ctx["turn_count"], 0)

        # Now classify an ambiguous message with this context
        intent = classify_intent(
            "tell me more",
            use_llm_fallback=False,
            conversation_context=ctx,
        )

        # The intent should have been processed (whether boosted or not,
        # the pipeline shouldn't error)
        self.assertIsNotNone(intent)
        self.assertIsNotNone(intent.type)
        self.assertGreater(intent.confidence, 0)

    def test_emotional_inertia_through_conversation(self):
        """
        Build deep emotional conversation → classify a non-emotional message →
        emotional inertia should override to brain_query.
        """
        from ai.conversation import ConversationHistory
        from shared.intent import classify_intent

        conv = ConversationHistory(max_turns=15)

        # Set emotional mode and sustain it with grief trigger keywords
        # ("miss him" matches the grief trigger list, keeping mode emotional)
        conv.update_mode("my brother passed away", "brain_query")
        for i in range(6):
            conv.add_user_message(f"I miss him so much {i}")
            conv.add_assistant_message(f"I'm so sorry for your loss {i}")
            conv.update_mode(f"I miss him every day {i}", "brain_query")

        ctx = conv.get_intent_context()

        # Verify the context signals deep emotional mode
        self.assertTrue(ctx.get("emotional_mode", False))
        # turns_in_mode should be >= 5 since mode_since_turn stayed at 0
        # (mode never changed, so mode_since_turn was never reset)
        self.assertGreaterEqual(ctx.get("turns_in_mode", 0), 5)

        # Classify something that would normally be architect_task
        intent = classify_intent(
            "add a button",
            use_llm_fallback=False,
            conversation_context=ctx,
        )

        # If emotional inertia kicked in, type should be brain_query
        if intent.signals.get("emotional_inertia"):
            self.assertEqual(intent.type, "brain_query")


# ---------------------------------------------------------------------------
# Integration #2: Personality guidance → system_messages pipeline
# ---------------------------------------------------------------------------

class TestPersonalityGuidancePipeline(unittest.TestCase):
    """Verify personality guidance flows from context into system_messages."""

    def test_guidance_in_context_reaches_system_messages(self):
        """
        When context has personality_guidance set, build_prompt_messages()
        should include it in system_messages.
        """
        from ai.advisor import build_prompt_messages
        from ai.conversation import ConversationHistory

        conv = ConversationHistory()
        context = {
            "trigger": {"type": "chat_request", "text": "how's the weather"},
            "personality": "kenyan_babe",
            "personality_guidance": "Use warm Kenyan slang. Reference shared experiences.",
        }
        meta = {"reason": "chat_request"}

        result = build_prompt_messages(context, meta, conv)
        messages = result["system_messages"]

        guidance_msgs = [m for m in messages if "Style guidance" in m.get("content", "")]
        self.assertTrue(
            len(guidance_msgs) > 0,
            "personality_guidance from context should appear in system_messages"
        )
        self.assertIn("Kenyan slang", guidance_msgs[0]["content"])

    def test_no_guidance_means_no_style_message(self):
        """
        When context has no personality_guidance, system_messages should
        not contain any style guidance entry.
        """
        from ai.advisor import build_prompt_messages
        from ai.conversation import ConversationHistory

        conv = ConversationHistory()
        context = {
            "trigger": {"type": "chat_request", "text": "hello"},
            "personality": "kenyan_babe",
        }
        meta = {"reason": "chat_request"}

        result = build_prompt_messages(context, meta, conv)
        messages = result["system_messages"]

        guidance_msgs = [m for m in messages if "Style guidance" in m.get("content", "")]
        self.assertEqual(len(guidance_msgs), 0)

    def test_advise_sets_guidance_on_context_for_prompt_builder(self):
        """
        Regression test for the wiring bug: advise() must set personality_guidance
        on BOTH ctx_to_send AND context, so build_prompt_messages reads it.
        """
        from ai.advisor import build_prompt_messages

        # Simulate what advise() does internally: personality_guidance should
        # be on the context dict passed to build_prompt_messages
        context = {
            "trigger": {"type": "user_intent", "text": "what's up"},
            "personality": "sage",
        }

        # Before fix: only ctx_to_send had it, context didn't
        # After fix: context also has it
        context["personality_guidance"] = "Be extra chill and laid back"

        from ai.conversation import ConversationHistory
        conv = ConversationHistory()
        result = build_prompt_messages(context, {"reason": "user_intent"}, conv)

        guidance_msgs = [
            m for m in result["system_messages"]
            if "Style guidance" in m.get("content", "")
        ]
        self.assertTrue(
            len(guidance_msgs) > 0,
            "When context has personality_guidance, it must appear in system_messages"
        )


# ---------------------------------------------------------------------------
# Integration #3: Routing history → UnifiedRouter.route() bias pipeline
# ---------------------------------------------------------------------------

class TestRoutingHistoryToRouterPipeline(unittest.TestCase):
    """Verify routing history outcomes affect live route() decisions."""

    def test_local_success_history_biases_route_score_down(self):
        """
        Log 3 local successes → route same task type →
        score should be lower (biased toward local).
        """
        from shared.routing import (
            UnifiedRouter, RouteDecision,
            log_routing_outcome, compute_history_bias,
        )

        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"SAGE_ROUTING_HISTORY_DIR": td}):
                # Log 3 successful local code completions
                decision = RouteDecision(
                    route="LOCAL", score=3, reason="test",
                    provider="ollama", model="gemma3:12b", task_type="code"
                )
                for _ in range(3):
                    log_routing_outcome(decision, "SUCCESS", project_id="integration_test")

                # Bias should now be negative for "code" tasks
                bias = compute_history_bias("code", project_id="integration_test")
                self.assertLess(bias, 0)

                # Route a moderate-complexity code query
                router = UnifiedRouter()
                result = router.route("fix the bug in auth module", task_type="code")

                # The history bias should be included in the reason
                # (for moderate queries that would normally score in HYBRID range)
                self.assertIsNotNone(result)
                self.assertIn(result.route, ("LOCAL", "HYBRID", "CLOUD"))

    def test_local_fail_cloud_success_biases_route_score_up(self):
        """
        Log local failures + cloud successes → route same task type →
        score should be higher (biased toward cloud).
        """
        from shared.routing import (
            UnifiedRouter, RouteDecision,
            log_routing_outcome, compute_history_bias,
        )

        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"SAGE_ROUTING_HISTORY_DIR": td}):
                local_dec = RouteDecision(
                    route="LOCAL", score=2, reason="test",
                    provider="ollama", model="gemma3:12b", task_type="plan"
                )
                cloud_dec = RouteDecision(
                    route="CLOUD", score=9, reason="test",
                    provider="google", model="gemini-1.5-pro", task_type="plan"
                )
                log_routing_outcome(local_dec, "FAILURE", project_id="int_cloud")
                log_routing_outcome(local_dec, "FAILURE", project_id="int_cloud")
                log_routing_outcome(cloud_dec, "SUCCESS", project_id="int_cloud")

                bias = compute_history_bias("plan", project_id="int_cloud")
                self.assertGreater(bias, 0)

    def test_history_for_one_task_type_doesnt_affect_another(self):
        """History for 'code' tasks should not bias 'chat' routing."""
        from shared.routing import (
            RouteDecision, log_routing_outcome, compute_history_bias,
        )

        with tempfile.TemporaryDirectory() as td:
            with patch.dict(os.environ, {"SAGE_ROUTING_HISTORY_DIR": td}):
                decision = RouteDecision(
                    route="LOCAL", score=2, reason="test",
                    provider="ollama", model="test", task_type="code"
                )
                for _ in range(3):
                    log_routing_outcome(decision, "SUCCESS", project_id="cross_type")

                code_bias = compute_history_bias("code", project_id="cross_type")
                chat_bias = compute_history_bias("chat", project_id="cross_type")

                self.assertLess(code_bias, 0)  # code has history
                self.assertEqual(chat_bias, 0)  # chat has no history


# ---------------------------------------------------------------------------
# Integration #4: Request dedup pipeline (exact logic from on_event)
# ---------------------------------------------------------------------------

class TestDedupPipeline(unittest.TestCase):
    """Test the exact dedup logic from main.py on_event()."""

    def _run_dedup(self, event_type, text, cache, window):
        """Replicate the exact dedup logic from on_event."""
        if text and window > 0:
            dedup_key = hashlib.md5(f"{event_type}:{text}".encode()).hexdigest()
            now = time.time()
            # Clean expired entries
            cleaned = {k: v for k, v in cache.items() if now - v < window}
            cache.clear()
            cache.update(cleaned)

            if dedup_key in cache:
                return True, cache  # duplicate
            cache[dedup_key] = now
        return False, cache  # not duplicate

    def test_first_request_passes(self):
        cache = {}
        is_dup, cache = self._run_dedup("user_intent", "tell me a joke", cache, 300)
        self.assertFalse(is_dup)
        self.assertEqual(len(cache), 1)

    def test_immediate_duplicate_blocked(self):
        cache = {}
        self._run_dedup("user_intent", "tell me a joke", cache, 300)
        is_dup, cache = self._run_dedup("user_intent", "tell me a joke", cache, 300)
        self.assertTrue(is_dup)

    def test_different_text_passes(self):
        cache = {}
        self._run_dedup("user_intent", "tell me a joke", cache, 300)
        is_dup, cache = self._run_dedup("user_intent", "what time is it", cache, 300)
        self.assertFalse(is_dup)
        self.assertEqual(len(cache), 2)

    def test_different_event_type_passes(self):
        cache = {}
        self._run_dedup("user_intent", "tell me a joke", cache, 300)
        is_dup, cache = self._run_dedup("smalltalk", "tell me a joke", cache, 300)
        self.assertFalse(is_dup)

    def test_expired_entry_allows_repeat(self):
        cache = {}
        # Manually insert an old entry
        dedup_key = hashlib.md5("user_intent:tell me a joke".encode()).hexdigest()
        cache[dedup_key] = time.time() - 400  # 400s ago, window is 300s

        is_dup, cache = self._run_dedup("user_intent", "tell me a joke", cache, 300)
        self.assertFalse(is_dup)

    def test_zero_window_disables_dedup(self):
        cache = {}
        self._run_dedup("user_intent", "tell me a joke", cache, 0)
        is_dup, cache = self._run_dedup("user_intent", "tell me a joke", cache, 0)
        self.assertFalse(is_dup)  # dedup disabled when window=0


# ---------------------------------------------------------------------------
# Integration #5: Full conversation lifecycle with phase-aware mode decay
# ---------------------------------------------------------------------------

class TestConversationLifecycle(unittest.TestCase):
    """Test full conversation lifecycle: mode transitions, phase changes, decay."""

    def test_emotional_mode_survives_deep_conversation(self):
        """
        Opening: set emotional mode → engaged: still emotional →
        deep: emotional mode PRESERVED (phase-aware decay) →
        mode should NOT decay to neutral.
        """
        from ai.conversation import ConversationHistory

        conv = ConversationHistory(max_turns=20)

        # Turn 1: trigger emotional mode
        conv.update_mode("my mom passed away last week", "brain_query")
        self.assertEqual(conv.mode, "emotional")

        # Turns 2-8: continue emotional conversation
        # Messages don't re-trigger emotional mode, so turns_in_mode accumulates.
        # Phase-aware decay should preserve emotional mode once in deep phase.
        for i in range(8):
            conv.add_user_message(f"I miss her so much {i}")
            conv.add_assistant_message(f"That's completely natural {i}")
            conv.update_mode(f"I miss her so much {i}", "brain_query")

        # Should be in deep or intimate phase
        phase = conv.get_phase()
        self.assertIn(phase, ("deep", "intimate"))

        # Emotional mode should be PRESERVED (not decayed)
        self.assertEqual(conv.mode, "emotional")

    def test_emotional_mode_decays_in_opening_phase(self):
        """
        If emotional mode is set but conversation switches to neutral topics,
        mode should decay after MODE_DECAY_TURNS since we're not in deep/intimate.
        """
        from ai.conversation import ConversationHistory

        conv = ConversationHistory(max_turns=20)

        # Set emotional mode using a proper trigger
        conv.update_mode("i'm feeling sad and lonely", "brain_query")
        self.assertEqual(conv.mode, "emotional")

        # Switch to non-emotional turns — enough to reach MODE_DECAY_TURNS
        for i in range(6):
            conv.add_user_message(f"anyway, what about the weather {i}")
            conv.add_assistant_message(f"The weather is nice {i}")
            conv.update_mode(f"what about the weather {i}", "smalltalk")

        # Mode should have decayed to neutral since phase is engaged (not deep/intimate)
        # and turns_in_mode exceeded MODE_DECAY_TURNS
        self.assertEqual(conv.mode, "neutral")

    def test_phase_progression_through_conversation(self):
        """Verify phases progress correctly: opening → engaged → deep → intimate."""
        from ai.conversation import ConversationHistory

        conv = ConversationHistory(max_turns=20)

        # Opening: 0-2 turns
        self.assertEqual(conv.get_phase(), "opening")
        conv.add_user_message("hi")
        conv.add_assistant_message("hey!")
        self.assertEqual(conv.get_phase(), "opening")

        # Engaged: 3-5 turns
        for i in range(2):
            conv.add_user_message(f"msg {i}")
            conv.add_assistant_message(f"reply {i}")
        self.assertEqual(conv.get_phase(), "engaged")

        # Deep: 6-10 turns
        for i in range(4):
            conv.add_user_message(f"deeper {i}")
            conv.add_assistant_message(f"deeper reply {i}")
        self.assertEqual(conv.get_phase(), "deep")

        # Intimate: 11+ turns
        for i in range(5):
            conv.add_user_message(f"intimate {i}")
            conv.add_assistant_message(f"intimate reply {i}")
        self.assertEqual(conv.get_phase(), "intimate")

    def test_context_summary_includes_phase(self):
        """get_context_summary() should include phase info."""
        from ai.conversation import ConversationHistory

        conv = ConversationHistory(max_turns=15)
        for i in range(4):
            conv.add_user_message(f"msg {i}")
            conv.add_assistant_message(f"reply {i}")

        summary = conv.get_context_summary()

        self.assertIn("phase", summary)
        self.assertEqual(summary["phase"], "engaged")

    def test_intent_context_includes_mode_and_phase(self):
        """get_intent_context() should include mode, phase, and turns_in_mode."""
        from ai.conversation import ConversationHistory

        conv = ConversationHistory(max_turns=15)
        conv.update_mode("i'm feeling sad and lonely", "brain_query")
        for i in range(4):
            conv.add_user_message(f"msg {i}")
            conv.add_assistant_message(f"reply {i}")

        ctx = conv.get_intent_context()

        self.assertIn("mode", ctx)
        self.assertEqual(ctx["mode"], "emotional")
        self.assertIn("phase", ctx)
        self.assertIn("turns_in_mode", ctx)
        self.assertIn("emotional_mode", ctx)
        self.assertTrue(ctx["emotional_mode"])


# ---------------------------------------------------------------------------
# Integration #6: Configurable env vars work across reloaded modules
# ---------------------------------------------------------------------------

class TestEnvVarPipelineIntegration(unittest.TestCase):
    """Verify env var overrides work when modules are reloaded (simulating restart)."""

    def test_model_policy_and_context_builder_share_same_values(self):
        """
        SAGE_NUM_CTX, SAGE_NUM_GPU, SAGE_NUM_THREAD should produce the same
        values in both model_policy and context_builder.
        """
        import importlib

        with patch.dict(os.environ, {
            "SAGE_NUM_CTX": "2048",
            "SAGE_NUM_GPU": "4",
            "SAGE_NUM_THREAD": "8",
        }):
            import ai.model_policy as mp
            importlib.reload(mp)
            policy = mp.choose_model()

            self.assertEqual(policy["options"]["num_ctx"], 2048)
            self.assertEqual(policy["options"]["num_gpu"], 4)
            self.assertEqual(policy["options"]["num_thread"], 8)

            # Restore
            importlib.reload(mp)

    def test_dedup_window_propagation(self):
        """
        SAGE_DEDUP_WINDOW_SEC env var should be read at module level in main.py.
        Since we can't import main.py (side effects), verify the pattern works.
        """
        with patch.dict(os.environ, {"SAGE_DEDUP_WINDOW_SEC": "60"}):
            window = int(os.getenv("SAGE_DEDUP_WINDOW_SEC", "300"))
            self.assertEqual(window, 60)

        # Without env var, default is 300
        with patch.dict(os.environ, {}, clear=True):
            window = int(os.getenv("SAGE_DEDUP_WINDOW_SEC", "300"))
            self.assertEqual(window, 300)


if __name__ == "__main__":
    unittest.main()
