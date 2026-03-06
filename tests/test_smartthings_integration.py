import asyncio
import os
import sys
import unittest
from unittest.mock import patch


class SmartThingsIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        brain_runtime_path = os.path.join(repo_root, "apps", "brain-runtime")
        if brain_runtime_path not in sys.path:
            sys.path.insert(0, brain_runtime_path)

    def test_parses_turn_on_command(self):
        import integrations.smartthings as smartthings

        command = smartthings.parse_home_control_command("turn on the kitchen lights")
        self.assertIsNotNone(command)
        self.assertEqual(command.kind, "device_command")
        self.assertEqual(command.capability, "switch")
        self.assertEqual(command.command, "on")
        self.assertEqual(command.raw_target, "kitchen lights")

    def test_parses_scene_command(self):
        import integrations.smartthings as smartthings

        command = smartthings.parse_home_control_command("run bedtime scene")
        self.assertIsNotNone(command)
        self.assertEqual(command.kind, "run_scene")
        self.assertEqual(command.raw_target, "bedtime")

    def test_alias_loader_accepts_json(self):
        import integrations.smartthings as smartthings

        aliases = smartthings._load_device_aliases('{"Kitchen Lights":"abc-123"}')
        self.assertEqual(aliases.get("kitchen lights"), "abc-123")

    def test_handle_request_returns_not_handled_when_integration_disabled(self):
        import integrations.smartthings as smartthings

        with patch.dict(os.environ, {"SMARTTHINGS_ENABLED": "false"}, clear=False):
            result = asyncio.run(smartthings.handle_home_control_request("turn on kitchen lights"))
        self.assertFalse(result.get("handled"))

    def test_handle_request_reports_missing_token_when_enabled(self):
        import integrations.smartthings as smartthings

        with patch.dict(
            os.environ,
            {
                "SMARTTHINGS_ENABLED": "true",
                "SMARTTHINGS_TOKEN": "",
            },
            clear=False,
        ):
            result = asyncio.run(smartthings.handle_home_control_request("turn on kitchen lights"))

        self.assertTrue(result.get("handled"))
        self.assertFalse(result.get("success"))
        self.assertIn("SMARTTHINGS_TOKEN", result.get("text", ""))


if __name__ == "__main__":
    unittest.main()
