"""Project profiles, stored in the ``project`` table.

The public API (``list_projects`` / ``get_project`` / ``create_project`` / ``update_project``
/ ``delete_project`` / ``ProjectProfile``) is unchanged from the YAML-backed version so
``app.py`` and the CLI did not need to change.
"""

from __future__ import annotations

import json
import re
from typing import List, Optional

from pydantic import BaseModel, Field

from .db import connection, utcnow


class ProjectProfile(BaseModel):
    slug: str
    name: str
    audience: str
    tone: str
    category_tags: List[str] = Field(default_factory=list)
    author: str
    target_word_count: int = 800
    notes: Optional[str] = None


class ProjectNotFoundError(KeyError):
    pass


class ProjectSlugConflictError(ValueError):
    pass


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


def _row_to_profile(row) -> ProjectProfile:
    return ProjectProfile(
        slug=row["slug"],
        name=row["name"],
        audience=row["audience"],
        tone=row["tone"],
        category_tags=json.loads(row["category_tags"] or "[]"),
        author=row["author"],
        target_word_count=row["target_word_count"],
        notes=row["notes"],
    )


def list_projects() -> List[ProjectProfile]:
    with connection() as conn:
        rows = conn.execute("SELECT * FROM project ORDER BY slug").fetchall()
    return [_row_to_profile(r) for r in rows]


def get_project(slug: str) -> ProjectProfile:
    with connection() as conn:
        row = conn.execute("SELECT * FROM project WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise ProjectNotFoundError(slug)
    return _row_to_profile(row)


def create_project(profile: ProjectProfile) -> ProjectProfile:
    with connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM project WHERE slug = ?", (profile.slug,)
        ).fetchone()
        if exists:
            raise ProjectSlugConflictError(profile.slug)
        conn.execute(
            """INSERT INTO project (slug, name, audience, tone, category_tags, author,
                                    target_word_count, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                profile.slug,
                profile.name,
                profile.audience,
                profile.tone,
                json.dumps(profile.category_tags),
                profile.author,
                profile.target_word_count,
                profile.notes,
                utcnow(),
            ),
        )
    return profile


def update_project(slug: str, profile: ProjectProfile) -> ProjectProfile:
    updated = profile.model_copy(update={"slug": slug})
    with connection() as conn:
        cur = conn.execute(
            """UPDATE project SET name = ?, audience = ?, tone = ?, category_tags = ?,
                                  author = ?, target_word_count = ?, notes = ?
               WHERE slug = ?""",
            (
                updated.name,
                updated.audience,
                updated.tone,
                json.dumps(updated.category_tags),
                updated.author,
                updated.target_word_count,
                updated.notes,
                slug,
            ),
        )
        if cur.rowcount == 0:
            raise ProjectNotFoundError(slug)
    return updated


def delete_project(slug: str) -> None:
    with connection() as conn:
        cur = conn.execute("DELETE FROM project WHERE slug = ?", (slug,))
        if cur.rowcount == 0:
            raise ProjectNotFoundError(slug)
