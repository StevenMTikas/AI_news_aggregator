"""The ``research_brief`` table. The brief is stored whole as JSON; a few columns are lifted
out for lookup (reuse a fresh brief instead of re-researching).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..schemas import ResearchBrief
from . import connection, utcnow


@dataclass
class StoredBrief:
    id: str
    brief: ResearchBrief
    created_at: str
    expires_at: Optional[str]


def save_brief(
    brief: ResearchBrief,
    *,
    project_slug: str,
    normalized_topic: str,
    run_id: Optional[str] = None,
    ttl_days: Optional[int] = None,
) -> str:
    brief_id = uuid.uuid4().hex
    expires_at = None
    if ttl_days:
        expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat(timespec="seconds")
    with connection() as conn:
        conn.execute(
            """INSERT INTO research_brief
                   (id, run_id, project_slug, topic, normalized_topic, content_json,
                    created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                brief_id,
                run_id,
                project_slug,
                brief.topic,
                normalized_topic,
                brief.model_dump_json(),
                utcnow(),
                expires_at,
            ),
        )
    return brief_id


def find_fresh_brief(project_slug: str, normalized_topic: str) -> Optional[StoredBrief]:
    now = utcnow()
    with connection() as conn:
        row = conn.execute(
            """SELECT * FROM research_brief
               WHERE project_slug = ? AND normalized_topic = ? AND superseded_by IS NULL
                 AND (expires_at IS NULL OR expires_at > ?)
               ORDER BY created_at DESC LIMIT 1""",
            (project_slug, normalized_topic, now),
        ).fetchone()
    if not row:
        return None
    return StoredBrief(
        id=row["id"],
        brief=ResearchBrief.model_validate_json(row["content_json"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


def get_brief(brief_id: str) -> Optional[StoredBrief]:
    with connection() as conn:
        row = conn.execute("SELECT * FROM research_brief WHERE id = ?", (brief_id,)).fetchone()
    if not row:
        return None
    return StoredBrief(
        id=row["id"],
        brief=ResearchBrief.model_validate_json(row["content_json"]),
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


def supersede(old_brief_id: str, new_brief_id: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE research_brief SET superseded_by = ? WHERE id = ?",
            (new_brief_id, old_brief_id),
        )
