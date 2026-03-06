"""
Browser Automation for Sage Agents.

Provides a Playwright-based browser session that agents can use for
web navigation, form filling, data extraction, and screenshots.
Lazy-loads Playwright to avoid import errors when not installed.
"""
from __future__ import annotations

import os
import time
from typing import Optional


class BrowserSession:
    """Manages a Playwright browser session for agent use."""

    def __init__(self, headless: bool = True):
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._page = None

    async def ensure_started(self) -> None:
        """Lazy-start the browser on first use."""
        if self._page is not None:
            return

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._page = await self._browser.new_page()
        print("[Browser] Session started (headless={})".format(self._headless))

    async def navigate(self, url: str) -> str:
        """Navigate to a URL and return page info."""
        await self.ensure_started()
        response = await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
        status = response.status if response else "unknown"
        title = await self._page.title()
        return f"Navigated to {self._page.url}. Status: {status}. Title: {title}"

    async def click(self, selector: str) -> str:
        """Click an element matching a CSS selector."""
        await self.ensure_started()
        await self._page.click(selector, timeout=5000)
        await self._page.wait_for_load_state("domcontentloaded")
        title = await self._page.title()
        return f"Clicked '{selector}'. Now at: {self._page.url}. Title: {title}"

    async def fill(self, selector: str, value: str) -> str:
        """Fill a form field."""
        await self.ensure_started()
        await self._page.fill(selector, value)
        return f"Filled '{selector}' with value."

    async def extract(self, selector: str = "body") -> str:
        """Extract text content from a CSS selector."""
        await self.ensure_started()
        try:
            content = await self._page.inner_text(selector, timeout=5000)
        except Exception as e:
            return f"Error extracting '{selector}': {e}"
        # Truncate for LLM context
        if len(content) > 4000:
            content = content[:4000] + "\n... (truncated)"
        return content

    async def screenshot(self, path: str = None) -> str:
        """Take a screenshot of the current page."""
        await self.ensure_started()
        if not path:
            screenshots_dir = os.path.join(".sage_memory", "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            path = os.path.join(screenshots_dir, f"{int(time.time())}.png")
        else:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        await self._page.screenshot(path=path)
        return f"Screenshot saved to {path}"

    async def get_url(self) -> str:
        """Get current page URL."""
        if self._page is None:
            return "No browser session active."
        return self._page.url

    async def close(self) -> None:
        """Close the browser session."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._playwright = None
        self._browser = None
        self._page = None
        print("[Browser] Session closed")
