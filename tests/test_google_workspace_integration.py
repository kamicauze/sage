import os
import sys
import unittest
from unittest.mock import patch


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = str(payload)

    def json(self):
        return self._payload


class GoogleWorkspaceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

        brain_runtime_path = os.path.join(repo_root, "apps", "brain-runtime")
        if brain_runtime_path not in sys.path:
            sys.path.insert(0, brain_runtime_path)

    def test_google_status_command(self):
        from integrations.google_workspace import handle_google_workspace_text

        with patch(
            "integrations.google_workspace.requests.request",
            return_value=_FakeResponse(
                {
                    "configured": True,
                    "connected": True,
                    "redirect_uri": "https://mini.tailnet.ts.net/google/auth/callback",
                    "connected_at": "2026-02-25T21:14:20Z",
                    "scopes": ["https://www.googleapis.com/auth/calendar"],
                }
            ),
        ) as mock_request:
            result = handle_google_workspace_text(
                user_text="/google status",
                api_base_url="http://127.0.0.1:8000",
                conversation_id="c1",
                request_id="r1",
            )

        self.assertTrue(result["handled"])
        self.assertEqual(result["action"], "status")
        self.assertIn("connected=True", result["response_text"])
        called_url = mock_request.call_args.kwargs["url"]
        self.assertTrue(called_url.endswith("/google/status"))

    def test_calendar_query_uses_events_endpoint(self):
        from integrations.google_workspace import handle_google_workspace_text

        with patch(
            "integrations.google_workspace.requests.request",
            return_value=_FakeResponse(
                {
                    "success": True,
                    "count": 1,
                    "items": [
                        {
                            "summary": "Project sync",
                            "start": {"dateTime": "2026-02-26T10:00:00+03:00"},
                        }
                    ],
                }
            ),
        ) as mock_request:
            result = handle_google_workspace_text(
                user_text="what is on my calendar today",
                api_base_url="http://127.0.0.1:8000",
            )

        self.assertTrue(result["handled"])
        self.assertEqual(result["action"], "calendar_list")
        self.assertIn("Project sync", result["response_text"])
        self.assertTrue(mock_request.call_args.kwargs["url"].endswith("/google/calendar/events"))

    def test_add_task_natural_language_uses_default_list(self):
        from integrations.google_workspace import handle_google_workspace_text

        calls = []

        def _fake_request(method, url, **kwargs):
            calls.append((method, url, kwargs))
            if url.endswith("/google/tasks/lists"):
                return _FakeResponse(
                    {
                        "success": True,
                        "items": [{"id": "list_1", "title": "My List"}],
                    }
                )
            if url.endswith("/google/tasks/list/list_1"):
                return _FakeResponse(
                    {
                        "success": True,
                        "task": {"title": "buy milk"},
                    }
                )
            return _FakeResponse({"error": "unexpected"}, status_code=404)

        with patch("integrations.google_workspace.requests.request", side_effect=_fake_request):
            result = handle_google_workspace_text(
                user_text="add task buy milk",
                api_base_url="http://127.0.0.1:8000",
            )

        self.assertTrue(result["handled"])
        self.assertEqual(result["action"], "tasks_create_nl")
        self.assertIn("Task added: buy milk", result["response_text"])
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][1].endswith("/google/tasks/lists"))
        self.assertTrue(calls[1][1].endswith("/google/tasks/list/list_1"))

    def test_non_google_text_is_not_handled(self):
        from integrations.google_workspace import handle_google_workspace_text

        result = handle_google_workspace_text(
            user_text="let us talk about model routing",
            api_base_url="http://127.0.0.1:8000",
        )
        self.assertFalse(result["handled"])


if __name__ == "__main__":
    unittest.main()
