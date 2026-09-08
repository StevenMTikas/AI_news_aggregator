"""Thread and repurpose compose pipelines: sibling recipes off the brief, writer + a light
(voice-only) review.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from ..agents.base import AgentBudget
from ..agents.library import REPURPOSE_AGENT, SOCIAL_THREAD_AGENT
from ..agent_loop import run_agent
from ..cost import CostLedger
from ..providers.base import LLMProvider
from ..schemas import RepurposePack, ResearchBrief, SocialThread
from .base import Document
from .review import light_review

_WRITE_BUDGET = AgentBudget(max_iterations=2, max_tool_calls=0)


def _vars(brief: ResearchBrief, project: Any) -> dict:
    return {
        "topic": brief.topic,
        "audience": getattr(project, "audience", ""),
        "style_guide": getattr(project, "style_guide", "") or "(none)",
    }


class _SiblingPipeline:
    document_type = ""
    default_target_words = None
    schema: type = object
    writer: Any = None

    def __init__(self, llm: LLMProvider, *, ledger: CostLedger | None = None) -> None:
        self.llm = llm
        self.ledger = ledger

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
        model = getattr(project, "default_model", None)
        writer = replace(self.writer, model=model) if model else self.writer
        draft = run_agent(
            self.llm, writer, "Research brief (JSON):\n" + brief.model_dump_json(indent=2),
            variables=_vars(brief, project), budget=_WRITE_BUDGET, ledger=self.ledger,
        )
        review = light_review(
            self.llm, self.ledger, draft=draft, schema=self.schema, doc_type=self.document_type,
            model=model,
        )
        return Document(
            type=self.document_type,
            content=review.content,
            title=self._title(review.content),
            based_on_brief_ids=[brief_id] if brief_id else [],
            review_status=review.status,
            review_notes=review.notes,
        )

    def _title(self, content: Any) -> str:  # pragma: no cover - overridden
        return self.document_type


class SocialThreadPipeline(_SiblingPipeline):
    document_type = "social_thread"
    schema = SocialThread
    writer = SOCIAL_THREAD_AGENT

    def _title(self, content: SocialThread) -> str:
        return (content.posts[0][:80] if content.posts else "Thread")


class RepurposePipeline(_SiblingPipeline):
    document_type = "repurpose"
    schema = RepurposePack
    writer = REPURPOSE_AGENT

    def _title(self, content: RepurposePack) -> str:
        return f"{len(content.snippets)} repurposed snippet(s)"
