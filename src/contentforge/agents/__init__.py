"""Agent definitions and the tools they can hold.

An ``Agent`` is a system-prompt template + an output schema + optional tools. The runner in
``contentforge.agent_loop`` executes one. Concrete agents (keyword, research, synthesis,
fact_checker, ...) arrive in Phases 4 and 7 of ARCHITECTURE_PLAN.md.
"""

from .base import Agent, AgentBudget, Tool, render_prompt, search_tool

__all__ = ["Agent", "AgentBudget", "Tool", "render_prompt", "search_tool"]
