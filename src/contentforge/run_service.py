"""Orchestration: research resolution -> compose -> render -> write.

In-memory for Phase 4 (brief cache is a dict, run state is the return value). Phase 5 swaps
the cache and run bookkeeping for SQLite without changing this surface.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from pydantic import BaseModel

from .cost import CostLedger
from .pipelines.base import Document
from .pipelines.blog_post import BlogPostPipeline
from .pipelines.research import ResearchPipeline
from .providers.base import LLMProvider, SearchBudget, SearchProvider
from .providers.serper import normalize_query
from .renderers.jekyll import JekyllMarkdownRenderer
from .schemas import ResearchBrief

DEFAULT_SEARCH_BUDGET = 12


@dataclass
class RunResult:
    brief: ResearchBrief
    documents: list[tuple[Document, Path]] = field(default_factory=list)
    cost: CostLedger = field(default_factory=CostLedger)
    reused_brief: bool = False

    @property
    def content(self) -> Optional[BaseModel]:
        return self.documents[0][0].content if self.documents else None

    # back-compat with the old crew-result seam used by app.py / cli.py
    @property
    def pydantic(self) -> Optional[BaseModel]:
        return self.content

    @property
    def primary_path(self) -> Optional[Path]:
        return self.documents[0][1] if self.documents else None


class RunService:
    def __init__(
        self,
        *,
        llm: LLMProvider,
        search_provider: SearchProvider,
        output_dir: Path | str,
        renderers: Mapping[str, Any] | None = None,
        search_budget_per_run: int = DEFAULT_SEARCH_BUDGET,
        brief_cache: dict | None = None,
    ) -> None:
        self.llm = llm
        self.search_provider = search_provider
        self.output_dir = Path(output_dir)
        self.renderers = dict(renderers or {"blog_post": JekyllMarkdownRenderer()})
        self.search_budget_per_run = search_budget_per_run
        self._briefs: dict[tuple[str, str], ResearchBrief] = (
            brief_cache if brief_cache is not None else {}
        )

    # -- public ----------------------------------------------------------------

    def run_atomic(
        self,
        project: Any,
        topic: str,
        *,
        artifacts: Iterable[str] = ("blog_post",),
        current_date: Optional[str] = None,
        force_fresh: bool = False,
    ) -> RunResult:
        current_date = current_date or date.today().isoformat()
        ledger = CostLedger()

        brief, reused = self._resolve_brief(project, topic, int(current_date[:4]), ledger, force_fresh)

        documents: list[tuple[Document, Path]] = []
        for artifact in artifacts:
            pipeline = self._compose_pipeline(artifact, ledger)
            doc = pipeline.compose(brief, project)
            documents.append((doc, self._render_and_write(doc, project, current_date)))

        return RunResult(brief=brief, documents=documents, cost=ledger, reused_brief=reused)

    # -- internals -----------------------------------------------------------------

    def _resolve_brief(
        self, project: Any, topic: str, year: int, ledger: CostLedger, force_fresh: bool
    ) -> tuple[ResearchBrief, bool]:
        key = (getattr(project, "slug", ""), normalize_query(topic))
        if not force_fresh and key in self._briefs:
            return self._briefs[key], True

        if hasattr(self.search_provider, "budget"):
            self.search_provider.budget = SearchBudget(max_calls=self.search_budget_per_run)

        brief = ResearchPipeline(self.llm, self.search_provider, ledger=ledger).run(
            topic,
            audience=getattr(project, "audience", ""),
            current_year=year,
            subject_focus=getattr(project, "subject_focus", "") or "",
            recency_days=getattr(project, "recency_days", None),
            min_sources=getattr(project, "min_sources", 5) or 5,
            max_searches=self.search_budget_per_run,
        )

        budget = getattr(self.search_provider, "budget", None)
        if budget is not None and budget.calls_made:
            ledger.record_search("serper", calls=budget.calls_made)

        self._briefs[key] = brief
        return brief, False

    def _compose_pipeline(self, artifact: str, ledger: CostLedger):
        if artifact == "blog_post":
            return BlogPostPipeline(self.llm, ledger=ledger)
        raise ValueError(f"unknown artifact type: {artifact!r}")

    def _render_and_write(self, doc: Document, project: Any, current_date: str) -> Path:
        renderer = self.renderers.get(doc.type)
        if renderer is None:
            raise ValueError(f"no renderer registered for document type {doc.type!r}")
        artifact = renderer.render(
            doc.content,
            context={
                "author": getattr(project, "author", ""),
                "category_tags": list(getattr(project, "category_tags", [])),
                "current_date": current_date,
            },
        )
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / artifact.filename
        path.write_bytes(artifact.content)
        return path


def default_run_service(output_dir: Path | str, **overrides: Any) -> RunService:
    """Build a RunService from environment config, overridable for tests."""

    llm = overrides.pop("llm", None)
    search_provider = overrides.pop("search_provider", None)
    if llm is None:
        from .providers.openai_provider import OpenAIProvider

        llm = OpenAIProvider()
    if search_provider is None:
        from .providers.serper import InMemorySearchCache, SerperSearchProvider

        search_provider = SerperSearchProvider(
            os.environ.get("SERPER_API_KEY", ""),
            cache=InMemorySearchCache(),
            budget=SearchBudget(max_calls=DEFAULT_SEARCH_BUDGET),
        )
    return RunService(llm=llm, search_provider=search_provider, output_dir=output_dir, **overrides)
