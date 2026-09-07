"""``python -m contentforge.db.backup`` -- snapshot the SQLite database.

Uses SQLite's online backup API (safe while the app is running), writes a timestamped copy
under ``data/backups/`` and keeps the most recent ``keep``.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import db_path


def backup_database(dest_dir: Optional[Path] = None, *, keep: int = 10) -> Path:
    src = db_path()
    if not src.exists():
        raise FileNotFoundError(f"no database at {src}")
    dest_dir = Path(dest_dir) if dest_dir else src.parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest_dir / f"app-{stamp}.db"

    source = sqlite3.connect(src)
    target = sqlite3.connect(dest)
    try:
        with target:
            source.backup(target)
    finally:
        source.close()
        target.close()

    snapshots = sorted(dest_dir.glob("app-*.db"))
    for old in snapshots[:-keep]:
        old.unlink()
    return dest


if __name__ == "__main__":  # pragma: no cover
    path = backup_database()
    print(f"backup written: {path}")
