import asyncio
import os
import sys
import unittest
from unittest.mock import patch


class DummyMemory:
    def __init__(self, *args, **kwargs):
        pass


class FakeClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload):
        self.published.append((topic, payload))


class BrainFastPathTests(unittest.TestCase):
    def setUp(self):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        brain_path = os.path.join(repo_root, "brain")
        if brain_path not in sys.path:
            sys.path.insert(0, brain_path)

    def test_memory_singleton_alias(self):
        import brain.memory.sage_memory as brain_sage
        import memory.sage_memory as top_sage

        self.assertIs(
            sys.modules.get("brain.memory.sage_memory"),
            sys.modules.get("memory.sage_memory"),
        )

        with patch.object(brain_sage, "SageMemory", DummyMemory):
            brain_sage._memory = None
            mem1 = brain_sage.get_memory()
            mem2 = top_sage.get_memory()
            self.assertIs(mem1, mem2)

    def test_quiet_hours_suppresses_router(self):
        import brain.action.router as router

        ai_out = {"type": "suggestion", "text": "Hey", "confidence": 0.9}
        result = asyncio.run(
            router.route(ai_out, context={"local_hour": 1}, evt={"is_critical": False})
        )
        self.assertTrue(result.get("suppressed"))
        self.assertEqual(result.get("reason"), "quiet_hours")

    def test_smalltalk_fast_path_skips_summary(self):
        import brain.main as main
        import brain.ai.advisor as advisor
        import brain.action.router as router

        async def fake_ollama_chat(*args, **kwargs):
            return '{"type":"suggestion","text":"Hey there","confidence":0.9,"report":{}}'

        async def run_event():
            event = {"type": "smalltalk", "text": "hi", "ts": 0}
            return await main.on_event(event)

        with patch.object(router, "in_quiet_hours", return_value=False):
            with patch.object(main.summarizer, "generate_summary", side_effect=AssertionError("summary called")):
                with patch.object(advisor, "ollama_chat", side_effect=fake_ollama_chat) as call_mock:
                    result = asyncio.run(run_event())
                    self.assertEqual(call_mock.call_count, 1)
                    self.assertEqual(result.get("type"), "suggestion")

    def test_suppressed_response_not_published(self):
        import brain.main as main

        class DummyHandler:
            async def handle_transcript(self, transcript, context, on_token=None):
                return {"type": "none", "suppressed": True, "text": ""}

        original_handler = main.voice_handler
        main.voice_handler = DummyHandler()
        client = FakeClient()
        try:
            asyncio.run(main.handle_voice_transcript("hi", client))
        finally:
            main.voice_handler = original_handler

        topics = [t for t, _ in client.published]
        self.assertNotIn("sage/voice/response", topics)


if __name__ == "__main__":
    unittest.main()
