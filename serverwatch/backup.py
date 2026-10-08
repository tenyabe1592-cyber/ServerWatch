from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def backup(source: Path, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"serverwatch-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.db"
    source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    target_db = sqlite3.connect(destination)
    try:
        source_db.backup(target_db)
        result = target_db.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"backup integrity check failed: {result}")
    finally:
        target_db.close()
        source_db.close()
    destination.chmod(0o600)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent ServerWatch SQLite backup")
    parser.add_argument("--source", type=Path, default=Path("/var/lib/serverwatch/serverwatch.db"))
    parser.add_argument("--destination", type=Path, default=Path("/var/backups/serverwatch"))
    args = parser.parse_args()
    print(backup(args.source, args.destination))


if __name__ == "__main__":
    main()

