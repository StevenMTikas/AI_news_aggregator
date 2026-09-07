"""Project profiles, stored in the ``project`` table.

The public API (``list_projects`` / ``get_project`` / ``create_project`` / ``update_project``
/ ``delete_project`` / ``ProjectProfile``) is unchanged from the YAML-backed version so
``app.py`` and the CLI did not need to change.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

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

    # Phase 6 enrichment -- all optional so older callers/tests are unaffected.
    subject_focus: str = ""  # what this project is *about*; steers research + retrieval
    style_guide: str = ""  # free-text voice rules (more expressive than `tone`)
    banned_phrases: List[str] = Field(default_factory=list)  # exact strings the editor removes
    recency_days: Optional[int] = None  # research recency window
    min_sources: int = 5
    prefer_domains: List[str] = Field(default_factory=list)
    exclude_domains: List[str] = Field(default_factory=list)
    default_model: Optional[str] = None
    length_overrides: Dict[str, int] = Field(default_factory=dict)  # {recipe: word_count}


class ProjectNotFoundError(KeyError):
    pass


class ProjectSlugConflictError(ValueError):
    pass


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "project"


_ENRICH_COLUMNS = (
    "subject_focus", "style_guide", "banned_phrases", "recency_days", "min_sources",
    "prefer_domains", "exclude_domains", "default_model", "length_overrides",
)
_JSON_COLUMNS = {"category_tags", "banned_phrases", "prefer_domains", "exclude_domains", "length_overrides"}


def _row_to_profile(row) -> ProjectProfile:
    keys = row.keys()
    data = {
        "slug": row["slug"],
        "name": row["name"],
        "audience": row["audience"],
        "tone": row["tone"],
        "category_tags": json.loads(row["category_tags"] or "[]"),
        "author": row["author"],
        "target_word_count": row["target_word_count"],
        "notes": row["notes"],
    }
    for col in _ENRICH_COLUMNS:
        if col in keys and row[col] is not None:
            data[col] = json.loads(row[col]) if col in _JSON_COLUMNS else row[col]
    return ProjectProfile(**data)


def _write_values(profile: ProjectProfile) -> dict:
    values = profile.model_dump()
    for col in _JSON_COLUMNS:
        values[col] = json.dumps(values[col])
    return values


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


_COLUMNS = (
    "slug", "name", "audience", "tone", "category_tags", "author", "target_word_count",
    "notes", *_ENRICH_COLUMNS,
)


def create_project(profile: ProjectProfile) -> ProjectProfile:
    values = _write_values(profile)
    with connection() as conn:
        if conn.execute("SELECT 1 FROM project WHERE slug = ?", (profile.slug,)).fetchone():
            raise ProjectSlugConflictError(profile.slug)
        cols = ", ".join(_COLUMNS) + ", created_at"
        placeholders = ", ".join(f":{c}" for c in _COLUMNS) + ", :created_at"
        conn.execute(
            f"INSERT INTO project ({cols}) VALUES ({placeholders})",
            {**values, "created_at": utcnow()},
        )
    return profile


def update_project(slug: str, profile: ProjectProfile) -> ProjectProfile:
    updated = profile.model_copy(update={"slug": slug})
    values = _write_values(updated)
    assignments = ", ".join(f"{c} = :{c}" for c in _COLUMNS if c != "slug")
    with connection() as conn:
        cur = conn.execute(
            f"UPDATE project SET {assignments} WHERE slug = :slug", {**values, "slug": slug}
        )
        if cur.rowcount == 0:
            raise ProjectNotFoundError(slug)
    return updated


def delete_project(slug: str) -> None:
    with connection() as conn:
        cur = conn.execute("DELETE FROM project WHERE slug = ?", (slug,))
        if cur.rowcount == 0:
            raise ProjectNotFoundError(slug)
