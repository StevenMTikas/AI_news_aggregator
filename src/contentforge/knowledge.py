"""Per-project knowledge store: hybrid retrieval over prior briefs and documents.

Two channels -- SQLite FTS5 (BM25 keyword) and embedding cosine (semantic) -- fused with
reciprocal-rank fusion. The embedding channel is skipped when no ``EmbeddingProvider`` is
configured, so retrieval still works offline. This is what lets a project get "smarter":
before new research, the pipeline is primed with what the project already established.
"""

from __future__ import annotations

import array
import math
import re
from dataclasses import dataclass
from typing import Optional, Sequence

from pydantic import BaseModel

from .db import connection
from .providers.base import EmbeddingProvider
from .schemas import BlogContent, ResearchBrief

_RRF_K = 60
_CHARS_PER_TOKEN = 4
_WORD = re.compile(r"[A-Za-z0-9]+")


@dataclass
class Excerpt:
    kind: str  # "brief" | "document"
    ref_id: str
    title: str
    text: str
    created_at: str
    score: float = 0.0


def _pack(vec: Sequence[float]) -> bytes:
    return array.array("f", vec).tobytes()


def _unpack(blob: bytes) -> list[float]:
    a = array.array("f")
    a.frombytes(blob)
    return list(a)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _match_query(query: str) -> str:
    terms = _WORD.findall(query.lower())
    return " OR ".join(f'"{t}"' for t in terms) if terms else '""'


def brief_text(brief: ResearchBrief) -> str:
    parts = [brief.topic, brief.summary, *brief.key_findings, *brief.trends, *brief.audience_impact]
    parts += [s.takeaway for s in brief.sources if s.takeaway]
    return "\n".join(p for p in parts if p)


def document_text(content: BaseModel) -> str:
    if isinstance(content, BlogContent):
        parts = [content.title, content.hook, *content.key_points]
        parts += [s.heading + "\n" + s.body for s in content.sections]
        return "\n".join(parts)
    return content.model_dump_json()


