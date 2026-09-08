"""Resolving a corpus for a compilation run: pick prior runs / briefs / documents, plus
optional retrieval hits, into a token-budgeted bundle the long-form pipeline can work from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from .db import briefs as brief_store
from .db import documents as doc_store
from .db import runs as run_store
from .knowledge import KnowledgeStore, brief_text, document_text
from .schemas import BlogContent, ResearchBrief, Source

_CHARS_PER_TOKEN = 4


class CorpusSelection(BaseModel):
    run_ids: List[str] = Field(default_factory=list)
    last_n_runs: Optional[int] = None
    last_n_days: Optional[int] = None
    include_retrieval: bool = True


@dataclass
class CorpusItem:
    kind: str  # "brief" | "document"
    id: str
    title: str
    text: str
    sources: List[str] = field(default_factory=list)


@dataclass
class Corpus:
    items: List[CorpusItem]
    brief_ids: List[str]
    document_ids: List[str]

    def as_prompt(self, token_budget: int = 6000) -> str:
        budget = token_budget * _CHARS_PER_TOKEN
        blocks: List[str] = []
        for item in self.items:
            block = f"### {item.title} ({item.kind})\n{item.text}"
            budget -= len(block)
            if budget <= 0 and blocks:
                blocks.append("(older corpus items omitted for length)")
                break
            blocks.append(block)
        return "\n\n".join(blocks)

    def merged_brief(self, topic: str) -> ResearchBrief:
        """A synthetic brief spanning the corpus, for the review chain to check claims against."""
        findings, trends, impact, sources, seen = [], [], [], [], set()
        for item in self.items:
            for url in item.sources:
                if url not in seen:
                    seen.add(url)
                    sources.append(Source(url=url, takeaway=f"cited in '{item.title}'"))
        for bid in self.brief_ids:
            stored = brief_store.get_brief(bid)
            if stored:
                findings += stored.brief.key_findings
                trends += stored.brief.trends
                impact += stored.brief.audience_impact
        return ResearchBrief(
            topic=topic, summary=f"Synthesised from {len(self.items)} prior project pieces.",
            key_findings=findings, trends=trends, audience_impact=impact, sources=sources,
        )


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")


def resolve_corpus(
    project_slug: str,
    selection: CorpusSelection,
    *,
    angle: str = "",
    knowledge: Optional[KnowledgeStore] = None,
) -> Corpus:
    run_ids = list(selection.run_ids)
    if not run_ids and (selection.last_n_runs or selection.last_n_days):
        since = _iso_days_ago(selection.last_n_days) if selection.last_n_days else None
        runs = run_store.list_runs(
            project_slug=project_slug, limit=selection.last_n_runs or 50,
            since=since, status="completed", kinds=("atomic", "research"),
        )
        run_ids = [r.id for r in runs]

    items: List[CorpusItem] = []
    brief_ids: List[str] = []
    document_ids: List[str] = []

    for stored in brief_store.list_briefs(project_slug=project_slug, run_ids=run_ids or None):
        brief_ids.append(stored.id)
        items.append(CorpusItem(
            "brief", stored.id, stored.brief.topic, brief_text(stored.brief),
            sources=[s.url for s in stored.brief.sources if s.url],
        ))

    for doc in doc_store.list_documents(project_slug=project_slug, run_ids=run_ids or None):
        if doc.type == "metadata":
            continue
        document_ids.append(doc.id)
        try:
            content = BlogContent.model_validate_json(doc.content_json)
            text, urls = document_text(content), content.sources
        except Exception:
            text, urls = doc.content_json, []
        items.append(CorpusItem("document", doc.id, doc.title, text, sources=urls))

    if selection.include_retrieval and knowledge is not None and (angle or run_ids):
        seen = {i.id for i in items}
        for ex in knowledge.retrieve(project_slug, angle or "overview", k=4):
            if ex.ref_id not in seen:
                items.append(CorpusItem(ex.kind, ex.ref_id, ex.title, ex.text))

    return Corpus(items=items, brief_ids=brief_ids, document_ids=document_ids)
