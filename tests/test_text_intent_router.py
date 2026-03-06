import os
import sys
import unittest


class TextIntentRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        brain_runtime_path = os.path.join(repo_root, "apps", "brain-runtime")
        if brain_runtime_path not in sys.path:
            sys.path.insert(0, brain_runtime_path)

    def test_parse_architect_command_with_query(self):
        import text_intent_router as router

        forced_type, query = router.parse_text_intent_command("/architect fix chat padding")
        self.assertEqual(forced_type, "architect_task")
        self.assertEqual(query, "fix chat padding")

    def test_parse_architect_build_command_without_query(self):
        import text_intent_router as router

        forced_type, query = router.parse_text_intent_command("/architect-build")
        self.assertEqual(forced_type, "architect_task")
        self.assertEqual(query, "")

    def test_parse_plain_text_without_command(self):
        import text_intent_router as router

        forced_type, query = router.parse_text_intent_command("just checking in")
        self.assertIsNone(forced_type)
        self.assertEqual(query, "just checking in")

    def test_detects_architect_like_text_requests(self):
        import text_intent_router as router

        self.assertTrue(
            router.looks_like_architect_text_request(
                "Sage update something on sage mobile and apply to repo"
            )
        )
        self.assertTrue(
            router.looks_like_architect_text_request(
                "architect fix weird padding on chat input"
            )
        )

    def test_avoids_calendar_and_false_positive_requests(self):
        import text_intent_router as router

        self.assertFalse(
            router.looks_like_architect_text_request(
                "Please update my meeting schedule for tomorrow"
            )
        )
        self.assertFalse(
            router.looks_like_architect_text_request(
                "I appreciate you checking in with me today"
            )
        )


if __name__ == "__main__":
    unittest.main()
