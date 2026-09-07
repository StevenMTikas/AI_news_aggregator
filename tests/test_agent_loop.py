import pytest
from pydantic import BaseModel

from src.contentforge.agent_loop import AgentLoopError, run_agent
from src.contentforge.agents.base import Agent, AgentBudget, render_prompt, search_tool
from src.contentforge.cost import CostLedger
from src.contentforge.providers.base import SearchResult
from src.contentforge.providers.fakes import FakeLLMProvider, ScriptedResponse
from src.contentforge.providers.serper import NullSearchProvider


class Answer(BaseModel):
    value: str


def make_agent(**overrides) -> Agent:
    defaults = dict(
        name="answerer",
        system_prompt="You answer as {who}.",
        output_schema=Answer,
    )
    defaults.update(overrides)
    return Agent(**defaults)


# ---------------------------------------------------------------- render_prompt


def test_render_prompt_fills_known_leaves_unknown():
    assert render_prompt("hi {name}, {missing}", {"name": "Sam"}) == "hi Sam, {missing}"


# ------------------------------------------------------------------- basic loop


def test_returns_parsed_output_with_no_tools():
    llm = FakeLLMProvider([ScriptedResponse(content='{"value": "42"}', tokens_in=10, tokens_out=5)])
    ledger = CostLedger()

    result = run_agent(llm, make_agent(), "the question", variables={"who": "a bot"}, ledger=ledger)

    assert isinstance(result, Answer) and result.value == "42"
    assert llm.calls[0].messages[0] == {"role": "system", "content": "You answer as a bot."}
    assert llm.calls[0].messages[1] == {"role": "user", "content": "the question"}
    assert llm.calls[0].response_model == "Answer"
    assert ledger.tokens_in == 10 and ledger.tokens_out == 5


def test_invalid_json_raises_agent_loop_error():
    llm = FakeLLMProvider([ScriptedResponse(content="not json")])
    with pytest.raises(AgentLoopError, match="did not match Answer"):
        run_agent(llm, make_agent(), "q")


def test_empty_response_raises_agent_loop_error():
    llm = FakeLLMProvider([ScriptedResponse(content=None)])
    with pytest.raises(AgentLoopError, match="no content"):
        run_agent(llm, make_agent(), "q")


# --------------------------------------------------------------------- tool use


def test_runs_tool_then_produces_final_answer():
    search = NullSearchProvider([SearchResult("Result One", "https://x.test/1", "a snippet")])
    agent = make_agent(tools=(search_tool(search),))
    llm = FakeLLMProvider(
        [
            ScriptedResponse(tool_calls=[("web_search", {"query": "anything"})]),
            ScriptedResponse(content='{"value": "done"}'),
        ]
    )
    budget = AgentBudget()
    ledger = CostLedger()

    result = run_agent(llm, agent, "research it", budget=budget, ledger=ledger)

    assert result.value == "done"
    assert budget.tool_calls_made == 1
    # the tool's rendered output was fed back to the model on the second turn
    tool_msg = llm.calls[1].messages[-1]
    assert tool_msg["role"] == "tool" and "Result One" in tool_msg["content"]
    assert len(ledger.events) == 2


def test_tool_budget_exhaustion_forces_answer():
    search = NullSearchProvider([SearchResult("R", "https://x.test/1")])
    agent = make_agent(tools=(search_tool(search),))
    llm = FakeLLMProvider(
        [
            ScriptedResponse(tool_calls=[("web_search", {"query": "one"})]),
            ScriptedResponse(content='{"value": "forced"}'),
        ]
    )
    budget = AgentBudget(max_tool_calls=1)

    result = run_agent(llm, agent, "go", budget=budget)

    assert result.value == "forced"
    assert budget.tool_calls_made == 1
    assert llm.calls[1].tools == []  # no tools offered once the budget is spent


def test_unknown_tool_name_is_reported_to_model():
    agent = make_agent(tools=())
    llm = FakeLLMProvider(
        [
            ScriptedResponse(tool_calls=[("mystery", {})]),
            ScriptedResponse(content='{"value": "ok"}'),
        ]
    )
    run_agent(llm, agent, "go", budget=AgentBudget())
    assert "no tool named 'mystery'" in llm.calls[1].messages[-1]["content"]


def test_iteration_cap_triggers_finalize_turn():
    search = NullSearchProvider([SearchResult("R", "https://x.test/1")])
    agent = make_agent(tools=(search_tool(search),))
    llm = FakeLLMProvider(
        [
            ScriptedResponse(tool_calls=[("web_search", {"query": "a"})]),
            ScriptedResponse(tool_calls=[("web_search", {"query": "b"})]),
            ScriptedResponse(content='{"value": "final"}'),
        ]
    )
    result = run_agent(llm, agent, "go", budget=AgentBudget(max_iterations=2, max_tool_calls=9))

    assert result.value == "final"
    assert llm.calls[-1].messages[-1]["content"].startswith("Provide your final answer")
