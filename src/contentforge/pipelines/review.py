"""The shared review chain: fact-check -> critique -> edit -> voice, plus a non-LLM
consistency check that the voice pass did not drop facts or sources.

`full_review` is used by the blog and LinkedIn pipelines; `light_review` (voice only) by the
thread and repurpose pipelines.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Type

from pydantic import BaseModel

from ..agents.base import Agent, AgentBudget
from ..agents.library import AUDIENCE_CRITIC_AGENT, FACT_CHECKER_AGENT, editor_for, voice_for
from ..agent_loop import run_agent
from ..cost import CostLedger
from ..knowledge import document_text
from ..providers.base import LLMProvider
from ..schemas import (
    BlogContent,
    FactCheckReport,
    Guide,
    LinkedInPost,
    Newsletter,
    PodcastScript,
    RepurposePack,
    ResearchBrief,
    SocialThread,
)

_BUDGET = AgentBudget(max_iterations=2, max_tool_calls=0)
_URL = re.compile(r"https?://\S+")

_FORMAT_HINTS = {
    "blog_post": "Format: blog post. Keep the hook, 3-5 sections, and Key Takeaways.",
    "linkedin_post": (
        "Format: LinkedIn post. hook carries the whole thing; body is plain-text stanzas "
        "with NO markdown; 3-5 hashtags; keep link_placement 'first_comment'."
    ),
    "social_thread": "Format: thread. Each post stands alone and is <= 270 characters.",
    "repurpose": "Format: platform snippets. Each is one finished, self-contained idea.",
    "newsletter": "Format: newsletter. A specific subject line, a short intro, one item per topic, a sign-off.",
    "podcast_script": "Format: podcast script -- read aloud. Contractions, short sentences, bracketed cues, no prose stage directions.",
    "guide": "Format: practical guide. Introduction, substantive sections each with a key takeaway, an ordered checklist, sources.",
}


@dataclass
class ReviewResult:
    content: BaseModel
    notes: str
    status: str  # "reviewed" | "flagged"
    factcheck: Optional[FactCheckReport] = None


# --------------------------------------------------------------------- helpers


def content_text(content: BaseModel) -> str:
    if isinstance(content, BlogContent):
        return document_text(content)
    if isinstance(content, LinkedInPost):
        return "\n\n".join([content.hook, *content.body, content.cta])
    if isinstance(content, SocialThread):
        return "\n".join(content.posts)
    if isinstance(content, RepurposePack):
        return "\n".join(f"[{s.platform}] {s.text}" for s in content.snippets)
    if isinstance(content, Newsletter):
        return "\n\n".join([content.subject, content.intro,
                            *(f"{i.heading}\n{i.body}" for i in content.items), content.sign_off])
    if isinstance(content, PodcastScript):
        return "\n\n".join([content.title, content.hook,
                            *(f"{s.cue}\n{s.script}" for s in content.segments), content.outro])
    if isinstance(content, Guide):
        return "\n\n".join([content.title, content.introduction,
                            *(f"{s.heading}\n{s.body}\n{s.key_takeaway}" for s in content.sections),
                            *content.checklist])
    return content.model_dump_json()


def content_urls(content: BaseModel) -> set[str]:
    if isinstance(content, BlogContent):
        return set(content.sources)
    if isinstance(content, Guide):
        return set(content.sources)
    if isinstance(content, LinkedInPost):
        return {content.link_url} if content.link_url else set()
    if isinstance(content, Newsletter):
        return {i.source_url for i in content.items if i.source_url}
    return set(_URL.findall(content_text(content)))


def consistency_check(before: BaseModel, after: BaseModel) -> str:
    problems: list[str] = []
    lost = content_urls(before) - content_urls(after)
    if lost:
        problems.append(f"voice pass dropped {len(lost)} source URL(s)")
    wb, wa = len(content_text(before).split()), len(content_text(after).split())
    if wb and abs(wa - wb) / wb > 0.4:
        problems.append(f"voice pass changed length by {round(100 * (wa - wb) / wb)}%")
    return "; ".join(problems)


def _factcheck_task(text: str, brief: ResearchBrief) -> str:
    return (
        "Text to check:\n" + text + "\n\n"
        "Research it must be faithful to (JSON):\n" + brief.model_dump_json(indent=2)
    )


def _critic_task(text: str) -> str:
    return "Draft to react to:\n" + text


def _editor_task(draft: BaseModel, brief: ResearchBrief, fc: FactCheckReport, crit, doc_type: str) -> str:
    return (
        "Draft (JSON):\n" + draft.model_dump_json(indent=2) + "\n\n"
        "Research brief (JSON):\n" + brief.model_dump_json(indent=2) + "\n\n"
        "Fact-check report (JSON):\n" + fc.model_dump_json(indent=2) + "\n\n"
        "Reader critique (JSON):\n" + crit.model_dump_json(indent=2)
    )


def _voice_task(content: BaseModel) -> str:
    return "Text to rewrite (JSON):\n" + content.model_dump_json(indent=2)


def _editor_vars(project: Any, doc_type: str, schema: Type[BaseModel]) -> dict:
    banned = getattr(project, "banned_phrases", []) or []
    return {
        "project_name": getattr(project, "name", ""),
        "audience": getattr(project, "audience", ""),
        "tone": getattr(project, "tone", "clear and direct"),
        "style_guide": getattr(project, "style_guide", "") or "(none)",
        "banned_phrases": ", ".join(banned) or "(none)",
        "schema": schema.__name__,
        "format_hint": _FORMAT_HINTS.get(doc_type, ""),
    }


def _review_notes(fc: FactCheckReport, crit, consistency: str) -> str:
    bits = [f"fact-check: {fc.overall}"]
    if fc.unsupported_claims:
        bits.append(f"unsupported: {'; '.join(fc.unsupported_claims[:3])}")
    if crit.weak_spots:
        bits.append(f"critique flagged {len(crit.weak_spots)} weak spot(s)")
    if consistency:
        bits.append(f"consistency: {consistency}")
    return " | ".join(bits)


# --------------------------------------------------------------------- chains


def full_review(
    llm: LLMProvider,
    ledger: Optional[CostLedger],
    *,
    draft: BaseModel,
    schema: Type[BaseModel],
    brief: ResearchBrief,
    project: Any,
    doc_type: str,
    model: Optional[str] = None,
) -> ReviewResult:
    text = content_text(draft)
    fc: FactCheckReport = run_agent(
        llm, _m(FACT_CHECKER_AGENT, model), _factcheck_task(text, brief),
        budget=_BUDGET, ledger=ledger,
    )  # type: ignore[assignment]
    crit = run_agent(
        llm, _m(AUDIENCE_CRITIC_AGENT, model), _critic_task(text),
        variables={"audience": getattr(project, "audience", "")}, budget=_BUDGET, ledger=ledger,
    )
    edited = run_agent(
        llm, _m(editor_for(schema), model), _editor_task(draft, brief, fc, crit, doc_type),
        variables=_editor_vars(project, doc_type, schema), budget=_BUDGET, ledger=ledger,
    )
    voiced = run_agent(
        llm, _m(voice_for(schema), model), _voice_task(edited),
        variables={"schema": schema.__name__, "format_hint": _FORMAT_HINTS.get(doc_type, "")},
        budget=_BUDGET, ledger=ledger,
    )
    consistency = consistency_check(edited, voiced)
    status = "reviewed" if fc.overall == "pass" and not consistency else "flagged"
    return ReviewResult(voiced, _review_notes(fc, crit, consistency), status, fc)


def light_review(
    llm: LLMProvider,
    ledger: Optional[CostLedger],
    *,
    draft: BaseModel,
    schema: Type[BaseModel],
    doc_type: str,
    model: Optional[str] = None,
) -> ReviewResult:
    voiced = run_agent(
        llm, _m(voice_for(schema), model), _voice_task(draft),
        variables={"schema": schema.__name__, "format_hint": _FORMAT_HINTS.get(doc_type, "")},
        budget=_BUDGET, ledger=ledger,
    )
    consistency = consistency_check(draft, voiced)
    return ReviewResult(voiced, f"voice pass{'; ' + consistency if consistency else ' clean'}",
                        "flagged" if consistency else "reviewed")


def _m(agent: Agent, model: Optional[str]) -> Agent:
    from dataclasses import replace

    return replace(agent, model=model) if model else agent
