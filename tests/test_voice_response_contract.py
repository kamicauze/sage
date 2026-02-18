import asyncio
import unittest
from unittest.mock import patch

from brain.core.response_contract import (
    normalize_router_result,
    normalize_voice_response,
)
from brain.voice.handler import VoiceHandler
from shared.intent import Intent


class _DummyConversation:
    def get_intent_context(self):
        return {"mode": "neutral"}

    def update_mode(self, transcript, intent_type):
        return None


class VoiceResponseContractTests(unittest.TestCase):
    def test_normalize_voice_response_maps_suggestion_to_success(self):
        payload = {
            "type": "suggestion",
            "text": "Hello there",
            "model": "gemma",
        }
        result = normalize_voice_response(
            payload,
            default_intent="brain_query",
            default_route="LOCAL",
        )

        self.assertEqual(result["type"], "success")
        self.assertEqual(result["text"], "Hello there")
        self.assertEqual(result["intent"], "brain_query")
        self.assertFalse(result["suppressed"])
        self.assertEqual(result["data"].get("model"), "gemma")

    def test_normalize_voice_response_enforces_suppressed_shape(self):
        payload = {"type": "success", "text": "hidden", "suppressed": True}
        result = normalize_voice_response(payload, default_intent="home_control")

        self.assertEqual(result["type"], "none")
        self.assertEqual(result["text"], "")
        self.assertTrue(result["suppressed"])
        self.assertIn("reason", result)

    def test_normalize_router_result_handles_invalid_payload(self):
        result = normalize_router_result("not-a-dict")
        self.assertFalse(result["suppressed"])
        self.assertEqual(result["reason"], "invalid_router_result")

    def test_voice_handler_returns_contract_for_brain_query(self):
        async def mock_brain_callback(intent, context, reason, on_token=None):
            return {"type": "suggestion", "text": "I can help with that.", "model": "local"}

        handler = VoiceHandler(mock_brain_callback, architect_bridge=None)
        intent = Intent(
            type="brain_query",
            project=None,
            query="what can you do",
            original="what can you do",
            confidence=0.95,
            method="rule",
            signals={},
        )

        with patch("brain.voice.handler.get_conversation", return_value=_DummyConversation()):
            with patch("brain.voice.handler.classify_intent", return_value=intent):
                result = asyncio.run(handler.handle_transcript("what can you do", {}))

        self.assertEqual(result["type"], "success")
        self.assertEqual(result["intent"], "brain_query")
        self.assertIn("route", result)
        self.assertIn("status", result)
        self.assertIn("data", result)
        self.assertFalse(result["suppressed"])


if __name__ == "__main__":
    unittest.main()
