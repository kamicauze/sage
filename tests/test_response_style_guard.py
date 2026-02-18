import os
import sys
import types
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
BRAINDIR = os.path.join(REPO_ROOT, "brain")
if BRAINDIR not in sys.path:
    sys.path.insert(0, BRAINDIR)

# Keep response-style tests runnable without full runtime deps installed.
if "aiohttp" not in sys.modules:
    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientSession = object
    aiohttp_stub.ClientTimeout = object
    sys.modules["aiohttp"] = aiohttp_stub

from ai.advisor import (
    _is_brief_followup_message,
    _sanitize_suggestion_text,
    build_prompt_messages,
)
from ai.conversation import ConversationHistory


class TestResponseStyleGuard(unittest.TestCase):
    def test_sanitize_removes_wrapping_quotes(self):
        self.assertEqual(
            _sanitize_suggestion_text('"Habari gani? Life good?"'),
            "Habari gani? Life good?",
        )

    def test_brief_followup_detection(self):
        self.assertTrue(_is_brief_followup_message("chicken salad"))
        self.assertFalse(_is_brief_followup_message("what should I cook tonight?"))

    def test_prompt_adds_brief_followup_instruction(self):
        conversation = ConversationHistory()
        context = {"trigger": {"text": "chicken salad"}, "summary": {}, "local_hour": 18}
        meta = {"reason": "user_intent"}

        prompt_meta = build_prompt_messages(context, meta, conversation)
        combined = "\n".join(m["content"] for m in prompt_meta["system_messages"])

        self.assertIn("short follow-up", combined)
        self.assertIn("do not force a follow-up question on every turn", combined.lower())


if __name__ == "__main__":
    unittest.main()
