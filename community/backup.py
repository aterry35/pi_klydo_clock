from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


def backup(data_dir: Path, keep_days: int = 14) -> Path:
    source = data_dir / "community.sqlite3"
    destination_dir = data_dir / "backups"
    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    destination = destination_dir / f"community-{stamp}.sqlite3"
    source_db = sqlite3.connect(source)
    destination_db = sqlite3.connect(destination)
    try:
        source_db.backup(destination_db)
    finally:
        destination_db.close()
        source_db.close()
    cutoff = datetime.now(UTC) - timedelta(days=keep_days)
    for path in destination_dir.glob("community-*.sqlite3"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
        if modified < cutoff:
            path.unlink()
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--keep-days", type=int, default=14)
    args = parser.parse_args()
    print(backup(args.data, args.keep_days))


if __name__ == "__main__":
    main()
