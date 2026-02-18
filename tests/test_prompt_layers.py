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

# Keep prompt-layer tests runnable without full runtime deps installed.
if "aiohttp" not in sys.modules:
    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientSession = object
    aiohttp_stub.ClientTimeout = object
    sys.modules["aiohttp"] = aiohttp_stub

from ai.conversation import ConversationHistory
from ai.advisor import build_prompt_messages
from ai.personalities import build_core_identity_prompt


class TestPromptLayers(unittest.TestCase):
    def test_core_prompt_sent_once_per_session(self):
        conversation = ConversationHistory()
        context = {"trigger": {"text": "hello"}, "summary": {}, "local_hour": 12}
        meta = {"reason": "smalltalk"}

        core_flags = []
        system_counts = []
        for _ in range(5):
            prompt_meta = build_prompt_messages(context, meta, conversation)
            core_flags.append(prompt_meta["include_core"])
            system_counts.append(len(prompt_meta["system_messages"]))

        self.assertTrue(core_flags[0])
        self.assertTrue(all(flag is False for flag in core_flags[1:]))
        self.assertEqual(system_counts[0], system_counts[1] + 1)
        self.assertTrue(all(count == system_counts[1] for count in system_counts[1:]))

    def test_examples_off_by_default(self):
        core_prompt = build_core_identity_prompt("kenyan_babe", include_examples=False)
        self.assertNotIn("Respond in this style:", core_prompt)


if __name__ == "__main__":
    unittest.main()
