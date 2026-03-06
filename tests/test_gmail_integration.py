"""
Tests for Gmail API integration (Phase 1).

Covers:
- Gmail scopes added to OAuth
- Gmail API endpoints (list, get, send, modify)
- _build_raw_email helper
- Gmail client wrapper command detection
- Gmail agent tools
"""

import os
import sys
import types
import unittest
from unittest.mock import patch, MagicMock

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BRAIN_PATH = os.path.join(REPO_ROOT, "apps", "brain-runtime")
if BRAIN_PATH not in sys.path:
    sys.path.insert(0, BRAIN_PATH)

# Stub missing runtime deps
if "aiohttp" not in sys.modules:
    _aiohttp_stub = types.ModuleType("aiohttp")
    _aiohttp_stub.ClientSession = object
    _aiohttp_stub.ClientTimeout = object
    sys.modules["aiohttp"] = _aiohttp_stub
if "dotenv" not in sys.modules:
    _dotenv_stub = types.ModuleType("dotenv")
    _dotenv_stub.load_dotenv = lambda *a, **kw: None
    sys.modules["dotenv"] = _dotenv_stub


try:
    import fastapi
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestGmailScopes(unittest.TestCase):
    """Test that Gmail scopes are included in the OAuth configuration."""

    def test_gmail_scopes_present(self):
        from architect.api.routes.google_workspace import _SCOPES

        self.assertIn("https://www.googleapis.com/auth/gmail.readonly", _SCOPES)
        self.assertIn("https://www.googleapis.com/auth/gmail.send", _SCOPES)
        self.assertIn("https://www.googleapis.com/auth/gmail.modify", _SCOPES)

    def test_calendar_tasks_scopes_preserved(self):
        from architect.api.routes.google_workspace import _SCOPES

        self.assertIn("https://www.googleapis.com/auth/calendar", _SCOPES)
        self.assertIn("https://www.googleapis.com/auth/tasks", _SCOPES)

    def test_gmail_base_url_defined(self):
        from architect.api.routes.google_workspace import _GMAIL_BASE

        self.assertEqual(_GMAIL_BASE, "https://gmail.googleapis.com/gmail/v1")


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestBuildRawEmail(unittest.TestCase):
    """Test the _build_raw_email helper function."""

    def test_basic_email(self):
        from architect.api.routes.google_workspace import _build_raw_email
        import base64

        raw = _build_raw_email(
            to="user@example.com",
            subject="Test Subject",
            body="Hello World",
        )
        # Should be base64url-encoded
        decoded = base64.urlsafe_b64decode(raw).decode("utf-8")
        self.assertIn("To: user@example.com", decoded)
        self.assertIn("Subject: Test Subject", decoded)
        self.assertIn("Hello World", decoded)

    def test_email_with_cc_bcc(self):
        from architect.api.routes.google_workspace import _build_raw_email
        import base64

        raw = _build_raw_email(
            to="to@test.com",
            subject="CC Test",
            body="Body",
            cc="cc@test.com",
            bcc="bcc@test.com",
        )
        decoded = base64.urlsafe_b64decode(raw).decode("utf-8")
        self.assertIn("Cc: cc@test.com", decoded)
        self.assertIn("Bcc: bcc@test.com", decoded)

    def test_email_without_cc_bcc(self):
        from architect.api.routes.google_workspace import _build_raw_email
        import base64

        raw = _build_raw_email(
            to="to@test.com",
            subject="No CC",
            body="Body",
        )
        decoded = base64.urlsafe_b64decode(raw).decode("utf-8")
        self.assertNotIn("Cc:", decoded)
        self.assertNotIn("Bcc:", decoded)


@unittest.skipUnless(HAS_FASTAPI, "fastapi not installed")
class TestGmailPydanticModels(unittest.TestCase):
    """Test Gmail Pydantic request models."""

    def test_gmail_send_request(self):
        from architect.api.routes.google_workspace import GmailSendRequest

        req = GmailSendRequest(to="test@test.com", subject="Hi", body="Hello")
        self.assertEqual(req.to, "test@test.com")
        self.assertIsNone(req.cc)
        self.assertIsNone(req.bcc)

    def test_gmail_modify_request(self):
        from architect.api.routes.google_workspace import GmailModifyRequest

        req = GmailModifyRequest(add_labels=["STARRED"], remove_labels=["INBOX"])
        self.assertEqual(req.add_labels, ["STARRED"])
        self.assertEqual(req.remove_labels, ["INBOX"])

    def test_gmail_modify_request_empty(self):
        from architect.api.routes.google_workspace import GmailModifyRequest

        req = GmailModifyRequest()
        self.assertIsNone(req.add_labels)
        self.assertIsNone(req.remove_labels)


class TestGmailClientDetection(unittest.TestCase):
    """Test that the brain-runtime client detects Gmail commands."""

    def test_looks_like_gmail_query(self):
        from brain.integrations.google_workspace import _looks_like_gmail_query

        self.assertTrue(_looks_like_gmail_query("check my email"))
        self.assertTrue(_looks_like_gmail_query("show gmail inbox"))
        self.assertTrue(_looks_like_gmail_query("search email for invoices"))
        self.assertTrue(_looks_like_gmail_query("read my mail"))

    def test_not_gmail_query(self):
        from brain.integrations.google_workspace import _looks_like_gmail_query

        self.assertFalse(_looks_like_gmail_query("what time is it"))
        self.assertFalse(_looks_like_gmail_query(""))
        self.assertFalse(_looks_like_gmail_query("email"))  # No action word

    def test_format_gmail_messages(self):
        from brain.integrations.google_workspace import _format_gmail_messages

        messages = [
            {"id": "msg1", "threadId": "t1"},
            {"id": "msg2", "threadId": "t2"},
        ]
        result = _format_gmail_messages(messages)
        self.assertIn("msg1", result)
        self.assertIn("msg2", result)
        self.assertIn("2 message(s)", result)

    def test_format_gmail_empty(self):
        from brain.integrations.google_workspace import _format_gmail_messages

        result = _format_gmail_messages([])
        self.assertIn("No messages", result)


class TestGmailAgentTools(unittest.TestCase):
    """Test Gmail agent tool factory functions."""

    def test_gmail_read_tool_creation(self):
        from shared.agent.tools import make_gmail_read_tool

        tool = make_gmail_read_tool("http://localhost:8000")
        self.assertEqual(tool.name, "gmail_read")
        self.assertFalse(tool.needs_approval)
        self.assertIn("query", tool.parameters)

    def test_gmail_send_tool_needs_approval(self):
        from shared.agent.tools import make_gmail_send_tool

        tool = make_gmail_send_tool("http://localhost:8000")
        self.assertEqual(tool.name, "gmail_send")
        self.assertTrue(tool.needs_approval)
        self.assertIn("to", tool.parameters)
        self.assertIn("subject", tool.parameters)

    def test_gmail_archive_tool_needs_approval(self):
        from shared.agent.tools import make_gmail_archive_tool

        tool = make_gmail_archive_tool("http://localhost:8000")
        self.assertEqual(tool.name, "gmail_archive")
        self.assertTrue(tool.needs_approval)
        self.assertIn("message_id", tool.parameters)

    def test_tool_schema_serialization(self):
        from shared.agent.tools import make_gmail_read_tool

        tool = make_gmail_read_tool()
        schema = tool.to_schema()
        self.assertEqual(schema["name"], "gmail_read")
        self.assertIn("description", schema)
        self.assertIn("parameters", schema)


if __name__ == "__main__":
    unittest.main()
