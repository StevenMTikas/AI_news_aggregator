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
    CritiqueReport,
    FactCheckReport,
    KeywordReport,
    ResearchBrief,
    ResearchNotes,
    Section,
    Source,
)


def sr(model) -> ScriptedResponse:
    return ScriptedResponse(content=model.model_dump_json())


def _blog(**kw) -> BlogContent:
    base = dict(
        title="Draft", meta_description="d", hook="h",
        sections=[Section(heading="A", body="b")], key_points=["k"], tags=["ai"],
        sources=["https://ex.test/1"],
    )
    base.update(kw)
    return BlogContent(**base)


def blog_compose_turns(final_title="Final, edited") -> list:
    """writer -> [fact-check, critique, editor, voice] = 5 scripted LLM turns."""
    return [
        sr(_blog(title="Draft")),
        sr(FactCheckReport(overall="pass")),
        sr(CritiqueReport()),
        sr(_blog(title="edited")),
        sr(_blog(title=final_title)),
    ]


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


def test_blog_post_pipeline_runs_writer_then_review_chain():
    llm = FakeLLMProvider(blog_compose_turns("Final, edited"))

    doc = BlogPostPipeline(llm).compose(BRIEF, project())

    assert doc.type == "blog_post"
    assert doc.content.title == "Final, edited"  # last turn = voice pass output
    assert doc.review_status == "reviewed"  # fact-check passed
    assert [c.response_model for c in llm.calls] == [
        "BlogContent", "FactCheckReport", "CritiqueReport", "BlogContent", "BlogContent",
    ]
    # writer saw the brief; fact-checker saw the brief too
    assert "AI cuts no-shows" in llm.calls[0].messages[-1]["content"]
    assert "AI cuts no-shows" in llm.calls[1].messages[-1]["content"]


def test_blog_post_pipeline_passes_brief_id_into_provenance():
    llm = FakeLLMProvider(blog_compose_turns())
    doc = BlogPostPipeline(llm).compose(BRIEF, project(), brief_id="brief-7")
    assert doc.based_on_brief_ids == ["brief-7"]


def test_blog_post_pipeline_applies_project_model_override():
    llm = FakeLLMProvider(blog_compose_turns())
    BlogPostPipeline(llm).compose(BRIEF, project(default_model="gpt-4o"))
    assert all(c.model == "gpt-4o" for c in llm.calls)


def test_blog_post_flagged_when_factcheck_fails():
    turns = blog_compose_turns()
    turns[1] = sr(FactCheckReport(overall="revise", unsupported_claims=["AI cuts no-shows by 99%"]))
    doc = BlogPostPipeline(FakeLLMProvider(turns)).compose(BRIEF, project())
    assert doc.review_status == "flagged"
    assert "unsupported" in doc.review_notes


# --------------------------------------------------------- linkedin / thread / repurpose


def test_linkedin_pipeline_full_review_off_the_brief():
    from src.contentforge.pipelines.linkedin import LinkedInPipeline
    from src.contentforge.schemas import LinkedInPost

    post = LinkedInPost(hook="A real hook.", body=["stanza one", "stanza two"], hashtags=["#ai"],
                        link_url="https://ex.test/1")
    llm = FakeLLMProvider([
        sr(post), sr(FactCheckReport(overall="pass")), sr(CritiqueReport()), sr(post), sr(post),
    ])
    doc = LinkedInPipeline(llm).compose(BRIEF, project(), brief_id="b1")

    assert doc.type == "linkedin_post"
    assert isinstance(doc.content, LinkedInPost)
    assert doc.content.link_placement == "first_comment"
    assert [c.response_model for c in llm.calls] == [
        "LinkedInPost", "FactCheckReport", "CritiqueReport", "LinkedInPost", "LinkedInPost",
    ]


def test_social_thread_pipeline_light_review():
    from src.contentforge.pipelines.social import SocialThreadPipeline
    from src.contentforge.schemas import SocialThread

    thread = SocialThread(posts=["hook post", "middle", "cta post"], hashtags=["#ai"])
    llm = FakeLLMProvider([sr(thread), sr(thread)])  # writer + voice only
    doc = SocialThreadPipeline(llm).compose(BRIEF, project())

    assert doc.type == "social_thread"
    assert [c.response_model for c in llm.calls] == ["SocialThread", "SocialThread"]
    assert doc.title == "hook post"


def test_repurpose_pipeline_light_review():
    from src.contentforge.pipelines.social import RepurposePipeline
    from src.contentforge.schemas import RepurposePack, Snippet

    pack = RepurposePack(snippets=[Snippet(platform="x", text="one"), Snippet(platform="linkedin", text="two")])
    llm = FakeLLMProvider([sr(pack), sr(pack)])
    doc = RepurposePipeline(llm).compose(BRIEF, project())
    assert doc.type == "repurpose" and "2 repurposed" in doc.title


def test_voice_consistency_flags_dropped_source():
    from src.contentforge.pipelines.review import consistency_check

    before = _blog(sources=["https://a.test", "https://b.test"])
    after = _blog(sources=["https://a.test"])
    assert "dropped 1 source" in consistency_check(before, after)
    assert consistency_check(before, before) == ""


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
