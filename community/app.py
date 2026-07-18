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
REPORT_REASONS = {
    "copyright",
    "inappropriate",
    "spam",
    "broken_package",
    "other",
}
DESIGN_STATUSES = {"published", "hidden"}
USER_STATUSES = {"active", "suspended"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    artist_name TEXT NOT NULL,
    watermark TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member',
    status TEXT NOT NULL DEFAULT 'active',
    suspended_at TEXT,
    suspension_reason TEXT,
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

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    design_id TEXT NOT NULL REFERENCES designs(id) ON DELETE CASCADE,
    reporter_user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    details TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolution TEXT,
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    resolved_by_user_id TEXT REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS moderation_actions (
    id TEXT PRIMARY KEY,
    actor_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    actor_name TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_designs_created ON designs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_comments_design ON comments(design_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_actions_created ON moderation_actions(created_at DESC);
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


def ensure_column(db: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def init_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        db.executescript(SCHEMA)
        ensure_column(db, "users", "role", "TEXT NOT NULL DEFAULT 'member'")
        ensure_column(db, "users", "status", "TEXT NOT NULL DEFAULT 'active'")
        ensure_column(db, "users", "suspended_at", "TEXT")
        ensure_column(db, "users", "suspension_reason", "TEXT")
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
               u.id, u.email, u.artist_name, u.watermark, u.role, u.status,
               u.suspended_at, u.suspension_reason, u.created_at
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
        "role": row["role"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


def require_auth(*, csrf: bool = False) -> tuple[sqlite3.Row, sqlite3.Row]:
    session = current_session()
    if not session:
        raise ApiError("Sign in is required.", 401)
    if session[1]["status"] != "active":
        raise ApiError("This account is suspended.", 403)
    if csrf and not secrets.compare_digest(
        request.headers.get("X-CSRF-Token", ""), session[0]["csrf_token"]
    ):
        raise ApiError("The session security token is missing or expired.", 403)
    return session


def agent_admin(app: Flask) -> sqlite3.Row | None:
    expected_hash = str(app.config.get("AGENT_TOKEN_HASH", ""))
    authorization = request.headers.get("Authorization", "")
    if not expected_hash or not authorization.startswith("Bearer "):
        return None
    token = authorization[7:].strip()
    if not token or not secrets.compare_digest(token_hash(token), expected_hash):
        return None
    email = str(app.config.get("AGENT_ADMIN_EMAIL", "")).strip().lower()
    row = get_db().execute(
        "SELECT * FROM users WHERE email = ? AND role = 'admin' AND status = 'active'",
        (email,),
    ).fetchone()
    if not row:
        raise ApiError("The agent administrator account is unavailable.", 403)
    return row


def require_admin(app: Flask, *, csrf: bool = False) -> tuple[sqlite3.Row, str, bool]:
    agent = agent_admin(app)
    if agent is not None:
        agent_name = str(app.config.get("AGENT_NAME", "")).strip() or agent["artist_name"]
        return agent, f"agent:{agent_name}", True
    _session, user = require_auth(csrf=csrf)
    if user["role"] != "admin":
        raise ApiError("Administrator access is required.", 403)
    return user, user["artist_name"], False


def record_action(
    db: sqlite3.Connection,
    *,
    actor: sqlite3.Row,
    actor_name: str,
    action: str,
    target_type: str,
    target_id: str,
    reason: str,
    metadata: dict[str, object] | None = None,
) -> str:
    action_id = str(uuid.uuid4())
    db.execute(
        """
        INSERT INTO moderation_actions
            (id, actor_user_id, actor_name, action, target_type, target_id, reason, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            action_id,
            actor["id"],
            actor_name,
            action,
            target_type,
            target_id,
            reason,
            json.dumps(metadata or {}, sort_keys=True),
            utc_now(),
        ),
    )
    return action_id


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


def design_payload(
    row: sqlite3.Row, liked: bool = False, *, include_status: bool = False
) -> dict[str, object]:
    design_id = row["id"]
    payload = {
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
    if include_status:
        payload["status"] = row["status"]
        payload["userId"] = row["user_id"]
    return payload


def select_design(
    design_id: str, user_id: str | None = None, *, include_hidden: bool = False
) -> sqlite3.Row | None:
    return get_db().execute(
        """
        SELECT d.*, u.artist_name, u.watermark,
               (SELECT COUNT(*) FROM likes l WHERE l.design_id = d.id) AS like_count,
               (SELECT COUNT(*) FROM comments c WHERE c.design_id = d.id) AS comment_count,
               EXISTS(SELECT 1 FROM likes mine WHERE mine.design_id = d.id AND mine.user_id = ?) AS liked_by_me
        FROM designs d JOIN users u ON u.id = d.user_id
        WHERE d.id = ? AND (d.status = 'published' OR ?)
        """,
        (user_id or "", design_id, int(include_hidden)),
    ).fetchone()


def request_can_view_hidden(app: Flask) -> bool:
    agent = agent_admin(app)
    if agent is not None:
        return True
    session = current_session()
    return bool(
        session
        and session[1]["role"] == "admin"
        and session[1]["status"] == "active"
    )


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
        AGENT_TOKEN_HASH=os.environ.get("PICLOCK_AGENT_TOKEN_HASH", ""),
        AGENT_ADMIN_EMAIL=os.environ.get("PICLOCK_AGENT_ADMIN_EMAIL", ""),
        AGENT_NAME=os.environ.get("PICLOCK_AGENT_NAME", ""),
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
        if row["status"] != "active":
            raise ApiError("This account is suspended.", 403)
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
        row = select_design(
            design_id, user_id, include_hidden=request_can_view_hidden(app)
        )
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
        row = select_design(design_id, include_hidden=request_can_view_hidden(app))
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
        row = select_design(design_id, include_hidden=request_can_view_hidden(app))
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

    @app.post("/api/designs/<design_id>/reports")
    def report_design(design_id: str):
        _session, user = require_auth(csrf=True)
        user_key = f"report-user:{user['id']}"
        ip_key = f"report-ip:{request.remote_addr}"
        if not limiter.allow(user_key, limit=8, window_seconds=86400) or not limiter.allow(
            ip_key, limit=30, window_seconds=86400
        ):
            raise ApiError("Report limit reached. Try again tomorrow.", 429)
        design = select_design(design_id, user["id"])
        if not design:
            raise ApiError("Design not found.", 404)
        if design["user_id"] == user["id"]:
            raise ApiError("You cannot report your own design.")
        payload = request.get_json(silent=True) or {}
        reason = str(payload.get("reason", "")).strip()
        if reason not in REPORT_REASONS:
            raise ApiError("Choose a valid report reason.")
        details = clean_text(payload.get("details"), minimum=0, maximum=1000, field="Details")
        if reason == "other" and len(details) < 10:
            raise ApiError("Describe the issue when choosing Other.")
        duplicate = get_db().execute(
            """
            SELECT id FROM reports
            WHERE design_id = ? AND reporter_user_id = ? AND status = 'open'
            """,
            (design_id, user["id"]),
        ).fetchone()
        if duplicate:
            raise ApiError("You already have an open report for this design.", 409)
        report_id = str(uuid.uuid4())
        created = utc_now()
        get_db().execute(
            """
            INSERT INTO reports
                (id, design_id, reporter_user_id, reason, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (report_id, design_id, user["id"], reason, details, created),
        )
        get_db().commit()
        return jsonify({"report": {"id": report_id, "status": "open", "createdAt": created}}), 201

    @app.get("/api/admin/summary")
    def admin_summary():
        require_admin(app)
        db = get_db()
        row = db.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM designs WHERE status = 'published') AS published_designs,
              (SELECT COUNT(*) FROM designs WHERE status = 'hidden') AS hidden_designs,
              (SELECT COUNT(*) FROM reports WHERE status = 'open') AS open_reports,
              (SELECT COUNT(*) FROM users WHERE status = 'active') AS active_users,
              (SELECT COUNT(*) FROM users WHERE status = 'suspended') AS suspended_users,
              (SELECT COALESCE(SUM(downloads), 0) FROM designs) AS total_downloads
            """
        ).fetchone()
        return jsonify(
            {
                "summary": {
                    "publishedDesigns": row["published_designs"],
                    "hiddenDesigns": row["hidden_designs"],
                    "openReports": row["open_reports"],
                    "activeUsers": row["active_users"],
                    "suspendedUsers": row["suspended_users"],
                    "totalDownloads": row["total_downloads"],
                }
            }
        )

    @app.get("/api/admin/reports")
    def admin_reports():
        require_admin(app)
        status = request.args.get("status", "open")
        if status not in {"open", "resolved", "dismissed", "all"}:
            raise ApiError("Choose a valid report status.")
        condition = "" if status == "all" else "WHERE r.status = ?"
        params: tuple[object, ...] = () if status == "all" else (status,)
        rows = get_db().execute(
            f"""
            SELECT r.*, d.title, d.status AS design_status,
                   owner.artist_name AS design_artist,
                   reporter.artist_name AS reporter_name,
                   resolver.artist_name AS resolver_name
            FROM reports r
            JOIN designs d ON d.id = r.design_id
            JOIN users owner ON owner.id = d.user_id
            JOIN users reporter ON reporter.id = r.reporter_user_id
            LEFT JOIN users resolver ON resolver.id = r.resolved_by_user_id
            {condition}
            ORDER BY CASE WHEN r.status = 'open' THEN 0 ELSE 1 END, r.created_at ASC
            LIMIT 250
            """,
            params,
        ).fetchall()
        return jsonify(
            {
                "reports": [
                    {
                        "id": row["id"],
                        "designId": row["design_id"],
                        "designTitle": row["title"],
                        "designArtist": row["design_artist"],
                        "designStatus": row["design_status"],
                        "reporterName": row["reporter_name"],
                        "reason": row["reason"],
                        "details": row["details"],
                        "status": row["status"],
                        "resolution": row["resolution"],
                        "resolverName": row["resolver_name"],
                        "createdAt": row["created_at"],
                        "resolvedAt": row["resolved_at"],
                    }
                    for row in rows
                ]
            }
        )

    @app.get("/api/admin/designs")
    def admin_designs():
        admin, _actor_name, _is_agent = require_admin(app)
        status = request.args.get("status", "all")
        if status not in DESIGN_STATUSES | {"all"}:
            raise ApiError("Choose a valid design status.")
        condition = "" if status == "all" else "WHERE d.status = ?"
        params: list[object] = [admin["id"]]
        if status != "all":
            params.append(status)
        rows = get_db().execute(
            f"""
            SELECT d.*, u.artist_name, u.watermark,
                   (SELECT COUNT(*) FROM likes l WHERE l.design_id = d.id) AS like_count,
                   (SELECT COUNT(*) FROM comments c WHERE c.design_id = d.id) AS comment_count,
                   (SELECT COUNT(*) FROM reports r WHERE r.design_id = d.id AND r.status = 'open') AS open_report_count,
                   EXISTS(SELECT 1 FROM likes mine WHERE mine.design_id = d.id AND mine.user_id = ?) AS liked_by_me
            FROM designs d JOIN users u ON u.id = d.user_id
            {condition}
            ORDER BY d.created_at DESC
            LIMIT 250
            """,
            tuple(params),
        ).fetchall()
        payloads = []
        for row in rows:
            payload = design_payload(row, row["liked_by_me"], include_status=True)
            payload["openReportCount"] = row["open_report_count"]
            payloads.append(payload)
        return jsonify({"designs": payloads})

    @app.get("/api/admin/users")
    def admin_users():
        require_admin(app)
        rows = get_db().execute(
            """
            SELECT u.*,
                   (SELECT COUNT(*) FROM designs d WHERE d.user_id = u.id) AS design_count,
                   (SELECT COUNT(*) FROM reports r WHERE r.reporter_user_id = u.id) AS report_count
            FROM users u ORDER BY u.created_at DESC LIMIT 250
            """
        ).fetchall()
        return jsonify(
            {
                "users": [
                    {
                        **public_user(row),
                        "designCount": row["design_count"],
                        "reportCount": row["report_count"],
                        "suspendedAt": row["suspended_at"],
                        "suspensionReason": row["suspension_reason"],
                    }
                    for row in rows
                ]
            }
        )

    @app.get("/api/admin/designs/<design_id>/package")
    def admin_design_package(design_id: str):
        require_admin(app)
        row = select_design(design_id, include_hidden=True)
        if not row:
            raise ApiError("Design not found.", 404)
        path = Path(row["package_path"])
        if not path.is_file():
            raise ApiError("Design package is unavailable.", 404)
        return send_file(
            path,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{row['slug']}.zip",
            conditional=True,
        )

    @app.get("/api/admin/actions")
    def admin_actions():
        require_admin(app)
        rows = get_db().execute(
            "SELECT * FROM moderation_actions ORDER BY created_at DESC LIMIT 250"
        ).fetchall()
        return jsonify(
            {
                "actions": [
                    {
                        "id": row["id"],
                        "actorName": row["actor_name"],
                        "action": row["action"],
                        "targetType": row["target_type"],
                        "targetId": row["target_id"],
                        "reason": row["reason"],
                        "metadata": json.loads(row["metadata_json"]),
                        "createdAt": row["created_at"],
                    }
                    for row in rows
                ]
            }
        )

    @app.post("/api/admin/designs/<design_id>/status")
    def moderate_design(design_id: str):
        actor, actor_name, _is_agent = require_admin(app, csrf=True)
        key = f"admin-action:{actor['id']}"
        if not limiter.allow(key, limit=120, window_seconds=3600):
            raise ApiError("Administrator action limit reached.", 429)
        payload = request.get_json(silent=True) or {}
        status = str(payload.get("status", ""))
        if status not in DESIGN_STATUSES:
            raise ApiError("Choose a valid design status.")
        reason = clean_text(payload.get("reason"), minimum=3, maximum=500, field="Reason")
        db = get_db()
        design = db.execute("SELECT * FROM designs WHERE id = ?", (design_id,)).fetchone()
        if not design:
            raise ApiError("Design not found.", 404)
        previous = design["status"]
        db.execute("UPDATE designs SET status = ? WHERE id = ?", (status, design_id))
        record_action(
            db,
            actor=actor,
            actor_name=actor_name,
            action="hide_design" if status == "hidden" else "restore_design",
            target_type="design",
            target_id=design_id,
            reason=reason,
            metadata={"previousStatus": previous, "newStatus": status},
        )
        db.commit()
        row = select_design(design_id, actor["id"], include_hidden=True)
        return jsonify({"design": design_payload(row, row["liked_by_me"], include_status=True)})

    @app.post("/api/admin/users/<user_id>/status")
    def moderate_user(user_id: str):
        actor, actor_name, _is_agent = require_admin(app, csrf=True)
        payload = request.get_json(silent=True) or {}
        status = str(payload.get("status", ""))
        if status not in USER_STATUSES:
            raise ApiError("Choose a valid account status.")
        reason = clean_text(payload.get("reason"), minimum=3, maximum=500, field="Reason")
        db = get_db()
        target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not target:
            raise ApiError("Account not found.", 404)
        if target["id"] == actor["id"] and status == "suspended":
            raise ApiError("Administrators cannot suspend their own account.")
        if target["role"] == "admin" and status == "suspended":
            active_admins = db.execute(
                "SELECT COUNT(*) FROM users WHERE role = 'admin' AND status = 'active'"
            ).fetchone()[0]
            if active_admins <= 1:
                raise ApiError("The last active administrator cannot be suspended.")
        previous = target["status"]
        suspended_at = utc_now() if status == "suspended" else None
        suspension_reason = reason if status == "suspended" else None
        db.execute(
            "UPDATE users SET status = ?, suspended_at = ?, suspension_reason = ? WHERE id = ?",
            (status, suspended_at, suspension_reason, user_id),
        )
        if status == "suspended":
            db.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        record_action(
            db,
            actor=actor,
            actor_name=actor_name,
            action="suspend_user" if status == "suspended" else "restore_user",
            target_type="user",
            target_id=user_id,
            reason=reason,
            metadata={"previousStatus": previous, "newStatus": status},
        )
        db.commit()
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return jsonify({"user": public_user(row)})

    @app.post("/api/admin/reports/<report_id>/resolve")
    def resolve_report(report_id: str):
        actor, actor_name, _is_agent = require_admin(app, csrf=True)
        payload = request.get_json(silent=True) or {}
        status = str(payload.get("status", ""))
        if status not in {"resolved", "dismissed"}:
            raise ApiError("Choose resolved or dismissed.")
        resolution = clean_text(
            payload.get("resolution"), minimum=3, maximum=500, field="Resolution"
        )
        db = get_db()
        report = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        if not report:
            raise ApiError("Report not found.", 404)
        db.execute(
            """
            UPDATE reports
            SET status = ?, resolution = ?, resolved_at = ?, resolved_by_user_id = ?
            WHERE id = ?
            """,
            (status, resolution, utc_now(), actor["id"], report_id),
        )
        record_action(
            db,
            actor=actor,
            actor_name=actor_name,
            action="resolve_report" if status == "resolved" else "dismiss_report",
            target_type="report",
            target_id=report_id,
            reason=resolution,
            metadata={"designId": report["design_id"], "reportReason": report["reason"]},
        )
        db.commit()
        return jsonify({"report": {"id": report_id, "status": status}})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False)
