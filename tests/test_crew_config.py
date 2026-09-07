"""
Guards against a mismatch between the {placeholder}s referenced in agents.yaml/tasks.yaml
and the keys build_default_inputs() actually supplies. CrewAI raises a plain ValueError at
generation time if any placeholder is missing from the inputs dict -- this test catches that
for free, without an LLM call or API key, by building the real crew and running its own
interpolation step directly.
"""
import pytest

from src.contentforge.crew import ContentForgeCrew
from src.contentforge.main import build_default_inputs
from src.contentforge.projects import ProjectProfile
from src.contentforge.schemas import BlogContent


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
    crew = ContentForgeCrew().crew()
    assert len(crew.agents) == 3
    assert len(crew.tasks) == 3


def test_blog_writer_task_has_output_pydantic_wired_to_blog_content():
    crew = ContentForgeCrew().crew()
    blog_writer_task = next(t for t in crew.tasks if t.output_pydantic is not None)
    assert blog_writer_task.output_pydantic is BlogContent


def test_blog_writer_task_receives_both_research_and_keyword_context():
    """
    The writer's prompt references the keyword research directly ("tags: drawn from the
    keyword research"), so the keyword task must be in its context -- not only reachable
    transitively through the researcher's prose.
    """
    crew = ContentForgeCrew().crew()
    blog_writer_task = next(t for t in crew.tasks if t.output_pydantic is not None)
    context_names = {t.name for t in blog_writer_task.context}
    assert context_names == {"research_task", "keyword_research_task"}


def test_all_placeholders_interpolate_without_error():
    """
    If agents.yaml/tasks.yaml reference a {placeholder} that build_default_inputs()
    doesn't supply (or vice versa -- a stale key nobody references), this either raises
    ValueError (missing key) here, or would silently do nothing (extra unused key -- not
    an error, but worth knowing about if it happens).
    """
    crew = ContentForgeCrew().crew()
    project = make_project()
    inputs = build_default_inputs("Test Topic", project)

    for t in crew.tasks:
        t.interpolate_inputs_and_add_conversation_history(inputs)
    for a in crew.agents:
        a.interpolate_inputs(inputs)
