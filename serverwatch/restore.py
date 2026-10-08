from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def restore(source: Path, destination: Path, *, replace: bool = False) -> None:
    if destination.exists() and not replace:
        raise FileExistsError("destination exists; stop ServerWatch and pass --replace explicitly")
    check = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"source integrity check failed: {result}")
    finally:
        check.close()
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_db = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    destination_db = sqlite3.connect(destination)
    try:
        source_db.backup(destination_db)
    finally:
        destination_db.close()
        source_db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a verified ServerWatch SQLite backup")
    parser.add_argument("source", type=Path)
    parser.add_argument("--destination", type=Path, default=Path("/var/lib/serverwatch/serverwatch.db"))
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    restore(args.source, args.destination, replace=args.replace)


if __name__ == "__main__":
    main()

