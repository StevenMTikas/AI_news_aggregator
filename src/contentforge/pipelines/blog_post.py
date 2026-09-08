"""Blog-post compose pipeline: ResearchBrief -> BlogContent, via writer + the full review
chain (fact-check -> critique -> edit -> voice).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from ..agents.base import AgentBudget
from ..agents.library import BLOG_WRITER_AGENT
from ..agent_loop import run_agent
from ..cost import CostLedger
from ..providers.base import LLMProvider
from ..schemas import BlogContent, ResearchBrief
from .base import Document, resolve_target_words
from .review import full_review

_WRITE_BUDGET = AgentBudget(max_iterations=2, max_tool_calls=0)


def _project_vars(project: Any, brief: ResearchBrief, target_words: Optional[int]) -> dict:
    return {
        "project_name": getattr(project, "name", ""),
        "topic": brief.topic,
        "audience": getattr(project, "audience", ""),
        "tone": getattr(project, "tone", "clear and direct"),
        "author": getattr(project, "author", ""),
        "target_word_count": target_words or 800,
        "notes": getattr(project, "notes", "") or "(none)",
    }


class BlogPostPipeline:
    document_type = "blog_post"
    default_target_words = 800

    def __init__(self, llm: LLMProvider, *, ledger: CostLedger | None = None,
                 writer_agent=BLOG_WRITER_AGENT) -> None:
        self.llm = llm
        self.ledger = ledger
        self.writer_agent = writer_agent

    def compose(
        self,
        brief: ResearchBrief,
        project: Any,
        *,
        corpus: Any | None = None,
        source: Document | None = None,
        context: Mapping[str, Any] | None = None,
        brief_id: str | None = None,
    ) -> Document:
        target_words = resolve_target_words(self.default_target_words, project, self.document_type)
        model = getattr(project, "default_model", None)
        writer = replace(self.writer_agent, model=model) if model else self.writer_agent

        draft: BlogContent = run_agent(
            self.llm, writer, "Research brief (JSON):\n" + brief.model_dump_json(indent=2),
            variables=_project_vars(project, brief, target_words),
            budget=_WRITE_BUDGET, ledger=self.ledger,
        )  # type: ignore[assignment]

        review = full_review(
            self.llm, self.ledger, draft=draft, schema=BlogContent, brief=brief,
            project=project, doc_type=self.document_type, model=model,
        )
        final: BlogContent = review.content  # type: ignore[assignment]
        return Document(
            type=self.document_type,
            content=final,
            title=final.title,
            based_on_brief_ids=[brief_id] if brief_id else [],
            review_status=review.status,
            review_notes=review.notes,
        )
