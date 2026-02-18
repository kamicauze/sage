import os
import sys
import time
import unittest


class PerceptionParserTests(unittest.TestCase):
    def setUp(self):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

    def test_parse_canonical_sensor_topic(self):
        from brain.perception.parser import parse_presence

        event = parse_presence(
            "sage/sensors/office/presence",
            '{"motion": "true", "ts": 1700000000}'
        )

        self.assertIsNotNone(event)
        self.assertEqual(event["room"], "office")
        self.assertTrue(event["motion"])
        self.assertTrue(event["presence"])
        self.assertEqual(event["type"], "presence_update")

    def test_parse_legacy_presence_topic_with_present_alias(self):
        from brain.perception.parser import parse_presence

        event = parse_presence(
            "sage/presence/living",
            '{"present": true, "timestamp": 1700000000000}'
        )

        self.assertIsNotNone(event)
        self.assertEqual(event["room"], "living")
        self.assertTrue(event["presence"])
        self.assertFalse(event["motion"])

    def test_parse_normalizes_seconds_timestamp(self):
        from brain.perception.parser import parse_presence

        seconds = int(time.time())
        event = parse_presence(
            "sage/sensors/desk/presence",
            f'{{"presence": 1, "ts": {seconds}}}'
        )

        self.assertIsNotNone(event)
        self.assertGreaterEqual(event["ts"], seconds * 1000)

    def test_parse_invalid_json_returns_none(self):
        from brain.perception.parser import parse_presence

        event = parse_presence("sage/sensors/office/presence", "not-json")
        self.assertIsNone(event)


if __name__ == "__main__":
    unittest.main()
