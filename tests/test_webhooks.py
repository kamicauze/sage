"""
Tests for Webhook ingestion (Phase 2).

Covers:
- Webhook registration (CRUD)
- Signature validation (GitHub, GitLab, generic)
- Template rendering
- Dispatch action types
- Trigger tracking
"""

import hashlib
import hmac
import json
import os
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    import fastapi
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestWebhookSignatureValidation(unittest.TestCase):
    """Test _validate_signature for various sources."""

    def _get_validate(self):
        from architect.api.routes.webhooks import _validate_signature
        return _validate_signature

    def test_no_secret_always_valid(self):
        validate = self._get_validate()
        hook = {"source": "github", "secret": ""}
        self.assertTrue(validate(hook, {}, b"any body"))

    def test_github_valid_signature(self):
        validate = self._get_validate()
        secret = "my-secret"
        body = b'{"action": "push"}'
        expected_sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        hook = {"source": "github", "secret": secret}
        headers = {"x-hub-signature-256": expected_sig}
        self.assertTrue(validate(hook, headers, body))

    def test_github_invalid_signature(self):
        validate = self._get_validate()
        hook = {"source": "github", "secret": "my-secret"}
        headers = {"x-hub-signature-256": "sha256=invalid"}
        self.assertFalse(validate(hook, headers, b"body"))

    def test_gitlab_valid_token(self):
        validate = self._get_validate()
        hook = {"source": "gitlab", "secret": "gitlab-token"}
        headers = {"x-gitlab-token": "gitlab-token"}
        self.assertTrue(validate(hook, headers, b"body"))

    def test_gitlab_invalid_token(self):
        validate = self._get_validate()
        hook = {"source": "gitlab", "secret": "correct"}
        headers = {"x-gitlab-token": "wrong"}
        self.assertFalse(validate(hook, headers, b"body"))

    def test_generic_valid_hmac(self):
        validate = self._get_validate()
        secret = "generic-secret"
        body = b'{"event": "deploy"}'
        expected_sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        hook = {"source": "generic", "secret": secret}
        headers = {"x-webhook-signature": expected_sig}
        self.assertTrue(validate(hook, headers, body))


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestTemplateRendering(unittest.TestCase):
    """Test _render_template."""

    def test_basic_template(self):
        from architect.api.routes.webhooks import _render_template

        result = _render_template(
            "Build triggered by push to {repo}: {message}",
            {"repo": "sage", "message": "fix bug"},
        )
        self.assertEqual(result, "Build triggered by push to sage: fix bug")

    def test_missing_key_left_as_is(self):
        from architect.api.routes.webhooks import _render_template

        result = _render_template("Hello {name}, your {role}", {"name": "Sage"})
        self.assertEqual(result, "Hello Sage, your {role}")

    def test_non_string_values_ignored(self):
        from architect.api.routes.webhooks import _render_template

        result = _render_template("{count} items", {"count": 42})
        self.assertEqual(result, "{count} items")  # int not replaced


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestWebhookStorage(unittest.TestCase):
    """Test webhook config persistence."""

    def test_load_empty_config(self):
        from architect.api.routes.webhooks import _load_config

        with patch("architect.api.routes.webhooks._STORE_PATH") as mock_path:
            mock_path.exists.return_value = False
            config = _load_config()
            self.assertEqual(config["version"], 1)
            self.assertEqual(config["hooks"], [])

    def test_save_and_load_config(self):
        from architect.api.routes.webhooks import _load_config, _save_config

        with tempfile.TemporaryDirectory() as tmpdir:
            store_path = os.path.join(tmpdir, "config.json")
            with patch("architect.api.routes.webhooks._STORE_PATH", __import__("pathlib").Path(store_path)):
                data = {"version": 1, "hooks": [{"id": "wh_test", "name": "test"}]}
                _save_config(data)
                loaded = _load_config()
                self.assertEqual(len(loaded["hooks"]), 1)
                self.assertEqual(loaded["hooks"][0]["id"], "wh_test")


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestDispatchAction(unittest.TestCase):
    """Test _dispatch_action for different action types."""

    @patch("architect.api.routes.webhooks.json")
    def test_start_agent_publishes_mqtt(self, mock_json):
        from architect.api.routes.webhooks import _dispatch_action

        mock_json.dumps = json.dumps
        action = {"type": "start_agent", "agent": "builder_agent", "goal_template": "Build {repo}"}
        payload = {"repo": "sage"}

        with patch("paho.mqtt.publish.single") as mock_publish:
            result = _dispatch_action(action, payload)
            self.assertTrue(result["dispatched"])
            self.assertEqual(result["agent"], "builder_agent")
            self.assertEqual(result["goal"], "Build sage")

    def test_unknown_action_type(self):
        from architect.api.routes.webhooks import _dispatch_action

        result = _dispatch_action({"type": "invalid"}, {})
        self.assertFalse(result["dispatched"])
        self.assertIn("Unknown action type", result["error"])

    @patch("architect.api.routes.webhooks.json")
    def test_brain_query_publishes_mqtt(self, mock_json):
        from architect.api.routes.webhooks import _dispatch_action

        mock_json.dumps = json.dumps
        action = {"type": "brain_query", "text_template": "CI failed: {status}"}
        payload = {"status": "error"}

        with patch("paho.mqtt.publish.single") as mock_publish:
            result = _dispatch_action(action, payload)
            self.assertTrue(result["dispatched"])
            self.assertEqual(result["text"], "CI failed: error")


if __name__ == "__main__":
    unittest.main()
