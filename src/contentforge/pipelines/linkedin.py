"""LinkedIn compose pipeline: a sibling recipe off the brief (or a repurpose of a `source`
Document), writer + the full review chain.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from ..agents.base import AgentBudget
from ..agents.library import LINKEDIN_WRITER_AGENT
from ..agent_loop import run_agent
from ..cost import CostLedger
from ..providers.base import LLMProvider
from ..schemas import LinkedInPost, ResearchBrief
from .base import Document
from .review import full_review

_WRITE_BUDGET = AgentBudget(max_iterations=2, max_tool_calls=0)


class LinkedInPipeline:
    document_type = "linkedin_post"
    default_target_words = 180

    def __init__(self, llm: LLMProvider, *, ledger: CostLedger | None = None,
                 writer_agent=LINKEDIN_WRITER_AGENT) -> None:
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
        model = getattr(project, "default_model", None)
        writer = replace(self.writer_agent, model=model) if model else self.writer_agent
        variables = {
            "topic": brief.topic,
            "audience": getattr(project, "audience", ""),
            "tone": getattr(project, "tone", "clear and direct"),
            "style_guide": getattr(project, "style_guide", "") or "(none)",
        }
        task = "Research brief (JSON):\n" + brief.model_dump_json(indent=2)
        if source is not None:
            task += (
                "\n\nExisting piece to point at / reshape (JSON):\n"
                + source.content.model_dump_json(indent=2)
            )

        draft: LinkedInPost = run_agent(
            self.llm, writer, task, variables=variables, budget=_WRITE_BUDGET, ledger=self.ledger,
        )  # type: ignore[assignment]

        review = full_review(
            self.llm, self.ledger, draft=draft, schema=LinkedInPost, brief=brief,
            project=project, doc_type=self.document_type, model=model,
        )
        final: LinkedInPost = review.content  # type: ignore[assignment]
        title = (final.hook.splitlines()[0][:80] if final.hook else "LinkedIn post")
        return Document(
            type=self.document_type,
            content=final,
            title=title,
            based_on_brief_ids=[brief_id] if brief_id else [],
            based_on_document_ids=[source.title] if source else [],
            review_status=review.status,
            review_notes=review.notes,
        )
