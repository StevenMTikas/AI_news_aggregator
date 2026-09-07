"""Agent definitions and the tools they can hold.

An ``Agent`` is a system-prompt template + an output schema + optional tools. The runner in
``contentforge.agent_loop`` executes one. ``library`` holds the concrete agents for the
research and blog pipelines.
"""

from .base import Agent, AgentBudget, Tool, render_prompt, search_tool
from .library import (
    AGENTS,
    BLOG_WRITER_AGENT,
    BRIEF_UPDATER_AGENT,
    EDITOR_AGENT,
    KEYWORD_AGENT,
    RESEARCH_AGENT,
    SYNTHESIS_AGENT,
)

__all__ = [
    "Agent",
    "AgentBudget",
    "Tool",
    "render_prompt",
    "search_tool",
    "AGENTS",
    "KEYWORD_AGENT",
    "RESEARCH_AGENT",
    "SYNTHESIS_AGENT",
    "BLOG_WRITER_AGENT",
    "EDITOR_AGENT",
    "BRIEF_UPDATER_AGENT",
]
