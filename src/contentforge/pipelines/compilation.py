"""Tier 2: assemble a long-form piece (newsletter / podcast script / guide) from a corpus of
the project's prior work -- outline -> write -> full review chain. No new research.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Optional

from ..agents.base import AgentBudget
from ..agents.library import OUTLINE_AGENT, longform_writer_for
from ..agent_loop import run_agent
from ..corpus import Corpus
from ..cost import CostLedger
from ..providers.base import LLMProvider
from ..schemas import LONGFORM_SCHEMAS, Guide, Newsletter, Outline, PodcastScript
from .base import Document
from .review import full_review

_BUDGET = AgentBudget(max_iterations=2, max_tool_calls=0)


def _title_of(content: Any) -> str:
    if isinstance(content, Newsletter):
        return content.subject
    if isinstance(content, (PodcastScript, Guide)):
        return content.title
    return "Long-form piece"


class CompilationPipeline:
    def __init__(self, llm: LLMProvider, *, ledger: Optional[CostLedger] = None) -> None:
        self.llm = llm
        self.ledger = ledger

    def compose(
        self,
        *,
        longform_type: str,
        corpus: Corpus,
        project: Any,
        angle: str = "",
        model: Optional[str] = None,
    ) -> Document:
        if longform_type not in LONGFORM_SCHEMAS:
            raise ValueError(f"unknown long-form type: {longform_type!r}")
        schema = LONGFORM_SCHEMAS[longform_type]
        corpus_block = corpus.as_prompt()

        outline_agent = replace(OUTLINE_AGENT, model=model) if model else OUTLINE_AGENT
        outline: Outline = run_agent(
            self.llm, outline_agent,
            "Corpus:\n" + corpus_block,
            variables={
                "longform_type": longform_type.replace("_", " "),
                "audience": getattr(project, "audience", ""),
                "angle": angle or "(no specific angle -- find the throughline)",
            },
            budget=_BUDGET, ledger=self.ledger,
        )  # type: ignore[assignment]

        writer = longform_writer_for(longform_type)
        if model:
            writer = replace(writer, model=model)
        draft = run_agent(
            self.llm, writer,
            "Outline (JSON):\n" + outline.model_dump_json(indent=2) + "\n\nCorpus:\n" + corpus_block,
            variables={
                "audience": getattr(project, "audience", ""),
                "style_guide": getattr(project, "style_guide", "") or "(none)",
            },
            budget=_BUDGET, ledger=self.ledger,
        )

        review = full_review(
            self.llm, self.ledger, draft=draft, schema=schema,
            brief=corpus.merged_brief(outline.title), project=project,
            doc_type=longform_type, model=model,
        )
        return Document(
            type=longform_type,
            content=review.content,
            title=_title_of(review.content),
            based_on_brief_ids=corpus.brief_ids,
            based_on_document_ids=corpus.document_ids,
            review_status=review.status,
            review_notes=review.notes,
        )
