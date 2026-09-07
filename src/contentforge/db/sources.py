"""The ``source`` table -- sources broken out of a brief for retrieval and (Phase 7)
per-claim credibility.
"""

from __future__ import annotations

import uuid
from typing import Optional, Sequence

from ..schemas import Source
from . import connection, utcnow


def save_sources(brief_id: str, project_slug: str, sources: Sequence[Source]) -> None:
    now = utcnow()
    rows = [
        (uuid.uuid4().hex, brief_id, project_slug, s.url, s.title, s.domain,
         s.published, s.takeaway, s.credibility, now)
        for s in sources
    ]
    if not rows:
        return
    with connection() as conn:
        conn.executemany(
            """INSERT INTO source
                   (id, brief_id, project_slug, url, title, domain, published_at, takeaway,
                    credibility, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )


def list_sources(brief_id: str) -> list[Source]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM source WHERE brief_id = ?", (brief_id,)).fetchall()
    return [
        Source(url=r["url"], title=r["title"], domain=r["domain"], published=r["published_at"],
               takeaway=r["takeaway"], credibility=r["credibility"])
        for r in rows
    ]


def set_credibility(source_id: str, credibility: Optional[str]) -> None:
    with connection() as conn:
        conn.execute("UPDATE source SET credibility = ? WHERE id = ?", (credibility, source_id))
