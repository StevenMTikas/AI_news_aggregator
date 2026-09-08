from types import SimpleNamespace

import pytest

from src.contentforge.db import connection
from src.contentforge.providers.base import SearchBudget, SearchResult
from src.contentforge.providers.fakes import FakeLLMProvider, ScriptedResponse
from src.contentforge.providers.serper import NullSearchProvider, SerperSearchProvider
from src.contentforge.run_service import RunService
from src.contentforge.schemas import (
    BlogContent,
    CritiqueReport,
    DocumentMetadata,
    FactCheckReport,
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
    """keyword -> research(tool + notes) -> synthesis -> brief fact-check = 5 turns."""
    return [
        sr(KeywordReport(primary_keywords=["ai reservations"])),
        ScriptedResponse(tool_calls=[("web_search", {"query": "restaurant ai 2026"})]),
        sr(ResearchNotes(findings=["AI cuts no-shows"], sources=[Source(url="https://ex.test/1", takeaway="down 20%")])),
        sr(ResearchBrief(topic="x", summary="s", key_findings=["AI cuts no-shows"], sources=[Source(url="https://ex.test/1", takeaway="down 20%")])),
        sr(FactCheckReport(overall="pass")),  # brief fact-check
    ]


def _blog_turns(title="The Post"):
    """writer -> fact-check -> critique -> editor -> voice = 5 turns."""
    draft = BlogContent(
        title="draft", meta_description="m", hook="h",
        sections=[Section(heading="A", body="b")], key_points=["k"], tags=["ai"], sources=["https://ex.test/1"],
    )
    final = draft.model_copy(update={"title": title})
    return [sr(draft), sr(FactCheckReport(overall="pass")), sr(CritiqueReport()), sr(final), sr(final)]


def _metadata_turn():
    return [sr(DocumentMetadata(title_options=["A title"], slug="a-title"))]


def _atomic_blog(title="The Post"):
    return _research_turns() + _blog_turns(title) + _metadata_turn()


def make_service(tmp_path, llm, search=None, **kw):
    return RunService(
        llm=llm,
        search_provider=search or NullSearchProvider([SearchResult("t", "https://ex.test/1", "down")]),
        output_dir=tmp_path,
        **kw,
    )


def test_run_atomic_produces_and_writes_blog_post(tmp_path):
    llm = FakeLLMProvider(_atomic_blog("Reservations, Reinvented"))
    svc = make_service(tmp_path, llm)

    result = svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07")

    assert result.reused_brief is False
    assert result.content.title == "Reservations, Reinvented"
    path = result.primary_path
    assert path.exists() and path.name == "2026-09-07-reservations-reinvented-blog-post.md"
    md = path.read_text(encoding="utf-8")
    assert "author: Sam Rivera" in md and "categories: [Food, AI]" in md


def test_run_atomic_emits_multiple_artifacts_from_one_brief(tmp_path):
    from src.contentforge.db import documents
    from src.contentforge.schemas import LinkedInPost, SocialThread

    li = LinkedInPost(hook="hook", body=["one"], hashtags=["#ai"])
    th = SocialThread(posts=["a", "b", "c"], hashtags=["#ai"])
    llm = FakeLLMProvider(
        _research_turns()
        + _blog_turns("Blog")
        + [sr(li), sr(FactCheckReport(overall="pass")), sr(CritiqueReport()), sr(li), sr(li)]
        + [sr(th), sr(th)]
        + _metadata_turn()
    )
    svc = make_service(tmp_path, llm)

    result = svc.run_atomic(
        project(), "AI for restaurants",
        artifacts=("blog_post", "linkedin_post", "social_thread"), current_date="2026-09-07",
    )

    types = {d.type for d in documents.list_documents(run_id=result.run_id)}
    assert {"blog_post", "linkedin_post", "social_thread", "metadata"} <= types
    # one research pass feeds all three artifacts (the FakeLLM script has no spare
    # research turns -- it would raise if an artifact re-triggered research)
    with connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM research_brief").fetchone()[0] == 1


def test_second_run_same_topic_reuses_brief(tmp_path):
    llm = FakeLLMProvider(
        _research_turns() + _blog_turns("First") + _metadata_turn()
        + _blog_turns("Second") + _metadata_turn()  # 2nd run: no research
    )
    svc = make_service(tmp_path, llm)

    r1 = svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07")
    r2 = svc.run_atomic(project(), "for  restaurants   AI", current_date="2026-09-08")

    assert r2.reused_brief is True
    assert r1.brief == r2.brief
    assert r2.content.title == "Second"


def test_force_fresh_bypasses_cache(tmp_path):
    llm = FakeLLMProvider(_atomic_blog("A") + _atomic_blog("B"))
    svc = make_service(tmp_path, llm)

    svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07")
    r2 = svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07", force_fresh=True)

    assert r2.reused_brief is False
    assert r2.content.title == "B"


def test_search_cost_recorded_from_budget(tmp_path):
    transport = lambda url, payload, headers: {"organic": [{"title": "R", "link": "https://ex.test/1", "snippet": "s"}]}
    serper = SerperSearchProvider("key", budget=SearchBudget(max_calls=5), transport=transport)
    llm = FakeLLMProvider(_atomic_blog())
    svc = make_service(tmp_path, llm, search=serper)

    result = svc.run_atomic(project(), "AI for restaurants", current_date="2026-09-07")

    assert result.cost.search_calls == 1  # one live web_search during research


def test_unknown_artifact_raises(tmp_path):
    llm = FakeLLMProvider(_research_turns())
    svc = make_service(tmp_path, llm)
    with pytest.raises(ValueError, match="unknown artifact"):
        svc.run_atomic(project(), "topic", artifacts=("podcast",), current_date="2026-09-07")


def test_second_topic_is_primed_with_prior_findings(tmp_path):
    llm = FakeLLMProvider(_atomic_blog("A") + _atomic_blog("B"))
    svc = make_service(tmp_path, llm)
    p = project(subject_focus="restaurant technology for independents")

    svc.run_atomic(p, "AI reservation software", current_date="2026-09-07")
    llm.calls.clear()
    svc.run_atomic(p, "AI kitchen inventory tools", current_date="2026-09-08")

    keyword_task = llm.calls[0].messages[-1]["content"]
    assert "Project focus: restaurant technology" in keyword_task
    assert "already established" in keyword_task


def test_update_brief_supersedes_and_records_a_run(tmp_path):
    from src.contentforge.db import briefs, runs

    llm = FakeLLMProvider(
        _atomic_blog("A")
        + [ScriptedResponse(tool_calls=[("web_search", {"query": "q"})]),
           sr(ResearchBrief(topic="x", summary="fresher picture", key_findings=["new fact"]))]
    )
    svc = make_service(tmp_path, llm)
    p = project()

    r1 = svc.run_atomic(p, "AI reservations", current_date="2026-09-07")
    old_id = briefs.find_fresh_brief("acme", "ai reservations").id

    updated = svc.update_brief(p, old_id, current_date="2026-10-01")

    assert "fresher picture" in updated.summary
    assert briefs.get_brief(old_id).brief  # still there, just superseded
    fresh = briefs.find_fresh_brief("acme", "ai reservations")
    assert fresh.id != old_id and "fresher picture" in fresh.brief.summary
    assert any(run.kind == "research" and run.status == "completed" for run in runs.list_runs())


# ------------------------------------------------------------------ compilation


def test_start_compilation_builds_longform_from_selected_runs(tmp_path):
    from src.contentforge.corpus import CorpusSelection
    from src.contentforge.db import documents
    from src.contentforge.schemas import (
        Guide, GuideSection, Outline, OutlineNode,
    )

    # two atomic runs to draw the corpus from
    llm = FakeLLMProvider(_atomic_blog("Bookings") + _atomic_blog("Inventory"))
    svc = make_service(tmp_path, llm)
    p = project()
    r1 = svc.run_atomic(p, "AI reservations", current_date="2026-09-07")
    r2 = svc.run_atomic(p, "AI inventory", current_date="2026-09-08")

    outline = Outline(title="Restaurant AI Guide", nodes=[OutlineNode(heading="Ops", points=["p"])])
    guide = Guide(title="Restaurant AI Guide", introduction="i",
                  sections=[GuideSection(heading="Ops", body="AI helps ops.", key_takeaway="start small")],
                  checklist=["Pick one tool"], sources=[])
    llm.queue(
        sr(outline), sr(guide), sr(FactCheckReport(overall="pass")), sr(CritiqueReport()),
        sr(guide), sr(guide),
    )

    result = svc.start_compilation(
        p, "guide", CorpusSelection(run_ids=[r1.run_id, r2.run_id], include_retrieval=False),
        angle="how independents adopt AI", current_date="2026-10-01",
    )

    assert result.content.title == "Restaurant AI Guide"
    assert result.primary_path.exists() and result.primary_path.suffix == ".pdf"
    assert result.primary_path.read_bytes()[:5] == b"%PDF-"

    doc = documents.list_documents(project_slug="acme", limit=1)[0]
    assert doc.type == "guide"
    # cites the two selected runs' briefs, no others
    assert len(doc.based_on_brief_ids) == 2


def test_start_compilation_fails_with_empty_corpus(tmp_path):
    from src.contentforge.corpus import CorpusSelection

    svc = make_service(tmp_path, FakeLLMProvider([]))
    with pytest.raises(ValueError, match="no prior content"):
        svc.start_compilation(project(), "newsletter", CorpusSelection(run_ids=["nope"]),
                              current_date="2026-10-01")
