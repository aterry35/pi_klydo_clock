from __future__ import annotations

import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from community.app import create_app


PNG = b"\x89PNG\r\n\x1a\n" + b"test-png"


def design_zip(name: str = "Community Test") -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("community-test/loop.mp4", b"fake-mp4-data")
        archive.writestr("community-test/pendulum.png", PNG)
        archive.writestr(
            "community-test/theme.json",
            json.dumps(
                {
                    "name": name,
                    "creator": {
                        "artist": "Test Artist",
                        "watermark": "Test Artist",
                        "watermark_enabled": True,
                    },
                }
            ),
        )
        archive.writestr("community-test/preview.png", PNG)
    return output.getvalue()


class CommunityApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        data = Path(self.temp.name)
        self.app = create_app(
            {
                "TESTING": True,
                "DATA_DIR": data,
                "DATABASE": data / "community.sqlite3",
                "COOKIE_SECURE": False,
                "ALLOWED_ORIGIN": "http://localhost",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def register(self, email: str = "artist@example.com") -> dict[str, object]:
        response = self.client.post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "correct-horse-battery",
                "artistName": "Test Artist",
                "watermark": "Test Artist",
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def test_register_login_and_profile(self) -> None:
        registered = self.register()
        self.assertEqual(registered["user"]["artistName"], "Test Artist")
        csrf = registered["csrfToken"]
        update = self.client.put(
            "/api/auth/profile",
            json={"artistName": "Updated Artist", "watermark": "Updated"},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.get_json()["user"]["watermark"], "Updated")

    def test_publish_like_comment_and_download(self) -> None:
        csrf = self.register()["csrfToken"]
        published = self.client.post(
            "/api/designs",
            data={
                "title": "Community Test",
                "description": "A validated test design.",
                "license": "CC BY-NC 4.0",
                "package": (io.BytesIO(design_zip()), "community-test.zip"),
            },
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(published.status_code, 201, published.get_json())
        design_id = published.get_json()["design"]["id"]

        like = self.client.put(
            f"/api/designs/{design_id}/like", headers={"X-CSRF-Token": csrf}
        )
        self.assertEqual(like.get_json(), {"likeCount": 1, "liked": True})

        comment = self.client.post(
            f"/api/designs/{design_id}/comments",
            json={"body": "This looks good on the clock."},
            headers={"X-CSRF-Token": csrf},
        )
        self.assertEqual(comment.status_code, 201)

        detail = self.client.get(f"/api/designs/{design_id}").get_json()["design"]
        self.assertEqual(detail["likeCount"], 1)
        self.assertEqual(detail["comments"][0]["artistName"], "Test Artist")
        download = self.client.get(detail["downloadUrl"])
        try:
            self.assertEqual(download.status_code, 200)
        finally:
            download.close()

    def test_rejects_invalid_package_and_anonymous_publish(self) -> None:
        anonymous = self.client.post("/api/designs", data={})
        self.assertEqual(anonymous.status_code, 401)
        csrf = self.register()["csrfToken"]
        invalid = self.client.post(
            "/api/designs",
            data={
                "title": "Broken Package",
                "description": "",
                "license": "Personal use only",
                "package": (io.BytesIO(b"not-a-zip"), "broken.zip"),
            },
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )
        self.assertEqual(invalid.status_code, 400)


if __name__ == "__main__":
    unittest.main()
