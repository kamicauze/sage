import os
import sys
import unittest
from unittest.mock import patch


class _FakeResponse:
    def __init__(self, status_code: int, response_payload: str):
        self.status_code = status_code
        self._response_payload = response_payload

    def json(self):
        return {"response": self._response_payload}


class IntentClassifierTests(unittest.TestCase):
    def setUp(self):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

    def test_llm_fallback_accepts_smalltalk(self):
        import shared.intent as intent_mod

        transcript = "yo, just checking on you"
        llm_json = '{"intent":"smalltalk","project":null,"confidence":0.92}'

        with patch.object(intent_mod, "CONFIDENCE_THRESHOLD", 0.95):
            with patch("requests.post", return_value=_FakeResponse(200, llm_json)):
                result = intent_mod.classify_intent(transcript, use_llm_fallback=True)

        self.assertEqual(result.type, "smalltalk")
        self.assertEqual(result.method, "llm")
        self.assertGreaterEqual(result.confidence, 0.9)

    def test_invalid_llm_intent_maps_to_smalltalk_for_greeting(self):
        import shared.intent as intent_mod

        transcript = "hey there"
        llm_json = '{"intent":"casual_chat","project":null,"confidence":0.88}'

        with patch.object(intent_mod, "CONFIDENCE_THRESHOLD", 0.95):
            with patch("requests.post", return_value=_FakeResponse(200, llm_json)):
                result = intent_mod.classify_intent(transcript, use_llm_fallback=True)

        self.assertEqual(result.type, "smalltalk")
        self.assertEqual(result.method, "llm")

    def test_invalid_llm_intent_maps_to_brain_query_when_not_smalltalk(self):
        import shared.intent as intent_mod

        transcript = "I need to vent about something"
        llm_json = '{"intent":"casual_chat","project":null,"confidence":0.81}'

        with patch.object(intent_mod, "CONFIDENCE_THRESHOLD", 0.95):
            with patch("requests.post", return_value=_FakeResponse(200, llm_json)):
                result = intent_mod.classify_intent(transcript, use_llm_fallback=True)

        self.assertEqual(result.type, "brain_query")
        self.assertIn(result.method, {"llm", "fast_rule"})

    def test_context_bias_skips_llm_for_short_followup(self):
        import shared.intent as intent_mod

        transcript = "chicken salad"
        context = {
            "mode": "neutral",
            "emotional_mode": False,
            "turns_in_mode": 1,
            "recent_intents": ["smalltalk", "brain_query"],
            "turn_count": 3,
        }

        with patch.object(intent_mod, "CONFIDENCE_THRESHOLD", 0.7):
            with patch("requests.post", side_effect=AssertionError("LLM fallback should not run")):
                result = intent_mod.classify_intent(
                    transcript,
                    use_llm_fallback=True,
                    conversation_context=context,
                )

        self.assertEqual(result.type, "brain_query")
        self.assertEqual(result.method, "context")
        self.assertGreaterEqual(result.confidence, 0.8)


if __name__ == "__main__":
    unittest.main()
