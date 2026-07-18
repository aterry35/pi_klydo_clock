from __future__ import annotations

import argparse
import io
import json
import sqlite3
import uuid
import zipfile
from pathlib import Path

from werkzeug.security import generate_password_hash

from .app import SCHEMA, slugify, utc_now


SYSTEM_USER_ID = "00000000-0000-0000-0000-000000000001"


def package_design(folder: Path) -> tuple[bytes, bytes, dict[str, object]]:
    theme = json.loads((folder / "theme.json").read_text())
    preview = (folder / "preview.png").read_bytes()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.iterdir()):
            if path.is_file() and not path.name.startswith("."):
                archive.write(path, f"{folder.name}/{path.name}")
    return buffer.getvalue(), preview, theme


def seed(data_dir: Path, designs_dir: Path) -> int:
    database = data_dir / "community.sqlite3"
    storage = data_dir / "designs"
    storage.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(database)
    db.executescript(SCHEMA)
    db.execute(
        """
        INSERT OR IGNORE INTO users (id, email, password_hash, artist_name, watermark, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            SYSTEM_USER_ID,
            "built-in@pi-klydo-clock.local",
            generate_password_hash(uuid.uuid4().hex),
            "Pi Klydo Clock",
            "Pi Klydo Clock",
            utc_now(),
        ),
    )
    added = 0
    for folder in sorted(path for path in designs_dir.iterdir() if path.is_dir()):
        if not all((folder / name).is_file() for name in ("theme.json", "preview.png")):
            continue
        title = str(json.loads((folder / "theme.json").read_text()).get("name") or folder.name)
        slug = f"built-in-{slugify(folder.name)}"
        if db.execute("SELECT 1 FROM designs WHERE slug = ?", (slug,)).fetchone():
            continue
        raw, preview, _theme = package_design(folder)
        design_id = str(uuid.uuid4())
        design_storage = storage / design_id
        design_storage.mkdir()
        package_path = design_storage / "design.zip"
        preview_path = design_storage / "preview.png"
        package_path.write_bytes(raw)
        preview_path.write_bytes(preview)
        db.execute(
            """
            INSERT INTO designs
                (id, user_id, slug, title, description, license, package_path, preview_path, package_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                design_id,
                SYSTEM_USER_ID,
                slug,
                title,
                "Official starting design for the Pi Klydo Clock.",
                "Personal use only",
                str(package_path),
                str(preview_path),
                len(raw),
                utc_now(),
            ),
        )
        added += 1
    db.commit()
    db.close()
    return added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--designs", type=Path, required=True)
    args = parser.parse_args()
    print(f"Seeded {seed(args.data, args.designs)} design(s).")


if __name__ == "__main__":
    main()
