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
    project_slug: Optional[str] = None


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
        expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat(timespec="microseconds")
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
        project_slug=row["project_slug"],
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
        project_slug=row["project_slug"],
    )


def list_briefs(*, project_slug: Optional[str] = None, run_ids: Optional[list[str]] = None,
                limit: int = 100) -> list[StoredBrief]:
    clauses, params = [], []
    if project_slug:
        clauses.append("project_slug = ?")
        params.append(project_slug)
    if run_ids:
        clauses.append(f"run_id IN ({', '.join('?' * len(run_ids))})")
        params.extend(run_ids)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM research_brief{where} ORDER BY created_at DESC LIMIT ?", params
        ).fetchall()
    return [
        StoredBrief(
            id=r["id"], brief=ResearchBrief.model_validate_json(r["content_json"]),
            created_at=r["created_at"], expires_at=r["expires_at"], project_slug=r["project_slug"],
        )
        for r in rows
    ]


def supersede(old_brief_id: str, new_brief_id: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE research_brief SET superseded_by = ? WHERE id = ?",
            (new_brief_id, old_brief_id),
        )
