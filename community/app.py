from __future__ import annotations

import hashlib
import io
import json
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
import uuid
import zipfile
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath

from flask import Flask, g, jsonify, request, send_file
from werkzeug.security import check_password_hash, generate_password_hash


SESSION_COOKIE = "piclock_session"
SESSION_DAYS = 30
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024
MAX_PREVIEW_BYTES = 5 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ALLOWED_LICENSES = {
    "CC BY 4.0",
    "CC BY-NC 4.0",
    "Personal use only",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    watermark TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS designs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    license TEXT NOT NULL,
    package_path TEXT NOT NULL,
    preview_path TEXT NOT NULL,
    package_bytes INTEGER NOT NULL,
    downloads INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'published',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS likes (
    design_id TEXT NOT NULL REFERENCES designs(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    PRIMARY KEY (design_id, user_id)
);

CREATE TABLE IF NOT EXISTS comments (
    id TEXT PRIMARY KEY,
    design_id TEXT NOT NULL REFERENCES designs(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_designs_created ON designs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_design ON comments(design_id, created_at ASC);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:64] or "clock-design"


def clean_text(value: object, *, minimum: int, maximum: int, field: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) < minimum or len(text) > maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum} characters.")
    return text


class RateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True


limiter = RateLimiter()


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        db = sqlite3.connect(g.app_config["DATABASE"], timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("PRAGMA journal_mode = WAL")
        g.db = db
    return g.db


def close_db(_error: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.executescript(SCHEMA)
        db.commit()
    finally:
        db.close()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def current_session() -> tuple[sqlite3.Row, sqlite3.Row] | None:
    token = request.cookies.get(SESSION_COOKIE, "")
    if not token:
        return None
    row = get_db().execute(
        """
        SELECT s.token_hash, s.csrf_token, s.expires_at,
               u.id, u.email, u.artist_name, u.watermark, u.created_at
        FROM sessions s JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ? AND s.expires_at > ?
        """,
        (token_hash(token), utc_now()),
    ).fetchone()
    if not row:
        return None
    return row, row


def public_user(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": row["id"],
        "email": row["email"],
        "artistName": row["artist_name"],
        "watermark": row["watermark"],
        "createdAt": row["created_at"],
    }


def require_auth(*, csrf: bool = False) -> tuple[sqlite3.Row, sqlite3.Row]:
    session = current_session()
    if not session:
        raise ApiError("Sign in is required.", 401)
    if csrf and not secrets.compare_digest(
        request.headers.get("X-CSRF-Token", ""), session[0]["csrf_token"]
    ):
        raise ApiError("The session security token is missing or expired.", 403)
    return session


def require_same_origin(app: Flask) -> None:
    origin = request.headers.get("Origin")
    allowed = app.config.get("ALLOWED_ORIGIN", "").rstrip("/")
    if origin and allowed and origin.rstrip("/") != allowed:
        raise ApiError("Cross-origin requests are not allowed.", 403)


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


def set_session_cookie(response, user_id: str, app: Flask):
    token = secrets.token_urlsafe(40)
    csrf = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(days=SESSION_DAYS)
    db = get_db()
    db.execute(
        "INSERT INTO sessions (token_hash, user_id, csrf_token, expires_at) VALUES (?, ?, ?, ?)",
        (token_hash(token), user_id, csrf, expires.isoformat()),
    )
    db.execute("DELETE FROM sessions WHERE expires_at <= ?", (utc_now(),))
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 86400,
        httponly=True,
        secure=app.config["COOKIE_SECURE"],
        samesite="Lax",
        path="/",
    )
    return csrf


def validate_design_zip(raw: bytes) -> tuple[str, bytes, dict[str, object]]:
    if not raw or len(raw) > MAX_UPLOAD_BYTES:
        raise ApiError("The design package must be smaller than 25 MB.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as error:
        raise ApiError("Upload a valid designer ZIP package.") from error

    infos = [item for item in archive.infolist() if not item.is_dir()]
    if not infos or len(infos) > 100:
        raise ApiError("The ZIP package has an invalid number of files.")
    if sum(item.file_size for item in infos) > MAX_UNCOMPRESSED_BYTES:
        raise ApiError("The expanded package is too large.")

    names: dict[str, zipfile.ZipInfo] = {}
    roots: set[str] = set()
    for info in infos:
        path = PurePosixPath(info.filename)
        if path.is_absolute() or ".." in path.parts or len(path.parts) < 2:
            raise ApiError("The ZIP package contains an unsafe path.")
        if info.flag_bits & 0x1:
            raise ApiError("Encrypted ZIP files are not supported.")
        roots.add(path.parts[0])
        names["/".join(path.parts[1:])] = info
    if len(roots) != 1:
        raise ApiError("The ZIP must contain one top-level design folder.")

    dial_name = next((name for name in ("loop.mp4", "loop.webm") if name in names), None)
    pendulum_name = next((name for name in ("pendulum.png", "pendulum.svg") if name in names), None)
    required = [dial_name, pendulum_name, "theme.json", "preview.png"]
    if any(name is None or name not in names for name in required):
        raise ApiError("The ZIP must include loop video, pendulum artwork, theme.json, and preview.png.")

    preview = archive.read(names["preview.png"])
    if len(preview) > MAX_PREVIEW_BYTES or not preview.startswith(PNG_SIGNATURE):
        raise ApiError("preview.png is missing, invalid, or too large.")
    if pendulum_name == "pendulum.png":
        pendulum = archive.read(names[pendulum_name])
        if not pendulum.startswith(PNG_SIGNATURE):
            raise ApiError("pendulum.png is not a valid PNG image.")

    try:
        theme = json.loads(archive.read(names["theme.json"]))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ApiError("theme.json is not valid JSON.") from error
    if not isinstance(theme, dict) or not str(theme.get("name", "")).strip():
        raise ApiError("theme.json must include a design name.")
    creator = theme.get("creator") if isinstance(theme.get("creator"), dict) else {}
    if (
        not str(creator.get("artist", "")).strip()
        or not str(creator.get("watermark", "")).strip()
        or not creator.get("watermark_enabled")
    ):
        raise ApiError("Community packages must include an enabled creator watermark.")
    return roots.pop(), preview, theme


def design_payload(row: sqlite3.Row, liked: bool = False) -> dict[str, object]:
    design_id = row["id"]
    return {
        "id": design_id,
        "slug": row["slug"],
        "title": row["title"],
        "description": row["description"],
        "license": row["license"],
        "artistName": row["artist_name"],
        "watermark": row["watermark"],
        "previewUrl": f"/api/designs/{design_id}/preview",
        "downloadUrl": f"/api/designs/{design_id}/download",
        "packageBytes": row["package_bytes"],
        "downloads": row["downloads"],
        "likeCount": row["like_count"],
        "commentCount": row["comment_count"],
        "likedByMe": bool(liked),
        "createdAt": row["created_at"],
    }


def select_design(design_id: str, user_id: str | None = None) -> sqlite3.Row | None:
    return get_db().execute(
        """
        SELECT d.*, u.artist_name, u.watermark,
               (SELECT COUNT(*) FROM likes l WHERE l.design_id = d.id) AS like_count,
               (SELECT COUNT(*) FROM comments c WHERE c.design_id = d.id) AS comment_count,
               EXISTS(SELECT 1 FROM likes mine WHERE mine.design_id = d.id AND mine.user_id = ?) AS liked_by_me
        FROM designs d JOIN users u ON u.id = d.user_id
        WHERE d.id = ? AND d.status = 'published'
        """,
        (user_id or "", design_id),
    ).fetchone()


def create_app(config: dict[str, object] | None = None) -> Flask:
    app = Flask(__name__)
    default_data_dir = Path(__file__).resolve().parent / ".data"
    data_dir = Path(os.environ.get("PICLOCK_DATA_DIR", default_data_dir))
    app.config.update(
        DATA_DIR=data_dir,
        DATABASE=data_dir / "community.sqlite3",
        COOKIE_SECURE=os.environ.get("PICLOCK_COOKIE_SECURE", "1") != "0",
        ALLOWED_ORIGIN=os.environ.get(
            "PICLOCK_ALLOWED_ORIGIN", "https://designer.18-191-209-51.sslip.io"
        ),
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES + 1024 * 1024,
    )
    if config:
        app.config.update(config)
    app.config["DATA_DIR"] = Path(app.config["DATA_DIR"])
    app.config["DATABASE"] = Path(app.config["DATABASE"])
    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)
    (app.config["DATA_DIR"] / "designs").mkdir(exist_ok=True)
    init_database(app.config["DATABASE"])

    @app.before_request
    def prepare_request() -> None:
        g.app_config = app.config
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            require_same_origin(app)

    app.teardown_appcontext(close_db)

    @app.errorhandler(ApiError)
    def handle_api_error(error: ApiError):
        return jsonify({"error": error.message}), error.status

    @app.errorhandler(413)
    def handle_too_large(_error):
        return jsonify({"error": "The upload is larger than 25 MB."}), 413

    @app.after_request
    def api_headers(response):
        if request.path.startswith("/api/"):
            response.headers["X-Content-Type-Options"] = "nosniff"
            if request.path.startswith("/api/auth/"):
                response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    def health():
        get_db().execute("SELECT 1").fetchone()
        return jsonify({"status": "ok"})

    @app.post("/api/auth/register")
    def register():
        key = f"register:{request.remote_addr}"
        if not limiter.allow(key, limit=8, window_seconds=3600):
            raise ApiError("Too many registration attempts. Try again later.", 429)
        payload = request.get_json(silent=True) or {}
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        artist_name = clean_text(payload.get("artistName"), minimum=2, maximum=60, field="Artist name")
        watermark = clean_text(payload.get("watermark") or artist_name, minimum=2, maximum=60, field="Watermark")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
            raise ApiError("Enter a valid email address.")
        if len(password) < 10 or len(password) > 200:
            raise ApiError("Password must contain at least 10 characters.")
        user_id = str(uuid.uuid4())
        created = utc_now()
        try:
            get_db().execute(
                "INSERT INTO users (id, email, password_hash, artist_name, watermark, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, email, generate_password_hash(password), artist_name, watermark, created),
            )
            get_db().commit()
        except sqlite3.IntegrityError as error:
            raise ApiError("An account already exists for this email.", 409) from error
        row = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        payload = {"user": public_user(row)}
        response = jsonify(payload)
        csrf = set_session_cookie(response, user_id, app)
        payload["csrfToken"] = csrf
        response.set_data(json.dumps(payload))
        return response, 201

    @app.post("/api/auth/login")
    def login():
        key = f"login:{request.remote_addr}"
        if not limiter.allow(key, limit=15, window_seconds=900):
            raise ApiError("Too many sign-in attempts. Try again later.", 429)
        payload = request.get_json(silent=True) or {}
        email = str(payload.get("email", "")).strip().lower()
        password = str(payload.get("password", ""))
        row = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if not row or not check_password_hash(row["password_hash"], password):
            raise ApiError("Email or password is incorrect.", 401)
        payload = {"user": public_user(row)}
        response = jsonify(payload)
        csrf = set_session_cookie(response, row["id"], app)
        payload["csrfToken"] = csrf
        response.set_data(json.dumps(payload))
        return response

    @app.get("/api/auth/me")
    def me():
        session = current_session()
        if not session:
            return jsonify({"user": None, "csrfToken": None})
        return jsonify({"user": public_user(session[1]), "csrfToken": session[0]["csrf_token"]})

    @app.post("/api/auth/logout")
    def logout():
        session, _user = require_auth(csrf=True)
        get_db().execute("DELETE FROM sessions WHERE token_hash = ?", (session["token_hash"],))
        get_db().commit()
        response = jsonify({"ok": True})
        response.delete_cookie(SESSION_COOKIE, path="/", samesite="Lax")
        return response

    @app.put("/api/auth/profile")
    def update_profile():
        _session, user = require_auth(csrf=True)
        payload = request.get_json(silent=True) or {}
        artist = clean_text(payload.get("artistName"), minimum=2, maximum=60, field="Artist name")
        watermark = clean_text(payload.get("watermark") or artist, minimum=2, maximum=60, field="Watermark")
        get_db().execute(
            "UPDATE users SET artist_name = ?, watermark = ? WHERE id = ?",
            (artist, watermark, user["id"]),
        )
        get_db().commit()
        row = get_db().execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
        return jsonify({"user": public_user(row)})

    @app.get("/api/designs")
    def list_designs():
        sort = request.args.get("sort", "new")
        query = re.sub(r"[%_]", "", request.args.get("query", "").strip())[:80]
        try:
            limit = min(48, max(1, int(request.args.get("limit", "24"))))
            offset = max(0, int(request.args.get("offset", "0")))
        except ValueError as error:
            raise ApiError("Invalid pagination values.") from error
        session = current_session()
        user_id = session[1]["id"] if session else ""
        order = "like_count DESC, d.created_at DESC" if sort == "popular" else "d.created_at DESC"
        rows = get_db().execute(
            f"""
            SELECT d.*, u.artist_name, u.watermark,
                   (SELECT COUNT(*) FROM likes l WHERE l.design_id = d.id) AS like_count,
                   (SELECT COUNT(*) FROM comments c WHERE c.design_id = d.id) AS comment_count,
                   EXISTS(SELECT 1 FROM likes mine WHERE mine.design_id = d.id AND mine.user_id = ?) AS liked_by_me
            FROM designs d JOIN users u ON u.id = d.user_id
            WHERE d.status = 'published'
              AND (? = '' OR d.title LIKE ? OR u.artist_name LIKE ?)
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            (user_id, query, f"%{query}%", f"%{query}%", limit, offset),
        ).fetchall()
        return jsonify({"designs": [design_payload(row, row["liked_by_me"]) for row in rows]})

    @app.get("/api/designs/<design_id>")
    def get_design(design_id: str):
        session = current_session()
        user_id = session[1]["id"] if session else None
        row = select_design(design_id, user_id)
        if not row:
            raise ApiError("Design not found.", 404)
        comments = get_db().execute(
            """
            SELECT c.id, c.body, c.created_at, u.artist_name
            FROM comments c JOIN users u ON u.id = c.user_id
            WHERE c.design_id = ? ORDER BY c.created_at ASC LIMIT 100
            """,
            (design_id,),
        ).fetchall()
        payload = design_payload(row, row["liked_by_me"])
        payload["comments"] = [
            {
                "id": item["id"],
                "body": item["body"],
                "artistName": item["artist_name"],
                "createdAt": item["created_at"],
            }
            for item in comments
        ]
        return jsonify({"design": payload})

    @app.post("/api/designs")
    def publish_design():
        _session, user = require_auth(csrf=True)
        key = f"upload:{user['id']}"
        if not limiter.allow(key, limit=5, window_seconds=3600):
            raise ApiError("Upload limit reached. Try again later.", 429)
        title = clean_text(request.form.get("title"), minimum=2, maximum=80, field="Title")
        description = clean_text(
            request.form.get("description"), minimum=0, maximum=600, field="Description"
        )
        license_name = str(request.form.get("license", "CC BY-NC 4.0"))
        if license_name not in ALLOWED_LICENSES:
            raise ApiError("Choose a supported license.")
        upload = request.files.get("package")
        if upload is None:
            raise ApiError("Attach the exported design ZIP.")
        raw = upload.read(MAX_UPLOAD_BYTES + 1)
        _package_root, preview, theme = validate_design_zip(raw)
        if str(theme["creator"]["artist"]).strip() != user["artist_name"]:
            raise ApiError("The package artist name must match the signed-in profile.")
        design_id = str(uuid.uuid4())
        slug = f"{slugify(title)}-{design_id[:8]}"
        design_dir = app.config["DATA_DIR"] / "designs" / design_id
        design_dir.mkdir(parents=True)
        package_path = design_dir / "design.zip"
        preview_path = design_dir / "preview.png"
        package_path.write_bytes(raw)
        preview_path.write_bytes(preview)
        try:
            get_db().execute(
                """
                INSERT INTO designs
                    (id, user_id, slug, title, description, license, package_path, preview_path, package_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    design_id,
                    user["id"],
                    slug,
                    title,
                    description,
                    license_name,
                    str(package_path),
                    str(preview_path),
                    len(raw),
                    utc_now(),
                ),
            )
            get_db().commit()
        except Exception:
            shutil.rmtree(design_dir, ignore_errors=True)
            raise
        row = select_design(design_id, user["id"])
        return jsonify({"design": design_payload(row, False)}), 201

    @app.get("/api/designs/<design_id>/preview")
    def design_preview(design_id: str):
        row = select_design(design_id)
        if not row:
            raise ApiError("Design not found.", 404)
        path = Path(row["preview_path"])
        if not path.is_file():
            raise ApiError("Preview is unavailable.", 404)
        response = send_file(path, mimetype="image/png", conditional=True, max_age=3600)
        response.headers["Cache-Control"] = "public, max-age=3600"
        return response

    @app.get("/api/designs/<design_id>/download")
    def download_design(design_id: str):
        row = select_design(design_id)
        if not row:
            raise ApiError("Design not found.", 404)
        path = Path(row["package_path"])
        if not path.is_file():
            raise ApiError("Design package is unavailable.", 404)
        get_db().execute("UPDATE designs SET downloads = downloads + 1 WHERE id = ?", (design_id,))
        get_db().commit()
        return send_file(
            path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{row['slug']}.zip",
            conditional=True,
        )

    @app.put("/api/designs/<design_id>/like")
    def like_design(design_id: str):
        _session, user = require_auth(csrf=True)
        if not select_design(design_id, user["id"]):
            raise ApiError("Design not found.", 404)
        get_db().execute(
            "INSERT OR IGNORE INTO likes (design_id, user_id, created_at) VALUES (?, ?, ?)",
            (design_id, user["id"], utc_now()),
        )
        get_db().commit()
        row = select_design(design_id, user["id"])
        return jsonify({"liked": True, "likeCount": row["like_count"]})

    @app.delete("/api/designs/<design_id>/like")
    def unlike_design(design_id: str):
        _session, user = require_auth(csrf=True)
        get_db().execute(
            "DELETE FROM likes WHERE design_id = ? AND user_id = ?", (design_id, user["id"])
        )
        get_db().commit()
        row = select_design(design_id, user["id"])
        if not row:
            raise ApiError("Design not found.", 404)
        return jsonify({"liked": False, "likeCount": row["like_count"]})

    @app.post("/api/designs/<design_id>/comments")
    def add_comment(design_id: str):
        _session, user = require_auth(csrf=True)
        key = f"comment:{user['id']}"
        if not limiter.allow(key, limit=20, window_seconds=3600):
            raise ApiError("Comment limit reached. Try again later.", 429)
        if not select_design(design_id, user["id"]):
            raise ApiError("Design not found.", 404)
        payload = request.get_json(silent=True) or {}
        body = clean_text(payload.get("body"), minimum=1, maximum=500, field="Comment")
        comment_id = str(uuid.uuid4())
        created = utc_now()
        get_db().execute(
            "INSERT INTO comments (id, design_id, user_id, body, created_at) VALUES (?, ?, ?, ?, ?)",
            (comment_id, design_id, user["id"], body, created),
        )
        get_db().commit()
        return jsonify(
            {
                "comment": {
                    "id": comment_id,
                    "body": body,
                    "artistName": user["artist_name"],
                    "createdAt": created,
                }
            }
        ), 201

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)
