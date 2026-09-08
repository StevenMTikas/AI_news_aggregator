"""The ``document`` table: composed artifacts, re-renderable from ``content_json`` alone."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Optional

from . import connection, utcnow


@dataclass
class StoredDocument:
    id: str
    run_id: Optional[str]
    project_slug: Optional[str]
    type: str
    title: str
    content_json: str
    rendered_path: Optional[str] = None
    rendered_format: Optional[str] = None
    based_on_brief_ids: list[str] = field(default_factory=list)
    based_on_document_ids: list[str] = field(default_factory=list)
    review_status: str = "unreviewed"
    review_notes: str = ""
    created_at: str = ""


def _row(r) -> StoredDocument:
    return StoredDocument(
        id=r["id"],
        run_id=r["run_id"],
        project_slug=r["project_slug"],
        type=r["type"],
        title=r["title"],
        content_json=r["content_json"],
        rendered_path=r["rendered_path"],
        rendered_format=r["rendered_format"],
        based_on_brief_ids=json.loads(r["based_on_brief_ids"] or "[]"),
        based_on_document_ids=json.loads(r["based_on_document_ids"] or "[]"),
        review_status=r["review_status"],
        review_notes=r["review_notes"],
        created_at=r["created_at"],
    )


def save_document(
    *,
    project_slug: str,
    doc_type: str,
    title: str,
    content_json: str,
    run_id: Optional[str] = None,
    rendered_path: Optional[str] = None,
    rendered_format: Optional[str] = None,
    based_on_brief_ids: Optional[list[str]] = None,
    based_on_document_ids: Optional[list[str]] = None,
    review_status: str = "unreviewed",
    review_notes: str = "",
) -> str:
    doc_id = uuid.uuid4().hex
    with connection() as conn:
        conn.execute(
            """INSERT INTO document
                   (id, run_id, project_slug, type, title, content_json, rendered_path,
                    rendered_format, based_on_brief_ids, based_on_document_ids,
                    review_status, review_notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                doc_id,
                run_id,
                project_slug,
                doc_type,
                title,
                content_json,
                rendered_path,
                rendered_format,
                json.dumps(based_on_brief_ids or []),
                json.dumps(based_on_document_ids or []),
                review_status,
                review_notes,
                utcnow(),
            ),
        )
    return doc_id


def get_document(doc_id: str) -> Optional[StoredDocument]:
    with connection() as conn:
        row = conn.execute("SELECT * FROM document WHERE id = ?", (doc_id,)).fetchone()
    return _row(row) if row else None


def list_documents(*, project_slug: Optional[str] = None, run_id: Optional[str] = None,
                   limit: int = 100) -> list[StoredDocument]:
    clauses, params = [], []
    if project_slug:
        clauses.append("project_slug = ?")
        params.append(project_slug)
    if run_id:
        clauses.append("run_id = ?")
        params.append(run_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)
    with connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM document{where} ORDER BY created_at DESC LIMIT ?", params
        ).fetchall()
    return [_row(r) for r in rows]


def set_rendered_path(doc_id: str, path: str, fmt: str) -> None:
    with connection() as conn:
        conn.execute(
            "UPDATE document SET rendered_path = ?, rendered_format = ? WHERE id = ?",
            (path, fmt, doc_id),
        )
