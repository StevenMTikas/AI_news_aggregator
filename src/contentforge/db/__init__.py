"""SQLite persistence layer.

One connection per operation, file-backed. The active database path is a module global so
tests can point it at a tmp file; on first use for a given path the schema is migrated.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .migrations import MIGRATIONS

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "app.db"
_db_path: Path = Path(os.environ.get("CONTENTFORGE_DB") or _DEFAULT_PATH)
_migrated: set[str] = set()


def db_path() -> Path:
    return _db_path


def set_db_path(path: str | Path) -> None:
    """Point the layer at a different database (tests, alternate profiles)."""
    global _db_path
    _db_path = Path(path)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_migrated(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Force migration now (used at app startup)."""
    with connection():
        pass


def _ensure_migrated(conn: sqlite3.Connection) -> None:
    key = str(_db_path)
    if key in _migrated:
        return
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for target, sql in MIGRATIONS:
        if target > version:
            conn.executescript(sql)
            conn.execute(f"PRAGMA user_version = {target}")
    conn.commit()
    _migrated.add(key)


def reset_migration_cache() -> None:
    """Tests call this after pointing at a fresh path."""
    _migrated.clear()
