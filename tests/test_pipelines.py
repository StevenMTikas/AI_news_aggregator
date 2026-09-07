from types import SimpleNamespace

from src.contentforge.cost import CostLedger
from src.contentforge.pipelines.base import resolve_target_words
from src.contentforge.pipelines.blog_post import BlogPostPipeline
from src.contentforge.pipelines.research import ResearchPipeline
from src.contentforge.providers.base import SearchResult
from src.contentforge.providers.fakes import FakeLLMProvider, ScriptedResponse
from src.contentforge.providers.serper import NullSearchProvider
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
        name="Acme", audience="restaurant owners", tone="warm", author="Sam",
        category_tags=["Food"], notes="", target_word_count=700, slug="acme",
    )
    base.update(kw)
    return SimpleNamespace(**base)


BRIEF = ResearchBrief(
    topic="AI for restaurants",
    summary="AI is reshaping reservations.",
    key_findings=["AI cuts no-shows by 20%"],
    sources=[Source(url="https://ex.test/1", takeaway="no-shows down 20%")],
    keyword_report=KeywordReport(primary_keywords=["ai reservations", "restaurant ai"]),
)


# ------------------------------------------------------------------ research


def test_research_pipeline_runs_keyword_research_synthesis():
    llm = FakeLLMProvider(
        [
            sr(KeywordReport(primary_keywords=["ai reservations", "restaurant ai"], long_tail=["ai no-show tool"])),
            ScriptedResponse(tool_calls=[("web_search", {"query": "restaurant ai reservations 2026"})]),
            sr(ResearchNotes(
                queries=["restaurant ai reservations 2026"],
                findings=["AI cuts no-shows by 20%"],
                sources=[Source(url="https://ex.test/1", takeaway="no-shows down 20%")],
            )),
            sr(ResearchBrief(
                topic="ignored - pipeline overwrites",
                summary="AI is reshaping reservations.",
                key_findings=["AI cuts no-shows by 20%"],
                sources=[Source(url="https://ex.test/1", takeaway="no-shows down 20%")],
            )),
        ]
    )
    search = NullSearchProvider([SearchResult("AI booking", "https://ex.test/1", "no-shows down")])
    ledger = CostLedger()

    brief = ResearchPipeline(llm, search, ledger=ledger).run(
        "AI for restaurants", audience="restaurant owners", current_year=2026
    )

    assert brief.topic == "AI for restaurants"  # pipeline forces it
    assert brief.keyword_report.primary_keywords == ["ai reservations", "restaurant ai"]
    assert brief.sources[0].url == "https://ex.test/1"
    # the research agent's web_search result reached the model
    assert any("no-shows down" in m["content"] for c in llm.calls for m in c.messages if m["role"] == "tool")
    assert len(ledger.events) == 4  # three agents, one with an extra tool-turn


# ------------------------------------------------------------------ blog post


def test_blog_post_pipeline_writes_then_edits():
    draft = BlogContent(
        title="Draft", meta_description="d", hook="h",
        sections=[Section(heading="A", body="b")], key_points=["k"], tags=["ai"], sources=["https://ex.test/1"],
    )
    final = draft.model_copy(update={"title": "Final, edited"})
    llm = FakeLLMProvider([sr(draft), sr(final)])

    doc = BlogPostPipeline(llm).compose(BRIEF, project())

    assert doc.type == "blog_post"
    assert doc.content.title == "Final, edited"
    assert doc.title == "Final, edited"
    # writer saw the brief; editor saw draft + brief
    assert "AI cuts no-shows" in llm.calls[0].messages[-1]["content"]
    assert "Draft" in llm.calls[1].messages[-1]["content"]


def test_blog_post_pipeline_passes_brief_id_into_provenance():
    b = BlogContent(title="t", meta_description="m", hook="h", sections=[Section(heading="A", body="b")], key_points=["k"], tags=[], sources=[])
    llm = FakeLLMProvider([sr(b), sr(b)])
    doc = BlogPostPipeline(llm).compose(BRIEF, project(), brief_id="brief-7")
    assert doc.based_on_brief_ids == ["brief-7"]


def test_blog_post_pipeline_applies_project_model_override():
    b = BlogContent(title="t", meta_description="m", hook="h", sections=[Section(heading="A", body="b")], key_points=["k"], tags=[], sources=[])
    llm = FakeLLMProvider([sr(b), sr(b)])
    BlogPostPipeline(llm).compose(BRIEF, project(default_model="gpt-4o"))
    assert llm.calls[0].model == "gpt-4o" and llm.calls[1].model == "gpt-4o"


# ------------------------------------------------------------------ length


def test_resolve_target_words_precedence():
    assert resolve_target_words(800, project(target_word_count=500), "blog_post") == 500
    assert resolve_target_words(800, SimpleNamespace(length_overrides={"blog_post": 300}, target_word_count=500), "blog_post") == 300
    assert resolve_target_words(800, SimpleNamespace(), "blog_post") == 800


# --------------------------------------------------------------- brief updater


def test_update_brief_reruns_against_existing():
    prior = ResearchBrief(
        topic="AI for restaurants", summary="old picture",
        key_findings=["2025: pilots underway"],
        keyword_report=KeywordReport(primary_keywords=["ai reservations"]),
    )
    updated_out = ResearchBrief(
        topic="ignored", summary="2026: mainstream",
        key_findings=["AI hosts now standard", "no-shows down 25%"],
        sources=[Source(url="https://ex.test/new", takeaway="mainstream in 2026")],
    )
    llm = FakeLLMProvider(
        [
            ScriptedResponse(tool_calls=[("web_search", {"query": "restaurant ai 2026 update"})]),
            sr(updated_out),
        ]
    )
    search = NullSearchProvider([SearchResult("New", "https://ex.test/new", "mainstream")])

    result = ResearchPipeline(llm, search).update_brief(prior, audience="owners", current_year=2026)

    assert result.topic == "AI for restaurants"  # preserved
    assert result.keyword_report.primary_keywords == ["ai reservations"]  # carried over
    assert "mainstream" in result.summary
    # the updater saw the old brief
    assert "old picture" in llm.calls[0].messages[-1]["content"]
