"""
Tests for Browser Automation Tools (Phase 4).

Covers:
- BrowserSession class methods (mocked Playwright)
- Browser tool factory functions
- Tool schema and approval settings
"""

import asyncio
import os
import sys
import types
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BRAIN_PATH = os.path.join(REPO_ROOT, "apps", "brain-runtime")
if BRAIN_PATH not in sys.path:
    sys.path.insert(0, BRAIN_PATH)

# Stub playwright before importing browser module
if "playwright" not in sys.modules:
    _pw_stub = types.ModuleType("playwright")
    _pw_api = types.ModuleType("playwright.async_api")

    class _MockPage:
        url = "https://example.com"
        async def goto(self, url, **kw): return MagicMock(status=200)
        async def title(self): return "Example"
        async def click(self, selector, **kw): pass
        async def fill(self, selector, value): pass
        async def inner_text(self, selector, **kw): return "Page content here"
        async def screenshot(self, path=None, **kw): pass
        async def wait_for_load_state(self, state): pass

    class _MockBrowser:
        async def new_page(self): return _MockPage()
        async def close(self): pass

    class _MockPlaywright:
        chromium = None  # Set after class definition
        async def stop(self): pass

    class _MockChromium:
        @staticmethod
        async def launch(**kw): return _MockBrowser()

    _MockPlaywright.chromium = _MockChromium()

    class _AsyncPlaywrightContextManager:
        async def start(self):
            return _MockPlaywright()

    def _mock_async_playwright():
        return _AsyncPlaywrightContextManager()

    _pw_api.async_playwright = _mock_async_playwright
    _pw_stub.async_api = _pw_api
    sys.modules["playwright"] = _pw_stub
    sys.modules["playwright.async_api"] = _pw_api

# Stub aiohttp if needed
if "aiohttp" not in sys.modules:
    _aiohttp_stub = types.ModuleType("aiohttp")
    _aiohttp_stub.ClientSession = object
    _aiohttp_stub.ClientTimeout = object
    sys.modules["aiohttp"] = _aiohttp_stub
if "dotenv" not in sys.modules:
    _dotenv_stub = types.ModuleType("dotenv")
    _dotenv_stub.load_dotenv = lambda *a, **kw: None
    sys.modules["dotenv"] = _dotenv_stub


def _run(coro):
    """Helper to run async coroutines in tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestBrowserSession(unittest.TestCase):
    """Test BrowserSession methods with mocked Playwright."""

    def test_session_created_not_started(self):
        from brain.integrations.browser import BrowserSession
        session = BrowserSession()
        self.assertIsNone(session._playwright)
        self.assertIsNone(session._browser)
        self.assertIsNone(session._page)

    def test_navigate_returns_info(self):
        from brain.integrations.browser import BrowserSession
        session = BrowserSession()
        result = _run(session.navigate("https://example.com"))
        self.assertIn("example.com", result.lower())

    def test_extract_returns_content(self):
        from brain.integrations.browser import BrowserSession
        session = BrowserSession()
        _run(session.ensure_started())
        result = _run(session.extract("body"))
        self.assertIn("Page content", result)

    def test_close_clears_state(self):
        from brain.integrations.browser import BrowserSession
        session = BrowserSession()
        _run(session.ensure_started())
        _run(session.close())
        self.assertIsNone(session._playwright)
        self.assertIsNone(session._browser)
        self.assertIsNone(session._page)


class TestBrowserToolFactories(unittest.TestCase):
    """Test browser tool factory functions."""

    def _make_mock_session(self):
        session = MagicMock()
        session.navigate = AsyncMock(return_value="Navigated to https://example.com. Title: Example")
        session.click = AsyncMock(return_value="Clicked 'button'. Now at: https://example.com/next")
        session.extract = AsyncMock(return_value="Extracted text content")
        session.screenshot = AsyncMock(return_value="Screenshot saved to test.png")
        return session

    def test_navigate_tool(self):
        from shared.agent.tools import make_browser_navigate_tool
        session = self._make_mock_session()
        tool = make_browser_navigate_tool(session)
        self.assertEqual(tool.name, "browser_navigate")
        self.assertTrue(tool.needs_approval)
        result = _run(tool.fn(url="https://example.com"))
        self.assertIn("example.com", result)

    def test_click_tool(self):
        from shared.agent.tools import make_browser_click_tool
        session = self._make_mock_session()
        tool = make_browser_click_tool(session)
        self.assertEqual(tool.name, "browser_click")
        self.assertTrue(tool.needs_approval)
        result = _run(tool.fn(selector="button"))
        self.assertIn("Clicked", result)

    def test_extract_tool_no_approval(self):
        from shared.agent.tools import make_browser_extract_tool
        session = self._make_mock_session()
        tool = make_browser_extract_tool(session)
        self.assertEqual(tool.name, "browser_extract")
        self.assertFalse(tool.needs_approval)

    def test_screenshot_tool_no_approval(self):
        from shared.agent.tools import make_browser_screenshot_tool
        session = self._make_mock_session()
        tool = make_browser_screenshot_tool(session)
        self.assertEqual(tool.name, "browser_screenshot")
        self.assertFalse(tool.needs_approval)

    def test_all_tools_have_schemas(self):
        from shared.agent.tools import (
            make_browser_navigate_tool,
            make_browser_click_tool,
            make_browser_extract_tool,
            make_browser_screenshot_tool,
        )
        session = self._make_mock_session()
        tools = [
            make_browser_navigate_tool(session),
            make_browser_click_tool(session),
            make_browser_extract_tool(session),
            make_browser_screenshot_tool(session),
        ]
        for tool in tools:
            schema = tool.to_schema()
            self.assertIn("name", schema)
            self.assertIn("description", schema)


if __name__ == "__main__":
    unittest.main()
