"""The review chain + a small AI-tell regression fixture."""

from src.contentforge.pipelines.review import (
    consistency_check,
    content_text,
    content_urls,
    full_review,
    light_review,
)
from src.contentforge.providers.fakes import FakeLLMProvider, ScriptedResponse
from src.contentforge.schemas import (
    BlogContent,
    CritiqueReport,
    FactCheckReport,
    LinkedInPost,
    ResearchBrief,
    Section,
    Source,
)


def sr(m):
    return ScriptedResponse(content=m.model_dump_json())


BRIEF = ResearchBrief(
    topic="AI for restaurants", summary="AI is reshaping bookings.",
    key_findings=["No-shows fell 22% in one pilot"],
    sources=[Source(url="https://sevenrooms.test/study", takeaway="no-shows down 22%")],
)

# A paragraph thick with AI-tell patterns, and a human-voiced rewrite that keeps the fact.
SLOP = (
    "In today's fast-paced restaurant landscape, it's worth noting that AI is not just a "
    "trend -- it's a fundamental shift. Studies have shown that no-shows fell 22% in one "
    "pilot, which is a testament to the transformative power of this technology. It's "
    "important to delve into how operators can leverage these tools."
)
CLEAN = (
    "One pilot cut no-shows by 22%. That is the number worth holding onto. "
    "The tools that got there are booking systems that predict which reservations won't "
    "show and release the table early. Here is how a small dining room can start."
)


def _blog(body: str) -> BlogContent:
    return BlogContent(
        title="AI Bookings", meta_description="m", hook="Your Friday rush, handled.",
        sections=[Section(heading="No-shows", body=body)], key_points=["fewer empty tables"],
        tags=["ai"], sources=["https://sevenrooms.test/study"],
    )


# --------------------------------------------------------------- consistency check


def test_consistency_check_clean_when_facts_and_sources_preserved():
    assert consistency_check(_blog(SLOP), _blog(CLEAN)) == ""


def test_consistency_check_flags_a_dropped_source():
    before = _blog(SLOP)
    after = _blog(CLEAN)
    after.sources = []
    assert "dropped 1 source" in consistency_check(before, after)


def test_consistency_check_flags_big_length_change():
    before = _blog("word " * 100)
    after = _blog("word " * 20)
    assert "changed length" in consistency_check(before, after)


def test_content_helpers_cover_each_schema():
    assert "no-shows" in content_text(_blog("about no-shows"))
    li = LinkedInPost(hook="h", body=["b"], link_url="https://x.test")
    assert content_urls(li) == {"https://x.test"}


# ------------------------------------------------------------------- full review


def test_full_review_runs_the_four_step_chain():
    draft = _blog("Studies have shown no-shows fell 22% in one pilot.")
    final = _blog("One pilot cut no-shows 22%.")
    llm = FakeLLMProvider([
        sr(FactCheckReport(overall="pass")),
        sr(CritiqueReport(weak_spots=["generic opener"])),
        sr(final),   # editor
        sr(final),   # voice
    ])

    result = full_review(
        llm, None, draft=draft, schema=BlogContent, brief=BRIEF,
        project=type("P", (), {"name": "P", "audience": "owners", "tone": "warm"})(),
        doc_type="blog_post",
    )

    assert result.content.sections[0].body == "One pilot cut no-shows 22%."
    assert result.status == "reviewed"
    assert "critique flagged 1 weak spot" in result.notes
    assert [c.response_model for c in llm.calls] == [
        "FactCheckReport", "CritiqueReport", "BlogContent", "BlogContent",
    ]


def test_full_review_flags_when_voice_drops_a_source():
    draft = _blog("no-shows fell 22%")
    voiced = _blog("no-shows fell 22%")
    voiced.sources = []  # voice pass lost the citation
    llm = FakeLLMProvider([
        sr(FactCheckReport(overall="pass")), sr(CritiqueReport()), sr(draft), sr(voiced),
    ])
    result = full_review(
        llm, None, draft=draft, schema=BlogContent, brief=BRIEF,
        project=type("P", (), {"name": "P", "audience": "o", "tone": "w"})(), doc_type="blog_post",
    )
    assert result.status == "flagged" and "dropped 1 source" in result.notes


def test_light_review_is_voice_only():
    draft = _blog(SLOP)
    llm = FakeLLMProvider([sr(_blog(CLEAN))])
    result = light_review(llm, None, draft=draft, schema=BlogContent, doc_type="blog_post")
    assert result.status == "reviewed"
    assert [c.response_model for c in llm.calls] == ["BlogContent"]
