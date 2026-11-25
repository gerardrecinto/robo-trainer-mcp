"""`robo-trainer-mcp export`: copy everything in the local database to one JSON file."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

from .db import db_path, make_private

USAGE = "usage: robo-trainer-mcp export [FILE] [--force]"


def dump(path: Path) -> dict:
    """Read every table. The database is opened read-only, so an export cannot change it."""
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        names = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        tables = {n: [dict(r) for r in conn.execute(f'SELECT * FROM "{n}"')] for n in names}
    finally:
        conn.close()
    return {
        "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": str(path),
        "row_counts": {n: len(rows) for n, rows in tables.items()},
        "tables": tables,
    }


def main(args: list[str]) -> int:
    force = "--force" in args
    rest = [a for a in args if a != "--force"]
    if len(rest) > 1 or any(a.startswith("-") for a in rest):
        print(USAGE, file=sys.stderr)
        return 2
    src = db_path()
    if not src.exists():
        print(
            f"robo-trainer-mcp: no data at {src}. Log something first, or set ROBO_TRAINER_HOME to the folder that holds data.db.",
            file=sys.stderr,
        )
        return 1
    out = Path(rest[0] if rest else f"robo-trainer-export-{datetime.now().strftime('%Y%m%d')}.json")
    if out.exists() and not force:
        print(f"robo-trainer-mcp: {out} already exists. Pass --force to replace it, or choose another file.", file=sys.stderr)
        return 1
    try:
        doc = dump(src)
        # The file holds health and training records, so it is created private from the start.
        fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(doc, fh, indent=2, default=str)
            fh.write("\n")
        make_private(out)
    except (OSError, sqlite3.Error) as exc:
        print(f"robo-trainer-mcp: export failed: {exc}", file=sys.stderr)
        return 1
    total = sum(doc["row_counts"].values())
    print(f"wrote {out}: {total} rows from {len(doc['tables'])} tables")
    return 0
