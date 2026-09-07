from types import SimpleNamespace

import pytest

from src.contentforge.providers.base import SearchBudget, SearchResult
from src.contentforge.providers.fakes import FakeLLMProvider, ScriptedResponse
from src.contentforge.providers.serper import NullSearchProvider, SerperSearchProvider
from src.contentforge.run_service import RunService
from src.contentforge.schemas import (
    BlogContent,
    KeywordReport,
    ResearchBrief,
    ResearchNotes,
    Section,
    Source,
)


def sr(model) -> ScriptedResponse:
    return ScriptedResponse(content=model.model_dump_json())


def project(**kw):
    base = dict(
        name="Acme", audience="restaurant owners", tone="warm", author="Sam Rivera",
        category_tags=["Food", "AI"], notes="", target_word_count=700, slug="acme",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _research_turns():
    return [
        sr(KeywordReport(primary_keywords=["ai reservations"])),
        ScriptedResponse(tool_calls=[("web_search", {"query": "restaurant ai 2026"})]),
        sr(ResearchNotes(findings=["AI cuts no-shows"], sources=[Source(url="https://ex.test/1", takeaway="down 20%")])),
        sr(ResearchBrief(topic="x", summary="s", key_findings=["AI cuts no-shows"], sources=[Source(url="https://ex.test/1", takeaway="down 20%")])),
    ]


def _blog_turns(title="The Post"):
    draft = BlogContent(
        title="draft", meta_description="m", hook="h",
        sections=[Section(heading="A", body="b")], key_points=["k"], tags=["ai"], sources=["https://ex.test/1"],
    )
    return [sr(draft), sr(draft.model_copy(update={"title": title}))]


def make_service(tmp_path, llm, search=None, **kw):
    return RunService(
        llm=llm,
        search_provider=search or NullSearchProvider([SearchResult("t", "https://ex.test/1", "down")]),
        output_dir=tmp_path,
        **kw,
    )


def test_run_atomic_produces_and_writes_blog_post(tmp_path):
    llm = FakeLLMProvider(_research_turns() + _blog_turns("Reservations, Reinvented"))
    svc = make_service(tmp_path, llm)

    result = svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07")

    assert result.reused_brief is False
    assert result.content.title == "Reservations, Reinvented"
    path = result.primary_path
    assert path.exists() and path.name == "2026-09-07-reservations-reinvented-blog-post.md"
    md = path.read_text(encoding="utf-8")
    assert "author: Sam Rivera" in md and "categories: [Food, AI]" in md


def test_second_run_same_topic_reuses_brief(tmp_path):
    # only two blog turns available for the second run -> if it re-researched, FakeLLM raises
    llm = FakeLLMProvider(_research_turns() + _blog_turns("First") + _blog_turns("Second"))
    svc = make_service(tmp_path, llm)

    r1 = svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07")
    r2 = svc.run_atomic(project(), "for  restaurants   AI", current_date="2026-09-08")  # normalises equal

    assert r2.reused_brief is True
    assert r1.brief is r2.brief
    assert r2.content.title == "Second"


def test_force_fresh_bypasses_cache(tmp_path):
    llm = FakeLLMProvider(_research_turns() + _blog_turns("A") + _research_turns() + _blog_turns("B"))
    svc = make_service(tmp_path, llm)

    svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07")
    r2 = svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07", force_fresh=True)

    assert r2.reused_brief is False
    assert r2.content.title == "B"


def test_search_cost_recorded_from_budget(tmp_path):
    transport = lambda url, payload, headers: {"organic": [{"title": "R", "link": "https://ex.test/1", "snippet": "s"}]}
    serper = SerperSearchProvider("key", budget=SearchBudget(max_calls=5), transport=transport)
    llm = FakeLLMProvider(_research_turns() + _blog_turns())
    svc = make_service(tmp_path, llm, search=serper)

    result = svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07")

    assert result.cost.search_calls == 1  # one live web_search during research


def test_unknown_artifact_raises(tmp_path):
    llm = FakeLLMProvider(_research_turns())
    svc = make_service(tmp_path, llm)
    with pytest.raises(ValueError, match="unknown artifact"):
        svc.run_atomic(project(), "topic", artifacts=("podcast",), current_date="2026-09-07")
