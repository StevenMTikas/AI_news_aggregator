from datetime import datetime, timedelta, timezone

import pytest

from src.contentforge import db
from src.contentforge.cost import CostLedger
from src.contentforge.db import briefs, costs, documents, runs
from src.contentforge.db.backup import backup_database
from src.contentforge.db.search_cache import SqliteSearchCache
from src.contentforge.providers.base import SearchResult
from src.contentforge.schemas import ResearchBrief, Source


def test_migrations_applied():
    from src.contentforge.db.migrations import MIGRATIONS

    with db.connection() as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == MIGRATIONS[-1][0]
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cols = {r[1] for r in conn.execute("PRAGMA table_info(project)")}
    assert {"project", "run", "research_brief", "document", "cost_event", "serper_cache", "source"} <= tables
    assert {"subject_focus", "style_guide", "banned_phrases", "exclude_domains", "length_overrides"} <= cols


# ------------------------------------------------------------------------ runs


def test_run_lifecycle_and_persistence():
    run = runs.create_run(project_slug="p", topic="AI stuff", kind="atomic")
    assert run.status == "pending"

    runs.update_run(run.id, status="running", progress=40)
    runs.update_run(run.id, status="completed", progress=100, cost_usd=0.12)

    # a fresh connection (== "after restart") still sees it
    db.reset_migration_cache()
    reloaded = runs.get_run(run.id)
    assert reloaded.status == "completed" and reloaded.cost_usd == 0.12
    assert reloaded.finished_at is not None
    assert runs.count_active() == 0


def test_list_runs_filters_by_project():
    runs.create_run(project_slug="a", topic="t1")
    runs.create_run(project_slug="b", topic="t2")
    assert {r.project_slug for r in runs.list_runs(project_slug="a")} == {"a"}


# ---------------------------------------------------------------------- briefs


def _brief() -> ResearchBrief:
    return ResearchBrief(topic="AI reservations", summary="s",
                         sources=[Source(url="https://x.test", takeaway="t")])


def test_brief_reuse_and_ttl():
    bid = briefs.save_brief(_brief(), project_slug="p", normalized_topic="ai reservations", ttl_days=7)
    hit = briefs.find_fresh_brief("p", "ai reservations")
    assert hit is not None and hit.id == bid and hit.brief.topic == "AI reservations"

    assert briefs.find_fresh_brief("p", "different topic") is None
    assert briefs.find_fresh_brief("other-project", "ai reservations") is None


def test_expired_brief_not_reused():
    bid = briefs.save_brief(_brief(), project_slug="p", normalized_topic="topic", ttl_days=7)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
    with db.connection() as conn:
        conn.execute("UPDATE research_brief SET expires_at = ? WHERE id = ?", (past, bid))
    assert briefs.find_fresh_brief("p", "topic") is None


def test_superseded_brief_not_reused():
    old = briefs.save_brief(_brief(), project_slug="p", normalized_topic="topic")
    new = briefs.save_brief(_brief(), project_slug="p", normalized_topic="topic")
    briefs.supersede(old, new)
    hit = briefs.find_fresh_brief("p", "topic")
    assert hit.id == new


# ------------------------------------------------------------------- documents


def test_document_round_trip():
    doc_id = documents.save_document(
        project_slug="p", doc_type="blog_post", title="T", content_json='{"a":1}',
        based_on_brief_ids=["b1"],
    )
    stored = documents.get_document(doc_id)
    assert stored.title == "T" and stored.based_on_brief_ids == ["b1"]

    documents.set_rendered_path(doc_id, "/out/t.md", "markdown")
    assert documents.get_document(doc_id).rendered_path == "/out/t.md"


# ----------------------------------------------------------------------- costs


def test_cost_ledger_persists_and_rolls_up():
    run = runs.create_run(project_slug="p", topic="t")
    ledger = CostLedger()
    ledger.record_llm("openai", "gpt-4o-mini", 1000, 400)
    ledger.record_llm("openai", "gpt-4o-mini", 500, 100)
    ledger.record_search("serper", calls=2)
    costs.save_ledger(run.id, ledger)

    totals = costs.run_totals(run.id)
    assert totals["tokens_in"] == 1500 and totals["search_calls"] == 2 and totals["usd"] > 0
    assert costs.project_totals("p")["runs"] == 1

    bd = costs.run_breakdown(run.id)
    kinds = {b["kind"] for b in bd}
    assert kinds == {"llm", "search"}
    llm_row = next(b for b in bd if b["kind"] == "llm")
    assert llm_row["tokens_in"] == 1500 and llm_row["calls"] == 2  # two turns aggregated


# --------------------------------------------------------------- search cache


def test_sqlite_search_cache_round_trip_and_empty_skip():
    cache = SqliteSearchCache()
    cache.put("organic:8:ai tools", [SearchResult(title="R", url="https://x.test", snippet="s")])
    hit = cache.get("organic:8:ai tools")
    assert hit and hit[0].url == "https://x.test"

    cache.put("organic:8:empty", [])
    assert cache.get("organic:8:empty") is None


def test_sqlite_search_cache_ttl_expires_news_fast():
    cache = SqliteSearchCache()
    cache.put("news:8:headline", [SearchResult(title="R", url="https://x.test")])
    stale = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(timespec="seconds")
    with db.connection() as conn:
        conn.execute("UPDATE serper_cache SET stored_at = ? WHERE key = 'news:8:headline'", (stale,))
    assert cache.get("news:8:headline") is None


# ---------------------------------------------------------------------- backup


def test_backup_writes_snapshot(tmp_path):
    runs.create_run(project_slug="p", topic="t")
    dest = backup_database(dest_dir=tmp_path / "backups", keep=3)
    assert dest.exists() and dest.suffix == ".db"


def test_backup_without_db_raises(tmp_path):
    db.set_db_path(tmp_path / "missing.db")
    db.reset_migration_cache()
    with pytest.raises(FileNotFoundError):
        backup_database()
