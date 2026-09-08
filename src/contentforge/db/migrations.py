"""Forward-only schema migrations, applied by ``db.migrate()``.

Each entry is ``(version, sql)``. ``PRAGMA user_version`` tracks what has been applied; on
connect, anything newer than the stored version runs in order inside one transaction.
"""

from __future__ import annotations

M001_INITIAL = """
CREATE TABLE project (
    slug              TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    audience          TEXT NOT NULL DEFAULT '',
    tone              TEXT NOT NULL DEFAULT '',
    category_tags     TEXT NOT NULL DEFAULT '[]',   -- json array
    author            TEXT NOT NULL DEFAULT '',
    target_word_count INTEGER NOT NULL DEFAULT 800,
    notes             TEXT,
    created_at        TEXT NOT NULL
);

-- project_slug is a soft reference (plain column + index), not a FK: runs, briefs and
-- documents outlive the project profile if it is deleted.
CREATE TABLE run (
    id            TEXT PRIMARY KEY,
    project_slug  TEXT,
    kind          TEXT NOT NULL,                 -- research | atomic | compilation
    status        TEXT NOT NULL DEFAULT 'pending',
    progress      INTEGER NOT NULL DEFAULT 0,
    message       TEXT NOT NULL DEFAULT '',
    topic         TEXT NOT NULL DEFAULT '',
    topic_slug    TEXT NOT NULL DEFAULT '',
    params        TEXT NOT NULL DEFAULT '{}',    -- json
    error         TEXT,
    cost_usd      REAL NOT NULL DEFAULT 0,
    search_calls  INTEGER NOT NULL DEFAULT 0,
    tokens_in     INTEGER NOT NULL DEFAULT 0,
    tokens_out    INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    finished_at   TEXT
);
CREATE INDEX idx_run_project ON run(project_slug, created_at DESC);

CREATE TABLE research_brief (
    id               TEXT PRIMARY KEY,
    run_id           TEXT REFERENCES run(id) ON DELETE SET NULL,
    project_slug     TEXT,
    topic            TEXT NOT NULL,
    normalized_topic TEXT NOT NULL,
    content_json     TEXT NOT NULL,              -- full ResearchBrief
    created_at       TEXT NOT NULL,
    expires_at       TEXT,
    superseded_by    TEXT REFERENCES research_brief(id) ON DELETE SET NULL
);
CREATE INDEX idx_brief_lookup ON research_brief(project_slug, normalized_topic);

CREATE TABLE document (
    id                    TEXT PRIMARY KEY,
    run_id                TEXT REFERENCES run(id) ON DELETE SET NULL,
    project_slug          TEXT,
    type                  TEXT NOT NULL,
    title                 TEXT NOT NULL DEFAULT '',
    content_json          TEXT NOT NULL,
    rendered_path         TEXT,
    rendered_format       TEXT,
    based_on_brief_ids    TEXT NOT NULL DEFAULT '[]',
    based_on_document_ids TEXT NOT NULL DEFAULT '[]',
    review_status         TEXT NOT NULL DEFAULT 'unreviewed',
    review_notes          TEXT NOT NULL DEFAULT '',
    created_at            TEXT NOT NULL
);
CREATE INDEX idx_document_project ON document(project_slug, created_at DESC);
CREATE INDEX idx_document_run ON document(run_id);

CREATE TABLE cost_event (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      TEXT REFERENCES run(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,                   -- llm | search | embedding
    provider    TEXT NOT NULL DEFAULT '',
    model       TEXT NOT NULL DEFAULT '',
    tokens_in   INTEGER NOT NULL DEFAULT 0,
    tokens_out  INTEGER NOT NULL DEFAULT 0,
    calls       INTEGER NOT NULL DEFAULT 1,
    usd         REAL NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX idx_cost_run ON cost_event(run_id);

CREATE TABLE serper_cache (
    key         TEXT PRIMARY KEY,
    query       TEXT NOT NULL,
    search_type TEXT NOT NULL,
    result_json TEXT NOT NULL,
    stored_at   TEXT NOT NULL
);
"""

M002_ENRICH = """
-- Project enrichment: voice + research strategy knobs (Phase 6).
ALTER TABLE project ADD COLUMN subject_focus    TEXT NOT NULL DEFAULT '';
ALTER TABLE project ADD COLUMN style_guide      TEXT NOT NULL DEFAULT '';
ALTER TABLE project ADD COLUMN banned_phrases   TEXT NOT NULL DEFAULT '[]';
ALTER TABLE project ADD COLUMN recency_days     INTEGER;
ALTER TABLE project ADD COLUMN min_sources      INTEGER NOT NULL DEFAULT 5;
ALTER TABLE project ADD COLUMN prefer_domains   TEXT NOT NULL DEFAULT '[]';
ALTER TABLE project ADD COLUMN exclude_domains  TEXT NOT NULL DEFAULT '[]';
ALTER TABLE project ADD COLUMN default_model    TEXT;
ALTER TABLE project ADD COLUMN length_overrides TEXT NOT NULL DEFAULT '{}';

-- One embedding vector per brief / document, stored as packed float32 bytes.
ALTER TABLE research_brief ADD COLUMN embedding BLOB;
ALTER TABLE document       ADD COLUMN embedding BLOB;

-- Sources broken out for retrieval and (Phase 7) per-claim credibility.
CREATE TABLE source (
    id           TEXT PRIMARY KEY,
    brief_id     TEXT REFERENCES research_brief(id) ON DELETE CASCADE,
    project_slug TEXT,
    url          TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    domain       TEXT NOT NULL DEFAULT '',
    published_at TEXT,
    takeaway     TEXT NOT NULL DEFAULT '',
    credibility  TEXT,
    created_at   TEXT NOT NULL
);
CREATE INDEX idx_source_brief ON source(brief_id);

-- Full-text (BM25) half of hybrid retrieval. Populated by the KnowledgeStore.
CREATE VIRTUAL TABLE brief_fts USING fts5(ref_id UNINDEXED, project_slug UNINDEXED, body);
CREATE VIRTUAL TABLE doc_fts   USING fts5(ref_id UNINDEXED, project_slug UNINDEXED, body);
"""

M003_BUDGET = """
-- Per-project spend caps (Phase 9). NULL = fall back to the env default.
ALTER TABLE project ADD COLUMN max_usd_per_run   REAL;
ALTER TABLE project ADD COLUMN max_search_calls  INTEGER;
"""

MIGRATIONS: list[tuple[int, str]] = [
    (1, M001_INITIAL),
    (2, M002_ENRICH),
    (3, M003_BUDGET),
]
