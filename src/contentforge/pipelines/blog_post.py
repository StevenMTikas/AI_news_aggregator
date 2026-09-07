"""Blog-post compose pipeline: ResearchBrief -> BlogContent, via writer -> editor."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping, Optional

from ..agents.base import AgentBudget
from ..agents.library import BLOG_WRITER_AGENT, EDITOR_AGENT
from ..agent_loop import run_agent
from ..cost import CostLedger
from ..providers.base import LLMProvider
from ..schemas import BlogContent, ResearchBrief
from .base import Document, resolve_target_words


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


def _writer_task(brief: ResearchBrief) -> str:
    return "Research brief (JSON):\n" + brief.model_dump_json(indent=2)


def _editor_task(draft: BlogContent, brief: ResearchBrief, target_words: Optional[int]) -> str:
    return (
        f"Target length: ~{target_words or 800} words.\n\n"
        "Draft (JSON):\n" + draft.model_dump_json(indent=2) + "\n\n"
        "Research brief it must stay faithful to (JSON):\n" + brief.model_dump_json(indent=2)
    )


class BlogPostPipeline:
    document_type = "blog_post"
    default_target_words = 800

    def __init__(
        self,
        llm: LLMProvider,
        *,
        ledger: CostLedger | None = None,
        writer_agent=BLOG_WRITER_AGENT,
        editor_agent=EDITOR_AGENT,
    ) -> None:
        self.llm = llm
        self.ledger = ledger
        self.writer_agent = writer_agent
        self.editor_agent = editor_agent

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
        variables = _project_vars(project, brief, target_words)
        model = getattr(project, "default_model", None)
        writer = replace(self.writer_agent, model=model) if model else self.writer_agent
        editor = replace(self.editor_agent, model=model) if model else self.editor_agent

        draft: BlogContent = run_agent(
            self.llm,
            writer,
            _writer_task(brief),
            variables=variables,
            budget=AgentBudget(max_iterations=2, max_tool_calls=0),
            ledger=self.ledger,
        )  # type: ignore[assignment]

        final: BlogContent = run_agent(
            self.llm,
            editor,
            _editor_task(draft, brief, target_words),
            variables=variables,
            budget=AgentBudget(max_iterations=2, max_tool_calls=0),
            ledger=self.ledger,
        )  # type: ignore[assignment]

        return Document(
            type=self.document_type,
            content=final,
            title=final.title,
            based_on_brief_ids=[brief_id] if brief_id else [],
        )