class KnowledgeStore:
    def __init__(self, *, embedder: Optional[EmbeddingProvider] = None) -> None:
        self.embedder = embedder

    # -- indexing ------------------------------------------------------------------

    def index_brief(self, brief_id: str, project_slug: str, brief: ResearchBrief) -> None:
        text = brief_text(brief)
        with connection() as conn:
            conn.execute(
                "INSERT INTO brief_fts (ref_id, project_slug, body) VALUES (?, ?, ?)",
                (brief_id, project_slug, text),
            )
            blob = self._embed(text)
            if blob is not None:
                conn.execute("UPDATE research_brief SET embedding = ? WHERE id = ?", (blob, brief_id))

    def index_document(self, doc_id: str, project_slug: str, content: BaseModel) -> None:
        text = document_text(content)
        with connection() as conn:
            conn.execute(
                "INSERT INTO doc_fts (ref_id, project_slug, body) VALUES (?, ?, ?)",
                (doc_id, project_slug, text),
            )
            blob = self._embed(text)
            if blob is not None:
                conn.execute("UPDATE document SET embedding = ? WHERE id = ?", (blob, doc_id))

    # -- retrieval ---------------------------------------------------------------

    def retrieve(self, project_slug: str, query: str, *, k: int = 6, token_budget: int = 1500) -> list[Excerpt]:
        ranked = self._fuse(
            self._fts_rank("brief_fts", project_slug, query),
            self._fts_rank("doc_fts", project_slug, query),
            self._vector_rank("research_brief", project_slug, query),
            self._vector_rank("document", project_slug, query),
        )
        excerpts: list[Excerpt] = []
        budget = token_budget * _CHARS_PER_TOKEN
        for (kind, ref_id), score in ranked:
            ex = self._materialize(kind, ref_id)
            if ex is None:
                continue
            ex.score = round(score, 5)
            excerpts.append(ex)
            budget -= len(ex.text)
            if len(excerpts) >= k or budget <= 0:
                break
        return excerpts

    def recent_brief_summaries(self, project_slug: str, limit: int = 3) -> list[str]:
        with connection() as conn:
            rows = conn.execute(
                """SELECT content_json FROM research_brief
                   WHERE project_slug = ? AND superseded_by IS NULL
                   ORDER BY created_at DESC LIMIT ?""",
                (project_slug, limit),
            ).fetchall()
        out = []
        for r in rows:
            b = ResearchBrief.model_validate_json(r["content_json"])
            out.append(f"{b.topic}: {b.summary}" if b.summary else b.topic)
        return out

    # -- internals -----------------------------------------------------------------

    def _embed(self, text: str) -> Optional[bytes]:
        if self.embedder is None or not text.strip():
            return None
        try:
            return _pack(self.embedder.embed([text]).vectors[0])
        except Exception:  # embedding is best-effort; never break a run over it
            return None

    def _fts_rank(self, table: str, project_slug: str, query: str) -> list[tuple[tuple[str, str], int]]:
        kind = "brief" if table == "brief_fts" else "document"
        with connection() as conn:
            try:
                rows = conn.execute(
                    f"""SELECT ref_id FROM {table}
                        WHERE project_slug = ? AND {table} MATCH ?
                        ORDER BY bm25({table}) LIMIT 20""",
                    (project_slug, _match_query(query)),
                ).fetchall()
            except Exception:
                return []
        return [((kind, r["ref_id"]), i) for i, r in enumerate(rows)]

    def _vector_rank(self, table: str, project_slug: str, query: str) -> list[tuple[tuple[str, str], int]]:
        if self.embedder is None:
            return []
        try:
            qvec = self.embedder.embed([query]).vectors[0]
        except Exception:
            return []
        kind = "brief" if table == "research_brief" else "document"
        with connection() as conn:
            rows = conn.execute(
                f"SELECT id, embedding FROM {table} WHERE project_slug = ? AND embedding IS NOT NULL",
                (project_slug,),
            ).fetchall()
        scored = sorted(
            ((r["id"], _cosine(qvec, _unpack(r["embedding"]))) for r in rows),
            key=lambda t: t[1],
            reverse=True,
        )
        return [((kind, rid), i) for i, (rid, _) in enumerate(scored[:20])]

    @staticmethod
    def _fuse(*ranked_lists) -> list[tuple[tuple[str, str], float]]:
        scores: dict[tuple[str, str], float] = {}
        for ranked in ranked_lists:
            for key, rank in ranked:
                scores[key] = scores.get(key, 0.0) + 1.0 / (_RRF_K + rank)
        return sorted(scores.items(), key=lambda t: t[1], reverse=True)

    def _materialize(self, kind: str, ref_id: str) -> Optional[Excerpt]:
        if kind == "brief":
            with connection() as conn:
                row = conn.execute(
                    "SELECT topic, content_json, created_at FROM research_brief WHERE id = ?", (ref_id,)
                ).fetchone()
            if not row:
                return None
            brief = ResearchBrief.model_validate_json(row["content_json"])
            return Excerpt("brief", ref_id, row["topic"], brief_text(brief)[:600], row["created_at"])
        with connection() as conn:
            row = conn.execute(
                "SELECT type, title, content_json, created_at FROM document WHERE id = ?", (ref_id,)
            ).fetchone()
        if not row:
            return None
        model = BlogContent if row["type"] == "blog_post" else BlogContent
        try:
            text = document_text(model.model_validate_json(row["content_json"]))
        except Exception:
            text = row["content_json"]
        return Excerpt("document", ref_id, row["title"], text[:600], row["created_at"])


def format_priming(subject_focus: str, recent_summaries: Sequence[str], excerpts: Sequence[Excerpt]) -> str:
    """Assemble the 'what this project already knows' block for the research pipeline."""
    lines: list[str] = []
    if subject_focus:
        lines.append(f"Project focus: {subject_focus}")
    if recent_summaries:
        lines.append("Recent briefs on this beat:")
        lines += [f"- {s}" for s in recent_summaries]
    if excerpts:
        lines.append("Related prior findings:")
        lines += [f"- ({e.kind}) {e.title}: {e.text.splitlines()[0][:200]}" for e in excerpts]
    return "\n".join(lines)
