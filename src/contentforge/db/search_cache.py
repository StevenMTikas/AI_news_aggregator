"""SQLite-backed ``SearchCache`` -- the cross-run persistence the Phase 3 ``InMemorySearchCache``
stood in for. TTL is applied on read: ``news`` results go stale in a day, everything else in
a week.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Sequence

from ..providers.base import SearchResult
from . import connection

_TTL = {"news": timedelta(days=1)}
_DEFAULT_TTL = timedelta(days=7)


def _ttl_for(key: str) -> timedelta:
    kind = key.split(":", 1)[0]
    return _TTL.get(kind, _DEFAULT_TTL)


class SqliteSearchCache:
    def get(self, key: str) -> list[SearchResult] | None:
        with connection() as conn:
            row = conn.execute(
                "SELECT result_json, stored_at FROM serper_cache WHERE key = ?", (key,)
            ).fetchone()
        if not row:
            return None
        stored_at = datetime.fromisoformat(row["stored_at"])
        if datetime.now(timezone.utc) - stored_at > _ttl_for(key):
            return None
        return [SearchResult(**r) for r in json.loads(row["result_json"])]

    def put(self, key: str, results: Sequence[SearchResult]) -> None:
        if not results:  # never cache an empty/failed response
            return
        payload = json.dumps([r.__dict__ for r in results])
        kind = key.split(":", 1)[0]
        with connection() as conn:
            conn.execute(
                """INSERT INTO serper_cache (key, query, search_type, result_json, stored_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET result_json = excluded.result_json,
                                                 stored_at = excluded.stored_at""",
                (key, key, kind, payload, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
