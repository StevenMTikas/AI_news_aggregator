from src.contentforge.db import briefs, connection, documents
from src.contentforge.knowledge import KnowledgeStore, format_priming
from src.contentforge.providers.fakes import FakeEmbeddingProvider
from src.contentforge.schemas import BlogContent, ResearchBrief, Section, Source


def _brief(topic, summary, findings) -> ResearchBrief:
    return ResearchBrief(
        topic=topic, summary=summary, key_findings=findings,
        sources=[Source(url="https://x.test", takeaway=f"evidence for {topic}")],
    )


def _index_brief(store, topic, summary, findings, slug="p"):
    b = _brief(topic, summary, findings)
    bid = briefs.save_brief(b, project_slug=slug, normalized_topic=topic.lower())
    store.index_brief(bid, slug, b)
    return bid


# ------------------------------------------------------------------ retrieval


def test_fts_only_retrieval_without_embedder():
    store = KnowledgeStore()  # no embedder
    _index_brief(store, "AI reservations", "Booking tools cut no-shows", ["No-shows down 20%"])
    _index_brief(store, "Solar panels", "Rooftop solar economics", ["Payback under 7 years"])

    hits = store.retrieve("p", "restaurant booking no-shows")
    assert hits and hits[0].title == "AI reservations"
    assert all(h.kind in {"brief", "document"} for h in hits)


def test_hybrid_retrieval_uses_both_channels():
    store = KnowledgeStore(embedder=FakeEmbeddingProvider())
    _index_brief(store, "AI reservations", "Booking software reduces empty tables", ["fewer no-shows"])
    _index_brief(store, "Kitchen inventory AI", "Forecasting covers to cut food waste", ["waste down 15%"])

    # a query that shares no exact words with either brief still retrieves via the vector channel
    hits = store.retrieve("p", "restaurant technology trends")
    assert len(hits) >= 1


def test_retrieval_is_scoped_to_project():
    store = KnowledgeStore()
    _index_brief(store, "AI reservations", "s", ["f"], slug="alpha")
    assert store.retrieve("beta", "AI reservations") == []


def test_retrieval_respects_token_budget():
    store = KnowledgeStore()
    for i in range(6):
        _index_brief(store, f"Topic {i}", "long summary " * 50, ["finding " * 20])
    hits = store.retrieve("p", "topic summary finding", k=6, token_budget=200)
    assert 1 <= len(hits) <= 3  # budget trims the list


def test_indexes_documents_too():
    store = KnowledgeStore()
    doc_id = documents.save_document(
        project_slug="p", doc_type="blog_post", title="Reservations, Reinvented",
        content_json=BlogContent(
            title="Reservations, Reinvented", meta_description="m", hook="h",
            sections=[Section(heading="Bookings", body="AI predicts no-shows")],
            key_points=["fewer empty tables"], tags=[], sources=[],
        ).model_dump_json(),
    )
    store.index_document(doc_id, "p", BlogContent.model_validate_json(
        documents.get_document(doc_id).content_json
    ))
    hits = store.retrieve("p", "no-shows bookings")
    assert any(h.kind == "document" and h.ref_id == doc_id for h in hits)


def test_recent_brief_summaries_skips_superseded():
    store = KnowledgeStore()
    old = _index_brief(store, "AI reservations", "old summary", ["old"])
    new = _index_brief(store, "AI reservations", "new summary", ["new"])
    briefs.supersede(old, new)

    summaries = store.recent_brief_summaries("p")
    assert any("new summary" in s for s in summaries)
    assert not any("old summary" in s for s in summaries)


def test_bad_fts_query_does_not_raise():
    store = KnowledgeStore()
    _index_brief(store, "AI reservations", "s", ["f"])
    assert isinstance(store.retrieve("p", 'AND OR "unbalanced'), list)


# ------------------------------------------------------------------- priming


def test_format_priming_assembles_block():
    from src.contentforge.knowledge import Excerpt

    text = format_priming(
        "restaurant technology for independent operators",
        ["AI reservations: booking tools cut no-shows"],
        [Excerpt("brief", "b1", "Kitchen AI", "Forecasting cuts waste 15%", "2026-01-01")],
    )
    assert "Project focus: restaurant technology" in text
    assert "Recent briefs on this beat:" in text
    assert "Kitchen AI" in text


def test_format_priming_empty_when_nothing_known():
    assert format_priming("", [], []) == ""


def test_embedding_stored_on_brief():
    store = KnowledgeStore(embedder=FakeEmbeddingProvider())
    bid = _index_brief(store, "AI reservations", "s", ["f"])
    with connection() as conn:
        blob = conn.execute("SELECT embedding FROM research_brief WHERE id = ?", (bid,)).fetchone()[0]
    assert blob is not None and len(blob) > 0
