"""Orchestration: research resolution -> compose -> render -> write, with SQLite persistence.

The brief cache, run bookkeeping, document store and cost ledger all live in the database
(``contentforge.db``), so run history and briefs survive a restart and a document can be
re-rendered from its stored JSON without any LLM or search call.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

from pydantic import BaseModel

from .agents.base import AgentBudget
from .agents.library import FACT_CHECKER_AGENT, METADATA_AGENT
from .agent_loop import run_agent
from .corpus import CorpusSelection, resolve_corpus
from .cost import CostLedger
from .db import briefs as brief_store
from .db import costs as cost_store
from .db import documents as doc_store
from .db import runs as run_store
from .db import sources as source_store
from .knowledge import KnowledgeStore, brief_text, format_priming
from .pipelines import COMPOSE_PIPELINES
from .pipelines.base import Document
from .pipelines.compilation import CompilationPipeline
from .pipelines.research import ResearchPipeline
from .providers.base import LLMProvider, SearchBudget, SearchProvider
from .providers.serper import normalize_query
from .renderers import DEFAULT_RENDERERS
from .schemas import DocumentMetadata, FactCheckReport, ResearchBrief

DEFAULT_SEARCH_BUDGET = 12
BRIEF_TTL_DAYS = 7


def _with_model(agent, model: Optional[str]):
    from dataclasses import replace

    return replace(agent, model=model) if model else agent


@dataclass
class RunResult:
    brief: ResearchBrief
    documents: list[tuple[Document, Path]] = field(default_factory=list)
    cost: CostLedger = field(default_factory=CostLedger)
    reused_brief: bool = False
    run_id: Optional[str] = None
    document_ids: list[str] = field(default_factory=list)

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
        knowledge: Optional[KnowledgeStore] = None,
        search_budget_per_run: int = DEFAULT_SEARCH_BUDGET,
        brief_ttl_days: Optional[int] = BRIEF_TTL_DAYS,
    ) -> None:
        self.llm = llm
        self.search_provider = search_provider
        self.output_dir = Path(output_dir)
        self.renderers = dict(renderers or DEFAULT_RENDERERS)
        self.knowledge = knowledge or KnowledgeStore()
        self.search_budget_per_run = search_budget_per_run
        self.brief_ttl_days = brief_ttl_days

    # -- public ----------------------------------------------------------------

    def run_atomic(
        self,
        project: Any,
        topic: str,
        *,
        artifacts: Iterable[str] = ("blog_post",),
        topic_slug: Optional[str] = None,
        current_date: Optional[str] = None,
        force_fresh: bool = False,
        run_id: Optional[str] = None,
    ) -> RunResult:
        artifacts = list(artifacts)
        current_date = current_date or date.today().isoformat()
        slug = getattr(project, "slug", "")
        ledger = CostLedger()

        if run_id is None:
            run_id = run_store.create_run(
                project_slug=slug, topic=topic, topic_slug=topic_slug or topic,
                params={"artifacts": artifacts, "force_fresh": force_fresh},
            ).id

        try:
            self._progress(run_id, 5, "running", "Resolving research...")
            brief, brief_id, reused = self._resolve_brief(
                project, topic, int(current_date[:4]), ledger, force_fresh, run_id
            )

            documents: list[tuple[Document, Path]] = []
            doc_ids: list[str] = []
            for i, artifact in enumerate(artifacts):
                self._progress(run_id, 45 + int(40 * i / len(artifacts)), "running",
                               f"Composing {artifact}...")
                pipeline = self._compose_pipeline(artifact, ledger)
                doc = pipeline.compose(brief, project, brief_id=brief_id)
                path = self._render_and_write(doc, project, current_date)
                doc_id = doc_store.save_document(
                    project_slug=slug, doc_type=doc.type, title=doc.title,
                    content_json=doc.content.model_dump_json(), run_id=run_id,
                    rendered_path=str(path), rendered_format=self.renderers[doc.type].mime,
                    based_on_brief_ids=doc.based_on_brief_ids,
                    review_status=doc.review_status, review_notes=doc.review_notes,
                )
                self.knowledge.index_document(doc_id, slug, doc.content)
                documents.append((doc, path))
                doc_ids.append(doc_id)

            self._progress(run_id, 92, "running", "Writing metadata...")
            self._compose_metadata(brief, project, run_id, slug, doc_ids, ledger)

            cost_store.save_ledger(run_id, ledger)
            totals = cost_store.run_totals(run_id)
            run_store.update_run(
                run_id, status="completed", progress=100, message="Done.",
                cost_usd=totals["usd"], search_calls=totals["search_calls"],
                tokens_in=totals["tokens_in"], tokens_out=totals["tokens_out"],
            )
            return RunResult(brief=brief, documents=documents, cost=ledger,
                             reused_brief=reused, run_id=run_id, document_ids=doc_ids)
        except Exception as exc:
            cost_store.save_ledger(run_id, ledger)
            run_store.update_run(run_id, status="failed", progress=0,
                                 message=f"Error: {exc}", error=str(exc))
            raise

    def start_compilation(
        self,
        project: Any,
        longform_type: str,
        selection: CorpusSelection,
        *,
        angle: str = "",
        current_date: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> RunResult:
        current_date = current_date or date.today().isoformat()
        slug = getattr(project, "slug", "")
        ledger = CostLedger()
        if run_id is None:
            run_id = run_store.create_run(
                project_slug=slug, kind="compilation",
                topic=f"{longform_type}: {angle or 'compilation'}",
                params={"longform_type": longform_type, "selection": selection.model_dump(), "angle": angle},
            ).id
        try:
            self._progress(run_id, 10, "running", "Gathering corpus...")
            corpus = resolve_corpus(slug, selection, angle=angle, knowledge=self.knowledge)
            if not corpus.items:
                raise ValueError("no prior content matched the selection")

            self._progress(run_id, 40, "running", f"Composing {longform_type}...")
            doc = CompilationPipeline(self.llm, ledger=ledger).compose(
                longform_type=longform_type, corpus=corpus, project=project, angle=angle,
                model=getattr(project, "default_model", None),
            )
            path = self._render_and_write(doc, project, current_date)
            doc_id = doc_store.save_document(
                project_slug=slug, doc_type=doc.type, title=doc.title,
                content_json=doc.content.model_dump_json(), run_id=run_id,
                rendered_path=str(path), rendered_format=self.renderers[doc.type].mime,
                based_on_brief_ids=doc.based_on_brief_ids,
                based_on_document_ids=doc.based_on_document_ids,
                review_status=doc.review_status, review_notes=doc.review_notes,
            )
            self.knowledge.index_document(doc_id, slug, doc.content)

            cost_store.save_ledger(run_id, ledger)
            totals = cost_store.run_totals(run_id)
            run_store.update_run(
                run_id, status="completed", progress=100, message="Done.",
                cost_usd=totals["usd"], search_calls=totals["search_calls"],
                tokens_in=totals["tokens_in"], tokens_out=totals["tokens_out"],
            )
            return RunResult(
                brief=corpus.merged_brief(doc.title), documents=[(doc, path)], cost=ledger,
                run_id=run_id, document_ids=[doc_id],
            )
        except Exception as exc:
            cost_store.save_ledger(run_id, ledger)
            run_store.update_run(run_id, status="failed", progress=0,
                                 message=f"Error: {exc}", error=str(exc))
            raise

    def render_document(self, document_id: str, *, project: Any | None = None) -> Path:
        """Re-render a stored document to disk. No LLM, no search."""
        stored = doc_store.get_document(document_id)
        if stored is None:
            raise KeyError(document_id)
        content = self._content_model(stored.type).model_validate_json(stored.content_json)
        project = project or self._project_for(stored.project_slug)
        path = self._render_and_write(
            Document(type=stored.type, content=content, title=stored.title),
            project,
            stored.created_at[:10],
        )
        doc_store.set_rendered_path(document_id, str(path), "markdown")
        return path

    # -- internals -----------------------------------------------------------------

    def _resolve_brief(self, project, topic, year, ledger, force_fresh, run_id):
        slug = getattr(project, "slug", "")
        normalized = normalize_query(topic)
        if not force_fresh:
            hit = brief_store.find_fresh_brief(slug, normalized)
            if hit is not None:
                return hit.brief, hit.id, True

        self._apply_strategy(project)
        priming = format_priming(
            getattr(project, "subject_focus", "") or "",
            self.knowledge.recent_brief_summaries(slug) if slug else [],
            self.knowledge.retrieve(slug, topic) if slug else [],
        )

        brief = ResearchPipeline(self.llm, self.search_provider, ledger=ledger).run(
            topic,
            audience=getattr(project, "audience", ""),
            current_year=year,
            subject_focus=getattr(project, "subject_focus", "") or "",
            recency_days=getattr(project, "recency_days", None),
            min_sources=getattr(project, "min_sources", 5) or 5,
            priming=priming,
            model=getattr(project, "default_model", None),
            max_searches=self.search_budget_per_run,
        )

        self._record_search_cost(ledger)
        self._factcheck_brief(brief, ledger, getattr(project, "default_model", None))
        brief_id = self._persist_brief(brief, slug, normalized, run_id)
        return brief, brief_id, False

    def _factcheck_brief(self, brief: ResearchBrief, ledger: CostLedger, model: Optional[str]) -> None:
        """Check each finding against the brief's own sources; annotate credibility, drop
        findings with no support.
        """
        agent = _with_model(FACT_CHECKER_AGENT, model)
        try:
            report: FactCheckReport = run_agent(
                self.llm, agent,
                "Text to check:\n" + brief_text(brief)
                + "\n\nResearch it must be faithful to (JSON):\n" + brief.model_dump_json(indent=2),
                budget=AgentBudget(max_iterations=2, max_tool_calls=0), ledger=ledger,
            )  # type: ignore[assignment]
        except Exception:
            return
        unsupported = {c.strip().lower() for c in report.unsupported_claims}
        brief.key_findings = [f for f in brief.key_findings if f.strip().lower() not in unsupported]
        supported_urls = {v.evidence_url for v in report.verdicts if v.verdict == "supported" and v.evidence_url}
        for source in brief.sources:
            if source.url in supported_urls:
                source.credibility = "supported"

    def _apply_strategy(self, project) -> None:
        if hasattr(self.search_provider, "budget"):
            self.search_provider.budget = SearchBudget(max_calls=self.search_budget_per_run)
        prefer = {d.lower().removeprefix("www.") for d in getattr(project, "prefer_domains", []) or []}
        exclude = {d.lower().removeprefix("www.") for d in getattr(project, "exclude_domains", []) or []}
        if hasattr(self.search_provider, "prefer_domains"):
            self.search_provider.prefer_domains = prefer
        if hasattr(self.search_provider, "exclude_domains"):
            self.search_provider.exclude_domains = exclude

    def _record_search_cost(self, ledger: CostLedger) -> None:
        budget = getattr(self.search_provider, "budget", None)
        if budget is not None and budget.calls_made:
            ledger.record_search("serper", calls=budget.calls_made)

    def _persist_brief(self, brief: ResearchBrief, slug: str, normalized: str, run_id: Optional[str],
                       supersedes: Optional[str] = None) -> str:
        brief_id = brief_store.save_brief(
            brief, project_slug=slug, normalized_topic=normalized, run_id=run_id,
            ttl_days=self.brief_ttl_days,
        )
        if supersedes:
            brief_store.supersede(supersedes, brief_id)
        source_store.save_sources(brief_id, slug, brief.sources)
        self.knowledge.index_brief(brief_id, slug, brief)
        return brief_id

    def update_brief(self, project: Any, brief_id: str, *, current_date: Optional[str] = None) -> ResearchBrief:
        """Re-research an existing brief; the new one supersedes it."""
        current_date = current_date or date.today().isoformat()
        slug = getattr(project, "slug", "")
        stored = brief_store.get_brief(brief_id)
        if stored is None:
            raise KeyError(brief_id)

        run_id = run_store.create_run(
            project_slug=slug, topic=stored.brief.topic, kind="research",
            params={"updates_brief": brief_id},
        ).id
        ledger = CostLedger()
        try:
            self._apply_strategy(project)
            updated = ResearchPipeline(self.llm, self.search_provider, ledger=ledger).update_brief(
                stored.brief,
                audience=getattr(project, "audience", ""),
                current_year=int(current_date[:4]),
                recency_days=getattr(project, "recency_days", None),
            )
            self._record_search_cost(ledger)
            self._persist_brief(
                updated, slug, normalize_query(stored.brief.topic), run_id, supersedes=brief_id
            )
            cost_store.save_ledger(run_id, ledger)
            totals = cost_store.run_totals(run_id)
            run_store.update_run(run_id, status="completed", progress=100, message="Brief updated.",
                                 cost_usd=totals["usd"], search_calls=totals["search_calls"],
                                 tokens_in=totals["tokens_in"], tokens_out=totals["tokens_out"])
            return updated
        except Exception as exc:
            cost_store.save_ledger(run_id, ledger)
            run_store.update_run(run_id, status="failed", progress=0, message=f"Error: {exc}", error=str(exc))
            raise

    def _compose_pipeline(self, artifact: str, ledger: CostLedger):
        cls = COMPOSE_PIPELINES.get(artifact)
        if cls is None:
            raise ValueError(f"unknown artifact type: {artifact!r}")
        return cls(self.llm, ledger=ledger)

    def _compose_metadata(self, brief, project, run_id, slug, doc_ids, ledger) -> Optional[str]:
        prior = self.knowledge.retrieve(slug, brief.topic, k=5) if slug else []
        prior_titles = "\n".join(f"- {e.title}" for e in prior if e.kind == "document") or "(none)"
        try:
            meta: DocumentMetadata = run_agent(
                self.llm, _with_model(METADATA_AGENT, getattr(project, "default_model", None)),
                "Research brief (JSON):\n" + brief.model_dump_json(indent=2)
                + f"\n\nThis project's prior pieces:\n{prior_titles}",
                variables={"topic": brief.topic, "audience": getattr(project, "audience", "")},
                budget=AgentBudget(max_iterations=2, max_tool_calls=0), ledger=ledger,
            )  # type: ignore[assignment]
        except Exception:
            return None
        return doc_store.save_document(
            project_slug=slug, doc_type="metadata", title=f"metadata: {brief.topic}",
            content_json=meta.model_dump_json(), run_id=run_id,
            based_on_document_ids=doc_ids,
        )

    _CONTENT_MODELS = {
        "blog_post": "BlogContent",
        "linkedin_post": "LinkedInPost",
        "social_thread": "SocialThread",
        "repurpose": "RepurposePack",
        "newsletter": "Newsletter",
        "podcast_script": "PodcastScript",
        "guide": "Guide",
        "metadata": "DocumentMetadata",
    }

    def _content_model(self, doc_type: str) -> type[BaseModel]:
        from . import schemas

        return getattr(schemas, self._CONTENT_MODELS.get(doc_type, "BlogContent"))

    def _project_for(self, slug: Optional[str]):
        from .projects import ProjectNotFoundError, get_project

        try:
            return get_project(slug) if slug else None
        except ProjectNotFoundError:
            return None

    def _render_and_write(self, doc: Document, project: Any, current_date: str) -> Path:
        renderer = self.renderers.get(doc.type)
        if renderer is None:
            raise ValueError(f"no renderer registered for document type {doc.type!r}")
        result = renderer.render(
            doc.content,
            context={
                "author": getattr(project, "author", ""),
                "category_tags": list(getattr(project, "category_tags", []) or []),
                "current_date": current_date,
            },
        )
        artifacts = result if isinstance(result, list) else [result]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        primary: Optional[Path] = None
        for artifact in artifacts:
            path = self.output_dir / artifact.filename
            path.write_bytes(artifact.content)
            primary = primary or path
        return primary  # type: ignore[return-value]

    def _progress(self, run_id: Optional[str], pct: int, status: str, message: str) -> None:
        if run_id:
            run_store.update_run(run_id, progress=pct, status=status, message=message)


def default_run_service(output_dir: Path | str, **overrides: Any) -> RunService:
    """Build a RunService from environment config, overridable for tests."""

    llm = overrides.pop("llm", None)
    search_provider = overrides.pop("search_provider", None)
    knowledge = overrides.pop("knowledge", None)
    if llm is None:
        from .providers.openai_provider import OpenAIProvider

        llm = OpenAIProvider()
    if search_provider is None:
        from .db.search_cache import SqliteSearchCache
        from .providers.serper import SerperSearchProvider

        search_provider = SerperSearchProvider(
            os.environ.get("SERPER_API_KEY", ""),
            cache=SqliteSearchCache(),
            budget=SearchBudget(max_calls=DEFAULT_SEARCH_BUDGET),
        )
    if knowledge is None:
        from .providers.openai_provider import OpenAIEmbeddingProvider

        knowledge = KnowledgeStore(embedder=OpenAIEmbeddingProvider())
    return RunService(
        llm=llm, search_provider=search_provider, output_dir=output_dir, knowledge=knowledge, **overrides
    )
