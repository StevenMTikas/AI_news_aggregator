# Changelog

## The rewrite — `ai_news_aggregator` → `contentforge`

A 10-phase rewrite (see [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md) for the full log). What
changed, at a glance:

### Architecture
- **CrewAI removed.** Orchestration is now plain Python: `providers/` protocols (LLM,
  embedding, search, renderer), a ~120-line `agent_loop`, and `pipelines/`. No `crew.py`, no
  `config/*.yaml`.
- **Research is a first-class, persisted artifact.** `research(topic) → ResearchBrief` runs
  once per topic and is cached per project; every artifact composes from that one brief, so
  a multi-format run pays for research once and re-running a topic is free.
- **SQLite (`data/app.db`)** replaces the YAML project files and the in-memory task dict:
  `project`, `run`, `research_brief`, `source`, `document`, `cost_event`, `serper_cache`,
  plus FTS5 tables. Forward-only migrations (`PRAGMA user_version`). `contentforge backup`.
- **Package + service renamed** `ai_news_aggregator` → `contentforge`. Render / Cloud Run /
  HF Spaces configs removed — it's a local-first single-operator tool.

### Capabilities
- **Multi-artifact atomic runs** — blog post + LinkedIn post + social thread + repurposed
  snippets + metadata, all from one brief.
- **Compilation runs** — assemble a newsletter (MD + HTML), podcast script, or guide (PDF)
  from several prior runs, no new research.
- **Review chain** on every draft — fact-check → audience critique → edit → a de-AI "voice"
  pass, with a non-LLM consistency check that the voice pass kept every fact and source.
- **Projects get smarter over time** — briefs and documents are embedded + FTS-indexed per
  project; new research is primed with what the project already established.
  `brief_updater_agent` re-researches a topic as a diff.
- **Per-project settings** — `subject_focus`, `style_guide`, `banned_phrases`, research
  strategy (recency / min sources / prefer / exclude domains), `default_model`,
  `length_overrides`, spend caps.

### Security & ops
- Opt-in API key (`CONTENTFORGE_API_KEY`) on the mutating/generating routes; rate limiter;
  CORS locked to configurable origins.
- Per-run spend caps (`CONTENTFORGE_MAX_USD_PER_RUN` / `max_search_calls`, env or per
  project) — a run that hits one finishes `partial` with completed artifacts kept.
- Cross-run Serper cache with TTL.

### Interfaces
- Web: reworked generate page (artifact picker, force-fresh, pre-commit research-status +
  spend line, SSE progress), a `/compile` page, a `/runs` history page with per-run cost
  breakdown and re-render.
- CLI: `contentforge` is now a `typer` app — `generate`, `compile`, `render`, `backup`,
  `project`, `runs`, `brief`.

### Tests
0 → 182 pytest (network-free) + 13 vitest.
