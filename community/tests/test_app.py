from __future__ import annotations

import io
import json
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path

from community.app import create_app, init_database, token_hash


PNG = b"\x89PNG\r\n\x1a\n" + b"test-png"


def design_zip(name: str = "Community Test", artist: str = "Test Artist") -> bytes:
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
                        "artist": artist,
                        "watermark": artist,
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
        self.database = data / "community.sqlite3"
        self.app = create_app(
            {
                "TESTING": True,
                "DATA_DIR": data,
                "DATABASE": self.database,
                "COOKIE_SECURE": False,
                "ALLOWED_ORIGIN": "http://localhost",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def register(
        self,
        email: str = "artist@example.com",
        *,
        client=None,
        artist: str = "Test Artist",
    ) -> dict[str, object]:
        response = (client or self.client).post(
            "/api/auth/register",
            json={
                "email": email,
                "password": "correct-horse-battery",
                "artistName": artist,
                "watermark": artist,
            },
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def promote_admin(self, client, email: str = "admin@example.com") -> dict[str, object]:
        payload = self.register(email, client=client, artist="Administrator")
        db = sqlite3.connect(self.database)
        db.execute("UPDATE users SET role = 'admin' WHERE email = ?", (email,))
        db.commit()
        db.close()
        return payload

    def submit_design(self, client, csrf: str, *, title: str = "Community Test"):
        return client.post(
            "/api/designs",
            data={
                "title": title,
                "description": "A validated test design.",
                "license": "CC BY-NC 4.0",
                "package": (io.BytesIO(design_zip()), "community-test.zip"),
            },
            headers={"X-CSRF-Token": csrf},
            content_type="multipart/form-data",
        )

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

    def test_submission_requires_approval_before_public_interaction(self) -> None:
        csrf = self.register()["csrfToken"]
        submitted = self.submit_design(self.client, csrf)
        self.assertEqual(submitted.status_code, 201, submitted.get_json())
        self.assertEqual(submitted.get_json()["design"]["status"], "pending_review")
        design_id = submitted.get_json()["design"]["id"]

        public = self.app.test_client()
        self.assertEqual(public.get(f"/api/designs/{design_id}").status_code, 404)
        self.assertEqual(public.get("/api/designs").get_json()["designs"], [])

        admin = self.app.test_client()
        admin_payload = self.promote_admin(admin)
        pending = admin.get("/api/admin/designs?status=pending_review").get_json()["designs"]
        self.assertEqual([item["id"] for item in pending], [design_id])
        preview = admin.get(pending[0]["previewUrl"])
        try:
            self.assertEqual(preview.status_code, 200)
        finally:
            preview.close()
        package = admin.get(pending[0]["downloadUrl"])
        try:
            self.assertEqual(package.status_code, 200)
        finally:
            package.close()

        invalid = admin.post(
            f"/api/admin/designs/{design_id}/status",
            json={"status": "hidden", "reason": "Invalid transition test."},
            headers={"X-CSRF-Token": admin_payload["csrfToken"]},
        )
        self.assertEqual(invalid.status_code, 409)
        approved = admin.post(
            f"/api/admin/designs/{design_id}/status",
            json={"status": "published", "reason": "Preview and package reviewed."},
            headers={"X-CSRF-Token": admin_payload["csrfToken"]},
        )
        self.assertEqual(approved.status_code, 200, approved.get_json())
        self.assertEqual(approved.get_json()["design"]["status"], "published")
        self.assertEqual(approved.get_json()["design"]["reviewReason"], "Preview and package reviewed.")
        self.assertIsNotNone(approved.get_json()["design"]["reviewedAt"])

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
        actions = admin.get("/api/admin/actions").get_json()["actions"]
        self.assertEqual(actions[0]["action"], "approve_design")

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

    def test_report_admin_hide_suspend_resolve_and_audit(self) -> None:
        owner = self.app.test_client()
        owner_csrf = self.register(client=owner)["csrfToken"]
        submitted = self.submit_design(owner, owner_csrf, title="Reported Design")
        design_id = submitted.get_json()["design"]["id"]

        admin = self.app.test_client()
        admin_payload = self.promote_admin(admin)
        approved = admin.post(
            f"/api/admin/designs/{design_id}/status",
            json={"status": "published", "reason": "Approved for moderation test."},
            headers={"X-CSRF-Token": admin_payload["csrfToken"]},
        )
        self.assertEqual(approved.status_code, 200, approved.get_json())

        reporter = self.app.test_client()
        reporter_payload = self.register(
            "reporter@example.com", client=reporter, artist="Reporter"
        )
        report = reporter.post(
            f"/api/designs/{design_id}/reports",
            json={"reason": "copyright", "details": "This appears to copy my work."},
            headers={"X-CSRF-Token": reporter_payload["csrfToken"]},
        )
        self.assertEqual(report.status_code, 201, report.get_json())
        report_id = report.get_json()["report"]["id"]

        db = sqlite3.connect(self.database)
        reporter_id = db.execute(
            "SELECT id FROM users WHERE email = 'reporter@example.com'"
        ).fetchone()[0]
        db.commit()
        db.close()

        summary = admin.get("/api/admin/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.get_json()["summary"]["openReports"], 1)

        hidden = admin.post(
            f"/api/admin/designs/{design_id}/status",
            json={"status": "hidden", "reason": "Reviewing a copyright report."},
            headers={"X-CSRF-Token": admin_payload["csrfToken"]},
        )
        self.assertEqual(hidden.status_code, 200, hidden.get_json())
        self.assertEqual(hidden.get_json()["design"]["status"], "hidden")
        self.assertEqual(self.app.test_client().get(f"/api/designs/{design_id}").status_code, 404)
        self.assertEqual(admin.get(f"/api/designs/{design_id}").status_code, 200)

        suspended = admin.post(
            f"/api/admin/users/{reporter_id}/status",
            json={"status": "suspended", "reason": "Repeated abusive reports."},
            headers={"X-CSRF-Token": admin_payload["csrfToken"]},
        )
        self.assertEqual(suspended.status_code, 200)
        blocked = reporter.post(
            f"/api/designs/{design_id}/comments",
            json={"body": "This should be blocked."},
            headers={"X-CSRF-Token": reporter_payload["csrfToken"]},
        )
        self.assertEqual(blocked.status_code, 401)

        resolved = admin.post(
            f"/api/admin/reports/{report_id}/resolve",
            json={"status": "resolved", "resolution": "Design hidden pending ownership review."},
            headers={"X-CSRF-Token": admin_payload["csrfToken"]},
        )
        self.assertEqual(resolved.status_code, 200)
        actions = admin.get("/api/admin/actions").get_json()["actions"]
        self.assertEqual({item["action"] for item in actions}, {
            "approve_design", "hide_design", "suspend_user", "resolve_report"
        })

    def test_agent_token_can_read_and_moderate_as_admin(self) -> None:
        owner_csrf = self.register()["csrfToken"]
        submitted = self.submit_design(self.client, owner_csrf, title="Agent Review")
        design_id = submitted.get_json()["design"]["id"]
        db = sqlite3.connect(self.database)
        db.execute("UPDATE users SET role = 'admin' WHERE email = 'artist@example.com'")
        db.commit()
        db.close()
        self.app.config.update(
            AGENT_TOKEN_HASH=token_hash("agent-secret"),
            AGENT_ADMIN_EMAIL="artist@example.com",
            AGENT_NAME="aterry45",
        )
        headers = {"Authorization": "Bearer agent-secret"}
        self.assertEqual(self.client.get("/api/admin/summary", headers=headers).status_code, 200)
        rejected = self.client.post(
            f"/api/admin/designs/{design_id}/status",
            json={"status": "rejected", "reason": "Automated package validation failed."},
            headers=headers,
        )
        self.assertEqual(rejected.status_code, 200, rejected.get_json())
        self.assertEqual(rejected.get_json()["design"]["status"], "rejected")
        actions = self.client.get("/api/admin/actions", headers=headers).get_json()["actions"]
        self.assertEqual(actions[0]["actorName"], "agent:aterry45")
        self.assertEqual(actions[0]["action"], "reject_design")

    def test_existing_database_receives_moderation_columns(self) -> None:
        old_database = Path(self.temp.name) / "old.sqlite3"
        db = sqlite3.connect(old_database)
        db.execute(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY, email TEXT, password_hash TEXT,
                artist_name TEXT, watermark TEXT, created_at TEXT
            )
            """
        )
        db.commit()
        db.close()
        init_database(old_database)
        db = sqlite3.connect(old_database)
        user_columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
        design_columns = {row[1] for row in db.execute("PRAGMA table_info(designs)")}
        db.close()
        self.assertTrue({"role", "status", "suspended_at", "suspension_reason"} <= user_columns)
        self.assertTrue({"reviewed_at", "reviewed_by_user_id", "review_reason"} <= design_columns)


if __name__ == "__main__":
    unittest.main()
