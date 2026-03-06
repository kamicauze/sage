import os
import sys
import unittest
from unittest.mock import patch

try:
    import fastapi  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    fastapi = None


@unittest.skipIf(fastapi is None, "fastapi is not installed in this environment")
class GoogleDriveRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = os.path.dirname(os.path.dirname(__file__))
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)

    def test_extract_google_drive_file_id_from_doc_url(self):
        from architect.api.routes.google_workspace import extract_google_drive_file_id

        file_id = extract_google_drive_file_id("https://docs.google.com/document/d/abcDEF1234567890ghiJKLmnop/edit")
        self.assertEqual(file_id, "abcDEF1234567890ghiJKLmnop")

    def test_search_drive_files_formats_results(self):
        from architect.api.routes import google_workspace as route

        with patch.object(
            route,
            "_google_request",
            return_value={
                "files": [
                    {
                        "id": "doc_123",
                        "name": "BaBish Spec",
                        "mimeType": "application/vnd.google-apps.document",
                        "webViewLink": "https://docs.google.com/document/d/doc_123/edit",
                        "modifiedTime": "2026-03-03T10:00:00Z",
                        "owners": [{"displayName": "Martin", "emailAddress": "martin@example.com"}],
                    }
                ]
            },
        ):
            response = route.search_drive_files(q="babish")

        self.assertTrue(response["success"])
        self.assertEqual(response["count"], 1)
        self.assertEqual(response["items"][0]["kind"], "doc")
        self.assertEqual(response["items"][0]["title"], "BaBish Spec")

    def test_get_drive_file_content_truncates_text(self):
        from architect.api.routes import google_workspace as route

        with patch.object(
            route,
            "get_drive_file_metadata",
            return_value={
                "asset_id": "doc_123",
                "title": "BaBish Spec",
                "kind": "doc",
                "url": "https://docs.google.com/document/d/doc_123/edit",
                "mime_type": "application/vnd.google-apps.document",
            },
        ), patch.object(
            route,
            "_drive_text_content",
            return_value={
                "content": "A" * 200,
                "content_type": "text/plain",
                "content_available": True,
            },
        ):
            response = route.get_drive_file_content("doc_123", max_chars=64)

        self.assertTrue(response["success"])
        self.assertTrue(response["content_available"])
        self.assertTrue(response["truncated"])
        self.assertEqual(len(response["content"]), 64)


if __name__ == "__main__":
    unittest.main()
