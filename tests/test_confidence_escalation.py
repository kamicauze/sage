"""
Tests for confidence-based cloud escalation and approval gate.

Covers:
- Confidence threshold decision logic
- Factual/smalltalk exemptions
- Recovered response escalation
- Cloud cost estimation
- Approval gate HTTP flow (mocked)
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import patch, AsyncMock, MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BRAIN_PATH = os.path.join(REPO_ROOT, "apps", "brain-runtime")
if BRAIN_PATH not in sys.path:
    sys.path.insert(0, BRAIN_PATH)


# ---------------------------------------------------------------------------
# Confidence threshold tests
# ---------------------------------------------------------------------------

class TestShouldEscalateToCloud(unittest.TestCase):
    """Tests for the should_escalate_to_cloud() decision function."""

    def setUp(self):
        from ai.escalation import should_escalate_to_cloud
        self.check = should_escalate_to_cloud

    def test_escalation_on_low_confidence(self):
        """Confidence below threshold should trigger escalation."""
        ai_out = {"type": "suggestion", "text": "Some answer", "confidence": 0.4}
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}):
            should, reason = self.check(
                ai_out, "user_intent", "user_intent", "tell me about X",
                cloud_provider="grok"
            )
        self.assertTrue(should)
        self.assertIn("low_confidence", reason)

    def test_no_escalation_above_threshold(self):
        """Confidence above threshold should not escalate."""
        ai_out = {"type": "suggestion", "text": "Good answer", "confidence": 0.8}
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}):
            should, reason = self.check(
                ai_out, "user_intent", "user_intent", "what should I do",
                cloud_provider="grok"
            )
        self.assertFalse(should)
        self.assertEqual(reason, "above_threshold")

    def test_escalation_on_recovered_response(self):
        """Recovered responses (JSON parse failure) should escalate."""
        ai_out = {"type": "suggestion", "text": "Partial", "confidence": 0.7, "recovered": True}
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}):
            should, reason = self.check(
                ai_out, "user_intent", "user_intent", "complex question",
                cloud_provider="grok"
            )
        self.assertTrue(should)
        self.assertEqual(reason, "recovered_response")

    def test_no_escalation_for_smalltalk_event(self):
        """Smalltalk event type should be exempt from escalation."""
        ai_out = {"type": "suggestion", "text": "Hey!", "confidence": 0.3}
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}):
            should, reason = self.check(
                ai_out, "smalltalk", "smalltalk", "hey there",
                cloud_provider="grok"
            )
        self.assertFalse(should)
        self.assertEqual(reason, "smalltalk_exempt")

    def test_no_escalation_for_smalltalk_reason(self):
        """Smalltalk meta_reason should be exempt."""
        ai_out = {"type": "suggestion", "text": "Hey!", "confidence": 0.3}
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}):
            should, reason = self.check(
                ai_out, "user_intent", "smalltalk", "hey",
                cloud_provider="grok"
            )
        self.assertFalse(should)
        self.assertEqual(reason, "smalltalk_exempt")

    def test_no_escalation_for_factual_query(self):
        """Factual queries should be exempt from escalation."""
        ai_out = {"type": "suggestion", "text": "Paris", "confidence": 0.4}
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}):
            should, reason = self.check(
                ai_out, "user_intent", "user_intent",
                "what is the capital of france",
                cloud_provider="grok"
            )
        self.assertFalse(should)
        self.assertEqual(reason, "factual_exempt")

    def test_no_escalation_threshold_disabled(self):
        """Setting threshold to 0.0 should disable escalation."""
        ai_out = {"type": "suggestion", "text": "Bad answer", "confidence": 0.1}
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key", "SAGE_CONFIDENCE_THRESHOLD": "0.0"}):
            # Need to reload module to pick up new env var
            import ai.escalation as esc
            import importlib
            importlib.reload(esc)
            should, reason = esc.should_escalate_to_cloud(
                ai_out, "user_intent", "user_intent", "complex Q",
                cloud_provider="grok"
            )
            # Restore
            importlib.reload(esc)
        self.assertFalse(should)
        self.assertEqual(reason, "threshold_disabled")

    def test_no_escalation_without_cloud_key(self):
        """No cloud API key should prevent escalation."""
        ai_out = {"type": "suggestion", "text": "Bad", "confidence": 0.2}
        with patch.dict(os.environ, {}, clear=True):
            should, reason = self.check(
                ai_out, "user_intent", "user_intent", "deep question",
                cloud_provider="grok"
            )
        self.assertFalse(should)
        self.assertEqual(reason, "no_cloud_key")

    def test_default_confidence_no_escalation(self):
        """When confidence is not set, default to 1.0 (no escalation)."""
        ai_out = {"type": "suggestion", "text": "Good answer"}
        with patch.dict(os.environ, {"XAI_API_KEY": "test-key"}):
            should, reason = self.check(
                ai_out, "user_intent", "user_intent", "some question",
                cloud_provider="grok"
            )
        self.assertFalse(should)
        self.assertEqual(reason, "above_threshold")


# ---------------------------------------------------------------------------
# Cost estimation tests
# ---------------------------------------------------------------------------

class TestCloudCostEstimation(unittest.TestCase):
    """Tests for estimate_cloud_cost()."""

    def setUp(self):
        from ai.escalation import estimate_cloud_cost
        self.estimate = estimate_cloud_cost

    def test_grok_cost(self):
        """Grok midpoint should be $0.40."""
        self.assertEqual(self.estimate("grok"), 0.4)

    def test_xai_cost(self):
        """XAI (same as grok) midpoint should be $0.40."""
        self.assertEqual(self.estimate("xai"), 0.4)

    def test_openai_cost(self):
        """OpenAI midpoint should be $0.25."""
        self.assertEqual(self.estimate("openai"), 0.25)

    def test_unknown_provider_cost(self):
        """Unknown provider should return default midpoint $0.30."""
        self.assertEqual(self.estimate("anthropic"), 0.3)


# ---------------------------------------------------------------------------
# Approval gate tests
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Minimal mock for aiohttp response."""
    def __init__(self, status, data):
        self.status = status
        self._data = data

    async def json(self):
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class _FakeSession:
    """Minimal mock for aiohttp.ClientSession."""
    def __init__(self, responses):
        self._responses = list(responses)
        self._call_index = 0

    def post(self, url, **kwargs):
        return self._next_response()

    def get(self, url, **kwargs):
        return self._next_response()

    def _next_response(self):
        resp = self._responses[self._call_index]
        self._call_index += 1
        return resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class TestApprovalGate(unittest.TestCase):
    """Tests for request_cloud_approval()."""

    def setUp(self):
        from ai.escalation import request_cloud_approval
        self.request_approval = request_cloud_approval

    def _make_mock_aiohttp(self, session):
        """Create a mock aiohttp module with a ClientSession that returns session."""
        import types
        mock_mod = types.ModuleType("aiohttp")
        mock_mod.ClientSession = lambda: session
        mock_mod.ClientTimeout = lambda total=5: {}
        return mock_mod

    def test_approval_approved(self):
        """Should return (True, 'approved') when reviewer approves."""
        create_resp = _FakeResponse(200, {
            "proposal": {"id": "test-123", "status": "pending"}
        })
        poll_resp = _FakeResponse(200, {
            "proposal": {"id": "test-123", "status": "approved", "decided_by": "human"}
        })
        session = _FakeSession([create_resp, poll_resp])
        mock_aiohttp = self._make_mock_aiohttp(session)

        with patch.dict(sys.modules, {"aiohttp": mock_aiohttp}):
            approved, detail = asyncio.run(self.request_approval(
                "test query", "grok", "low_confidence",
                api_url="http://localhost:8000", timeout_s=10
            ))
        self.assertTrue(approved)
        self.assertEqual(detail, "approved")

    def test_approval_denied(self):
        """Should return (False, 'denied: ...') when reviewer denies."""
        create_resp = _FakeResponse(200, {
            "proposal": {"id": "test-456", "status": "pending"}
        })
        poll_resp = _FakeResponse(200, {
            "proposal": {
                "id": "test-456", "status": "denied",
                "decision_reason": "too expensive"
            }
        })
        session = _FakeSession([create_resp, poll_resp])
        mock_aiohttp = self._make_mock_aiohttp(session)

        with patch.dict(sys.modules, {"aiohttp": mock_aiohttp}):
            approved, detail = asyncio.run(self.request_approval(
                "test query", "grok", "low_confidence",
                api_url="http://localhost:8000", timeout_s=10
            ))
        self.assertFalse(approved)
        self.assertIn("denied", detail)
        self.assertIn("too expensive", detail)

    def test_approval_api_error(self):
        """Should return (False, 'api_error') when API returns non-200."""
        create_resp = _FakeResponse(500, {})
        session = _FakeSession([create_resp])
        mock_aiohttp = self._make_mock_aiohttp(session)

        with patch.dict(sys.modules, {"aiohttp": mock_aiohttp}):
            approved, detail = asyncio.run(self.request_approval(
                "test query", "grok", "low_confidence",
                api_url="http://localhost:8000", timeout_s=5
            ))
        self.assertFalse(approved)
        self.assertEqual(detail, "api_error")

    def test_approval_connection_error(self):
        """Should return (False, 'error: ...') on connection failure."""
        import types
        mock_aiohttp = types.ModuleType("aiohttp")
        mock_aiohttp.ClientSession = MagicMock(side_effect=Exception("Connection refused"))
        mock_aiohttp.ClientTimeout = lambda total=5: {}

        with patch.dict(sys.modules, {"aiohttp": mock_aiohttp}):
            approved, detail = asyncio.run(self.request_approval(
                "test query", "grok", "low_confidence",
                api_url="http://localhost:9999", timeout_s=5
            ))
        self.assertFalse(approved)
        self.assertIn("error", detail)


if __name__ == "__main__":
    unittest.main()
