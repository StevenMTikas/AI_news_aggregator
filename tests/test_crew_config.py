"""
Guards against a mismatch between the {placeholder}s referenced in agents.yaml/tasks.yaml
and the keys build_default_inputs() actually supplies. CrewAI raises a plain ValueError at
generation time if any placeholder is missing from the inputs dict -- this test catches that
for free, without an LLM call or API key, by building the real crew and running its own
interpolation step directly.
"""
import pytest

from src.ai_news_aggregator.crew import AiNewsAggregator
from src.ai_news_aggregator.main import build_default_inputs
from src.ai_news_aggregator.projects import ProjectProfile
from src.ai_news_aggregator.schemas import BlogContent


@pytest.fixture(autouse=True)
def fake_api_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("SERPER_API_KEY", "test-serper-key")


def make_project() -> ProjectProfile:
    return ProjectProfile(
        slug="acme-launch",
        name="Acme Launch",
        audience="solo developers evaluating dev tools",
        tone="conversational",
        category_tags=["Productivity", "SaaS"],
        author="Jane Doe",
        target_word_count=700,
    )


def test_crew_builds_with_expected_agents_and_tasks():
    crew = AiNewsAggregator().crew()
    assert len(crew.agents) == 3
    assert len(crew.tasks) == 3


def test_blog_writer_task_has_output_pydantic_wired_to_blog_content():
    crew = AiNewsAggregator().crew()
    blog_writer_task = next(t for t in crew.tasks if t.output_pydantic is not None)
    assert blog_writer_task.output_pydantic is BlogContent


def test_all_placeholders_interpolate_without_error():
    """
    If agents.yaml/tasks.yaml reference a {placeholder} that build_default_inputs()
    doesn't supply (or vice versa -- a stale key nobody references), this either raises
    ValueError (missing key) here, or would silently do nothing (extra unused key -- not
    an error, but worth knowing about if it happens).
    """
    crew = AiNewsAggregator().crew()
    project = make_project()
    inputs = build_default_inputs("Test Topic", project)

    for t in crew.tasks:
        t.interpolate_inputs_and_add_conversation_history(inputs)
    for a in crew.agents:
        a.interpolate_inputs(inputs)
