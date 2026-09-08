from src.contentforge.corpus import CorpusSelection, resolve_corpus
from src.contentforge.db import briefs, documents, runs
from src.contentforge.schemas import BlogContent, ResearchBrief, Section, Source


def _seed_run(topic, *, summary="s", url="https://ex.test/a", blog_title="A post") -> str:
    run = runs.create_run(project_slug="p", topic=topic, kind="atomic")
    runs.update_run(run.id, status="completed")
    briefs.save_brief(
        ResearchBrief(topic=topic, summary=summary, key_findings=[f"{topic} finding"],
                      sources=[Source(url=url, takeaway="t")]),
        project_slug="p", normalized_topic=topic.lower(), run_id=run.id,
    )
    documents.save_document(
        project_slug="p", doc_type="blog_post", title=blog_title, run_id=run.id,
        content_json=BlogContent(
            title=blog_title, meta_description="m", hook="h",
            sections=[Section(heading="H", body="body about " + topic)],
            key_points=["k"], tags=[], sources=[url],
        ).model_dump_json(),
    )
    return run.id


def test_resolve_corpus_by_explicit_run_ids():
    r1 = _seed_run("AI reservations", blog_title="Bookings post")
    r2 = _seed_run("AI inventory", blog_title="Inventory post")
    _seed_run("Unrelated", blog_title="Other post")

    corpus = resolve_corpus("p", CorpusSelection(run_ids=[r1, r2], include_retrieval=False))

    titles = {i.title for i in corpus.items}
    assert {"AI reservations", "AI inventory", "Bookings post", "Inventory post"} <= titles
    assert "Other post" not in titles
    assert len(corpus.brief_ids) == 2 and len(corpus.document_ids) == 2


def test_resolve_corpus_last_n_runs():
    _seed_run("one")
    _seed_run("two")
    _seed_run("three")
    corpus = resolve_corpus("p", CorpusSelection(last_n_runs=2, include_retrieval=False))
    topics = {i.title for i in corpus.items if i.kind == "brief"}
    assert topics == {"two", "three"}


def test_merged_brief_spans_the_corpus():
    r1 = _seed_run("AI reservations", summary="bookings", url="https://a.test")
    r2 = _seed_run("AI inventory", summary="inventory", url="https://b.test")
    corpus = resolve_corpus("p", CorpusSelection(run_ids=[r1, r2], include_retrieval=False))

    merged = corpus.merged_brief("Restaurant tech roundup")
    assert merged.topic == "Restaurant tech roundup"
    assert "AI reservations finding" in merged.key_findings
    assert {"https://a.test", "https://b.test"} <= {s.url for s in merged.sources}


def test_corpus_as_prompt_respects_budget():
    for i in range(5):
        _seed_run(f"topic {i}", summary="long " * 200)
    corpus = resolve_corpus("p", CorpusSelection(last_n_runs=5, include_retrieval=False))
    prompt = corpus.as_prompt(token_budget=150)
    assert "omitted for length" in prompt
