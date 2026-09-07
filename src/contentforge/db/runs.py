"""The ``run`` table: one row per generation, replacing the in-memory tasks dict."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from pydantic import BaseModel, Field

from . import connection, utcnow

TERMINAL = {"completed", "failed", "partial"}


class Run(BaseModel):
    id: str
    project_slug: Optional[str] = None
    kind: str = "atomic"
    status: str = "pending"
    progress: int = 0
    message: str = ""
    topic: str = ""
    topic_slug: str = ""
    params: dict = Field(default_factory=dict)
    error: Optional[str] = None
    cost_usd: float = 0.0
    search_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    created_at: str = ""
    finished_at: Optional[str] = None


def _row_to_run(row) -> Run:
    data = dict(row)
    data["params"] = json.loads(data.get("params") or "{}")
    return Run(**data)


def create_run(*, project_slug: str, topic: str, topic_slug: str = "", kind: str = "atomic",
               params: Optional[dict] = None) -> Run:
    run = Run(
        id=uuid.uuid4().hex,
        project_slug=project_slug,
        kind=kind,
        topic=topic,
        topic_slug=topic_slug or topic,
        params=params or {},
        message="Queued.",
        created_at=utcnow(),
    )
    with connection() as conn:
        conn.execute(
            """INSERT INTO run (id, project_slug, kind, status, progress, message, topic,
                                topic_slug, params, created_at)
               VALUES (:id, :project_slug, :kind, :status, :progress, :message, :topic,
                       :topic_slug, :params, :created_at)""",
            {**run.model_dump(), "params": json.dumps(run.params)},
        )
    return run


def get_run(run_id: str) -> Optional[Run]:
    with connection() as conn:
        row = conn.execute("SELECT * FROM run WHERE id = ?", (run_id,)).fetchone()
    return _row_to_run(row) if row else None


def list_runs(*, project_slug: Optional[str] = None, limit: int = 50) -> list[Run]:
    query = "SELECT * FROM run"
    params: list[Any] = []
    if project_slug:
        query += " WHERE project_slug = ?"
        params.append(project_slug)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_run(r) for r in rows]


def update_run(run_id: str, **fields: Any) -> None:
    if not fields:
        return
    if "params" in fields:
        fields["params"] = json.dumps(fields["params"])
    if fields.get("status") in TERMINAL and "finished_at" not in fields:
        fields["finished_at"] = utcnow()
    assignments = ", ".join(f"{k} = :{k}" for k in fields)
    with connection() as conn:
        conn.execute(f"UPDATE run SET {assignments} WHERE id = :id", {**fields, "id": run_id})


def count_active() -> int:
    with connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM run WHERE status IN ('pending', 'running')"
        ).fetchone()
    return row[0]
