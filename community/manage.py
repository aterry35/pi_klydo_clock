from __future__ import annotations

import argparse
import json
import os
import sqlite3
import uuid
from pathlib import Path

from community.app import init_database, utc_now


def promote(email: str, data_dir: Path) -> None:
    database = data_dir / "community.sqlite3"
    init_database(database)
    db = sqlite3.connect(database)
    db.row_factory = sqlite3.Row
    try:
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email.strip().lower(),)
        ).fetchone()
        if not user:
            raise SystemExit(f"No account found for {email}.")
        db.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user["id"],))
        db.execute(
            """
            INSERT INTO moderation_actions
                (id, actor_user_id, actor_name, action, target_type, target_id,
                 reason, metadata_json, created_at)
            VALUES (?, NULL, 'system-deploy', 'promote_admin', 'user', ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                user["id"],
                "Administrator assigned by the server operator.",
                json.dumps({"email": user["email"]}),
                utc_now(),
            ),
        )
        db.commit()
        print(f"Administrator enabled: {user['artist_name']} <{user['email']}>")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Pi Clock community accounts")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path(os.environ.get("PICLOCK_DATA_DIR", Path(__file__).parent / ".data")),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    promote_parser = commands.add_parser("promote", help="Assign the administrator role")
    promote_parser.add_argument("--email", required=True)
    args = parser.parse_args()
    if args.command == "promote":
        promote(args.email, args.data)


if __name__ == "__main__":
    main()
