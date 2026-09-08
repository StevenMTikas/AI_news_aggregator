"""Agent definitions and the tools they can hold.

An ``Agent`` is a system-prompt template + an output schema + optional tools. The runner in
``contentforge.agent_loop`` executes one. ``library`` holds the concrete agents; ``editor_for``
/ ``voice_for`` build schema-specific editor / voice agents for the review chain.
"""

from .base import Agent, AgentBudget, Tool, render_prompt, search_tool
from .library import (
    AGENTS,
    AUDIENCE_CRITIC_AGENT,
    BLOG_WRITER_AGENT,
    BRIEF_UPDATER_AGENT,
    EDITOR_AGENT,
    FACT_CHECKER_AGENT,
    KEYWORD_AGENT,
    LINKEDIN_WRITER_AGENT,
    METADATA_AGENT,
    REPURPOSE_AGENT,
    RESEARCH_AGENT,
    SOCIAL_THREAD_AGENT,
    SYNTHESIS_AGENT,
    editor_for,
    voice_for,
)

__all__ = [
    "Agent",
    "AgentBudget",
    "Tool",
    "render_prompt",
    "search_tool",
    "editor_for",
    "voice_for",
    "AGENTS",
    "KEYWORD_AGENT",
    "RESEARCH_AGENT",
    "SYNTHESIS_AGENT",
    "BLOG_WRITER_AGENT",
    "EDITOR_AGENT",
    "FACT_CHECKER_AGENT",
    "AUDIENCE_CRITIC_AGENT",
    "METADATA_AGENT",
    "LINKEDIN_WRITER_AGENT",
    "SOCIAL_THREAD_AGENT",
    "REPURPOSE_AGENT",
    "BRIEF_UPDATER_AGENT",
]
