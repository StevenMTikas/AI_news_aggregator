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

MIGRATIONS: list[tuple[int, str]] = [
    (1, M001_INITIAL),
]
