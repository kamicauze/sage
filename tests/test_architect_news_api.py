import importlib
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:  # pragma: no cover - optional dependency in test env
    TestClient = None


def _fmt_rfc822(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def _make_rss(items: list[dict[str, str]]) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<rss version='2.0'>",
        "<channel>",
        "<title>Test Feed</title>",
    ]
    for item in items:
        lines.extend(
            [
                "<item>",
                f"<title>{item['title']}</title>",
                f"<link>{item['link']}</link>",
                f"<description>{item['description']}</description>",
                f"<pubDate>{item['pubDate']}</pubDate>",
                "</item>",
            ]
        )
    lines.extend(["</channel>", "</rss>"])
    return "".join(lines)


@unittest.skipIf(TestClient is None, "fastapi is not installed in this environment")
class ArchitectNewsAPITests(unittest.TestCase):
    @staticmethod
    def _reload_server_module():
        import architect.api.server as server_module

        return importlib.reload(server_module)

    def _auth_disabled_env(self):
        return {
            "SAGE_ARCHITECT_API_AUTH_REQUIRED": "false",
            "SAGE_ARCHITECT_API_CORS_ORIGINS": "http://localhost:3000",
            "SAGE_NEWS_X_HANDLES": "OpenAI",
            "SAGE_NEWS_NITTER_BASE_URL": "https://nitter.net",
        }

    @staticmethod
    def _mock_response(text: str) -> Mock:
        response = Mock()
        response.text = text
        response.raise_for_status.return_value = None
        return response

    def test_ai_news_filters_non_relevant_headlines(self):
        now = datetime.now(timezone.utc)
        rss = _make_rss(
            [
                {
                    "title": "OpenAI announces new GPT model for coding",
                    "link": "https://example.com/ai",
                    "description": "The generative AI model improves agent workflows.",
                    "pubDate": _fmt_rfc822(now),
                },
                {
                    "title": "City football league results",
                    "link": "https://example.com/sports",
                    "description": "Weekend sports recap and highlights.",
                    "pubDate": _fmt_rfc822(now),
                },
            ]
        )

        with patch.dict(os.environ, self._auth_disabled_env(), clear=False):
            server_module = self._reload_server_module()
            with patch(
                "architect.api.routes.news._DEFAULT_FEED_SOURCES",
                (
                    {
                        "name": "Unit Feed",
                        "url": "https://example.com/rss",
                        "source_type": "news",
                    },
                ),
            ):
                with patch(
                    "architect.api.routes.news.requests.get",
                    return_value=self._mock_response(rss),
                ):
                    with TestClient(server_module.app) as client:
                        response = client.get("/news/ai?include_x=false&limit=10&query=ai")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["failed_sources"], 0)
        self.assertEqual(len(body["items"]), 1)
        self.assertIn("OpenAI", body["items"][0]["title"])

    def test_ai_news_includes_x_sources_when_enabled(self):
        now = datetime.now(timezone.utc)
        old = now - timedelta(hours=3)
        base_rss = _make_rss(
            [
                {
                    "title": "Anthropic releases Claude update for agents",
                    "link": "https://example.com/anthropic",
                    "description": "New LLM capabilities for tool use.",
                    "pubDate": _fmt_rfc822(old),
                }
            ]
        )
        x_rss = _make_rss(
            [
                {
                    "title": "OpenAI shipped a new reasoning model",
                    "link": "https://x.com/openai/status/123",
                    "description": "AI release details from X.",
                    "pubDate": _fmt_rfc822(now),
                }
            ]
        )

        def fake_get(url: str, *args, **kwargs):
            if "nitter.net/OpenAI/rss" in url:
                return self._mock_response(x_rss)
            return self._mock_response(base_rss)

        with patch.dict(os.environ, self._auth_disabled_env(), clear=False):
            server_module = self._reload_server_module()
            with patch(
                "architect.api.routes.news._DEFAULT_FEED_SOURCES",
                (
                    {
                        "name": "Unit Feed",
                        "url": "https://example.com/rss",
                        "source_type": "news",
                    },
                ),
            ):
                with patch("architect.api.routes.news.requests.get", side_effect=fake_get) as mock_get:
                    with TestClient(server_module.app) as client:
                        response = client.get("/news/ai?include_x=true&limit=10&query=ai")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(any(item["source_type"] == "x" for item in body["items"]))
        called_urls = [args[0] for args, _ in mock_get.call_args_list]
        self.assertTrue(any("nitter.net/OpenAI/rss" in url for url in called_urls))


if __name__ == "__main__":
    unittest.main()
