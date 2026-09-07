"""Run one :class:`~contentforge.agents.base.Agent` to a validated structured output.

This is the whole orchestration layer -- a tool-calling loop with iteration and tool-call
caps that emits LLM cost events. It replaces CrewAI for the linear/DAG pipelines this project
uses. Search-call cost is *not* recorded here: it is derived from ``SearchBudget.calls_made``
by the orchestrator, so cache hits are never charged.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from pydantic import BaseModel, ValidationError

from .agents.base import Agent, AgentBudget
from .cost import CostLedger
from .providers.base import LLMProvider, LLMResult

_FINALIZE = "Provide your final answer now as the required structured output. Do not call tools."


class AgentLoopError(RuntimeError):
    """The agent could not produce a valid output within its budget."""


def run_agent(
    llm: LLMProvider,
    agent: Agent,
    task: str,
    *,
    variables: Mapping[str, Any] | None = None,
    budget: AgentBudget | None = None,
    ledger: CostLedger | None = None,
    provider_name: str = "openai",
) -> BaseModel:
    budget = budget or AgentBudget()
    tools_by_name = {t.spec.name: t for t in agent.tools}
    specs = agent.tool_specs() or None

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": agent.render_system_prompt(variables or {})},
        {"role": "user", "content": task},
    ]

    for _ in range(budget.max_iterations):
        offer_tools = specs if (specs and budget.tool_calls_left > 0) else None
        result = _complete(llm, agent, messages, offer_tools, ledger, provider_name)

        if not result.tool_calls:
            return _parse(agent, result)

        messages.append(_assistant_message(result))
        for call in result.tool_calls:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": _run_tool(tools_by_name, call.name, call.arguments, budget),
                }
            )

    # Ran out of iterations while still calling tools -- force a toolless final answer.
    messages.append({"role": "user", "content": _FINALIZE})
    return _parse(agent, _complete(llm, agent, messages, None, ledger, provider_name))


# --------------------------------------------------------------------------- internals


def _complete(
    llm: LLMProvider,
    agent: Agent,
    messages: list[dict[str, Any]],
    tools: Any,
    ledger: CostLedger | None,
    provider_name: str,
) -> LLMResult:
    result = llm.complete(
        messages,
        tools=tools,
        response_model=agent.output_schema,
        model=agent.model,
        temperature=agent.temperature,
    )
    if ledger is not None:
        ledger.record_llm(provider_name, result.model, result.tokens_in, result.tokens_out)
    return result


def _run_tool(
    tools_by_name: Mapping[str, Any],
    name: str,
    arguments: Mapping[str, Any],
    budget: AgentBudget,
) -> str:
    tool = tools_by_name.get(name)
    if tool is None:
        return f"Error: no tool named {name!r} is available."
    if budget.tool_calls_left <= 0:
        return "Tool-call budget exhausted. Provide your final answer now."
    try:
        output = tool.run(**dict(arguments))
    except TypeError as exc:
        return f"Error calling {name}: {exc}"
    budget.record_tool_call()
    return output


def _assistant_message(result: LLMResult) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": result.content or "",
        "tool_calls": [
            {
                "id": call.id,
                "type": "function",
                "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
            }
            for call in result.tool_calls
        ],
    }


def _parse(agent: Agent, result: LLMResult) -> BaseModel:
    if not result.content:
        raise AgentLoopError(
            f"{agent.name}: model returned no content and no tool call (finish_reason="
            f"{result.finish_reason!r})"
        )
    try:
        return agent.output_schema.model_validate_json(result.content)
    except ValidationError as exc:
        raise AgentLoopError(
            f"{agent.name}: output did not match {agent.output_schema.__name__}: {exc}"
        ) from exc
