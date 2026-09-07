"""The research pipeline: topic -> ResearchBrief, via keyword -> research -> synthesis.

Expensive (this is the only place search credits are spent). The orchestrator caches the
brief so composition never triggers it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from ..agents.base import AgentBudget, search_tool
from ..agents.library import BRIEF_UPDATER_AGENT, KEYWORD_AGENT, RESEARCH_AGENT, SYNTHESIS_AGENT
from ..agent_loop import run_agent
from ..cost import CostLedger
from ..providers.base import LLMProvider, SearchProvider
from ..schemas import KeywordReport, ResearchBrief, ResearchNotes


def _priming_block(priming: str) -> str:
    return (
        "\n\nWhat this project already established on this beat (build on it, surface what's "
        f"new or changed -- do not re-derive what's known):\n{priming}"
        if priming
        else ""
    )


def _keyword_task(topic: str, priming: str) -> str:
    return f'Generate the keyword set for: "{topic}".' + _priming_block(priming)


def _research_task(kw: KeywordReport, min_sources: int, priming: str) -> str:
    primary = "\n- ".join(kw.primary_keywords) or "(none supplied)"
    also = ", ".join([*kw.long_tail, *kw.trending]) or "(none)"
    return (
        f"Primary keywords to investigate:\n- {primary}\n\n"
        f"Also relevant: {also}\n\n"
        f"Find at least {min_sources} distinct credible sources and record queries, findings, "
        "and sources." + _priming_block(priming)
    )


def _synthesis_task(kw: KeywordReport, notes: ResearchNotes, priming: str) -> str:
    primary = "\n- ".join(kw.primary_keywords) or "(none)"
    return (
        f"Primary keywords:\n- {primary}\n\n"
        f"Research notes (JSON):\n{notes.model_dump_json(indent=2)}" + _priming_block(priming)
    )


class ResearchPipeline:
    def __init__(
        self,
        llm: LLMProvider,
        search_provider: SearchProvider,
        *,
        ledger: CostLedger | None = None,
        keyword_agent=KEYWORD_AGENT,
        research_agent=RESEARCH_AGENT,
        synthesis_agent=SYNTHESIS_AGENT,
    ) -> None:
        self.llm = llm
        self.search_provider = search_provider
        self.ledger = ledger
        self.keyword_agent = keyword_agent
        self.research_agent = research_agent
        self.synthesis_agent = synthesis_agent

    def run(
        self,
        topic: str,
        *,
        audience: str,
        current_year: int,
        subject_focus: str = "",
        recency_days: Optional[int] = None,
        min_sources: int = 5,
        priming: str = "",
        model: Optional[str] = None,
        max_searches: int = 8,
    ) -> ResearchBrief:
        variables = {
            "topic": topic,
            "audience": audience,
            "current_year": str(current_year),
            "subject_focus": subject_focus or "(not specified)",
            "min_sources": min_sources,
        }

        keyword_agent = replace(self.keyword_agent, model=model) if model else self.keyword_agent
        keywords: KeywordReport = run_agent(
            self.llm,
            keyword_agent,
            _keyword_task(topic, priming),
            variables=variables,
            budget=AgentBudget(max_iterations=2, max_tool_calls=0),
            ledger=self.ledger,
        )  # type: ignore[assignment]

        research_agent = replace(
            self.research_agent,
            model=model or self.research_agent.model,
            tools=(search_tool(self.search_provider, recency_days=recency_days, limit=8),),
        )
        notes: ResearchNotes = run_agent(
            self.llm,
            research_agent,
            _research_task(keywords, min_sources, priming),
            variables=variables,
            budget=AgentBudget(max_iterations=max_searches + 3, max_tool_calls=max_searches),
            ledger=self.ledger,
        )  # type: ignore[assignment]

        synthesis_agent = replace(self.synthesis_agent, model=model) if model else self.synthesis_agent
        brief: ResearchBrief = run_agent(
            self.llm,
            synthesis_agent,
            _synthesis_task(keywords, notes, priming),
            variables=variables,
            budget=AgentBudget(max_iterations=2, max_tool_calls=0),
            ledger=self.ledger,
        )  # type: ignore[assignment]

        brief.topic = topic
        brief.keyword_report = keywords
        return brief

    def update_brief(
        self,
        prior: ResearchBrief,
        *,
        audience: str,
        current_year: int,
        recency_days: Optional[int] = None,
        max_searches: int = 6,
    ) -> ResearchBrief:
        """Re-research a topic against an existing brief: what's new / changed / gone."""
        variables = {"topic": prior.topic, "audience": audience, "current_year": str(current_year)}
        agent = replace(
            BRIEF_UPDATER_AGENT,
            tools=(search_tool(self.search_provider, recency_days=recency_days, limit=8),),
        )
        updated: ResearchBrief = run_agent(
            self.llm,
            agent,
            "Current brief (JSON):\n" + prior.model_dump_json(indent=2),
            variables=variables,
            budget=AgentBudget(max_iterations=max_searches + 3, max_tool_calls=max_searches),
            ledger=self.ledger,
        )  # type: ignore[assignment]
        updated.topic = prior.topic
        updated.keyword_report = prior.keyword_report
        return updated
