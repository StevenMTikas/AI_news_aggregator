# Architecture Rewrite — Master Plan (Final)

One combined plan covering the prompt-chain fixes **and** the full architecture upgrade, run
as a single campaign before any real projects are added.

Supersedes [PROMPT_CHAIN_IMPROVEMENT_PLAN.md](PROMPT_CHAIN_IMPROVEMENT_PLAN.md): that
document's Phase 1 becomes **Phase 1** here; its Phases 2–5 are absorbed into Phases 4, 7 and
8 (CrewAI is being removed, so its `crew.py` / `tasks.yaml` edits no longer apply).

---

## 1. Decisions (finalized)

| Topic | Decision |
|---|---|
| **Framework** | Remove CrewAI. Plain-Python orchestration: `providers/` + `agents/` + `pipelines/` + a ~120-line `agent_loop`. Delete `crew.py`, `config/agents.yaml`, `config/tasks.yaml`, and the `crewai*` deps. |
| **Package name** | `ai_news_aggregator` → **`contentforge`**. |
| **Persistence** | SQLite (`data/app.db`) as source of truth. Prior research and generated content persist per project and compound over time. |
| **Deploy** | **Local-first single process** (see §9.1). SQLite on local disk + a built-in backup command. Optional Docker image + persistent volume for a personal VPS. **Remove** `render.yaml`, `GOOGLE_CLOUD_RUN_DEPLOYMENT.md`, `HUGGINGFACE_DEPLOYMENT.md`, and the HF front-matter in `README.md` — ephemeral-disk hosting fights the whole design. |
| **Access model** | Single operator. One static API key guards mutating/generating endpoints; CORS locked to localhost. No accounts, no multi-tenancy. |
| **Output — atomic runs** | topic → one paid research pass → blog post + social thread + repurposed snippets, all from one fact-checked brief. |
| **Output — compilation runs** | Build the framework for all three long-form types and implement all three: **newsletter**, **podcast script** (script text only for now; renderer seam left for audio), **informative guide → PDF**. Chosen from a dropdown, with a control for how much prior content feeds in. |
| **PDF engine** | **WeasyPrint** (HTML/CSS → PDF). ReportLab noted as fallback if system libs are a problem. |
| **Retrieval ("smarter over time")** | **Hybrid retrieval from the start** — SQLite FTS5 (BM25 keyword) + embedding vector search (`text-embedding-3-small`, brute-force cosine over stored vectors), fused. Best long-term recall; the `KnowledgeStore` interface hides it so the impl can evolve (e.g. `sqlite-vec`) without touching callers. |
| **Primary surface** | Keep the FastAPI web UI as primary; CLI is a first-class equal. UI gets a real rework (§10). |
| **Agent roster** | Core 11 agents (§6), all built this campaign. `claims_extractor` is **merged into `fact_checker_agent`**. `audience_critic_agent` and `voice_agent` (de-AI / natural-voice rewrite) are their **own standalone agents**, not merged. |

---

## 2. Current state (verified in-repo)

- `src/ai_news_aggregator/`: `crew.py` (CrewAI `@CrewBase`, 3 agents, `Process.sequential`),
  `config/agents.yaml` + `config/tasks.yaml`, `main.py` (`run_pipeline` fuses kickoff + save),
  `projects.py` (YAML-file-per-project CRUD), `schemas.py` (`BlogContent`), `cli.py`,
  `tools/` (empty).
- `app.py`: FastAPI. In-memory `tasks: Dict[str, Dict]` job state. `/api/projects` CRUD with
  **no auth**. `allow_origins=["*"]`. `/api/generate` unthrottled. 1-second poll loop in
  `static/app.js`.
- `config/projects/` doesn't exist yet; **no projects committed** — clean moment to change
  shape.
- Deps: `crewai[tools]>=0.201.1` (installed `crewai 0.201.1` / `crewai-tools 0.76.0`).
- Tests: `tests/` (pytest, network-free, mocks the pipeline) + `static/tests/` (vitest).
- Deploy scaffolding: `render.yaml`, `Dockerfile` (port 7860, HF-style),
  `GOOGLE_CLOUD_RUN_DEPLOYMENT.md`, `HUGGINGFACE_DEPLOYMENT.md`, README HF front-matter.
- Known bugs from prior review: writer never receives the keyword report; renderer drops
  `meta_description` / `tags` / `sources`; garbled leftover prompt sentences; Serper cache is
  in-memory and per-run; no search budget cap.

---

## 3. Target architecture

```
Interfaces        FastAPI (web UI + JSON API)      ·      CLI (typer)
                          │  single API key · CORS → localhost
                          ▼
Orchestration     RunService
                  • create/track runs (status, cost, error) in SQLite
                  • research resolution: reuse a fresh brief or trigger research
                  • budget caps: max search calls / max $ per run → graceful partial output
                  • topic dedupe (normalized topic) · brief supersession
                          │
                          ▼
Pipelines (code)  research          → ResearchBrief   (expensive, persisted, TTL'd)
                  atomic            → Document[]       (blog_post · social_thread · repurpose)
                  compilation       → Document         (newsletter · podcast_script · guide/PDF)
                  each = ordered agent steps + input/output schema + renderer + strategy
                          │
                          ▼
Agents (code)     keyword · research · synthesis · fact_checker · editor · audience_critic ·
                  voice · metadata · brief_updater ·
                  {blog_writer · social_thread · repurpose · outline · longform_writer}
                  run by agent_loop(llm, agent, context, budget) → pydantic
                          │
                          ▼
Capabilities      LLMProvider        (OpenAIProvider; seam for Anthropic)
(protocols)       EmbeddingProvider  (OpenAIEmbeddingProvider)
                  SearchProvider     (SerperSearchProvider + persistent cache; NullSearchProvider)
                  Renderer           (JekyllMarkdown · SocialThread · Newsletter · PodcastScript · PDF)
                  KnowledgeStore     (hybrid per-project retrieval over prior briefs + documents)
                          │
                          ▼
Persistence       SQLite  data/app.db
                  project · run · research_brief · source · document · cost_event · serper_cache
                  + FTS5 index + embedding blobs
```

Design rules:

- **Research is separated from composition.** `research(topic, strategy) → ResearchBrief`
  runs once per topic and is cached; `compose(brief, project, corpus) → Document` is cheap,
  does no web search, reruns freely. Collapses Serper spend to one call-set per *topic*
  instead of per *artifact*; makes new formats nearly free; gives the fact-checker something
  concrete to verify against.
- **Code owns "how", the DB owns "what / voice".** Pipelines and prompts live in Python
  (versioned, testable). Per-project knobs — subject focus, style guide, banned phrases,
  research strategy — live in the DB, editable at runtime.
- **Every brief and document is retained and indexed per project.** That accumulating,
  searchable corpus is what makes a project "smarter" (§7).
- **Providers are protocols, not vendors.** Swapping Serper, or gpt-4o-mini for Claude, is a
  one-file change that never touches pipelines or agents.

---

## 4. Data model (SQLite)

Thin data-access layer (`db/` module, plain `sqlite3` + SQL). Schema versioned via
`schema.sql` + `PRAGMA user_version` + forward-only migration scripts. Timestamps UTC
ISO-8601. JSON columns for lists/dicts.

| Table | Key columns | Notes |
|---|---|---|
| `project` | `id`, `slug` (unique), `name`, `audience`, `author`, `subject_focus` (text — what the project is *about*; steers research + retrieval), `style_guide` (text), `banned_phrases` (json), `recency_days` (int), `min_sources` (int), `prefer_domains` (json), `exclude_domains` (json), `default_model`, `created_at` | Replaces `ProjectProfile` + the YAML files. `tone` / `category_tags` / `target_word_count` fold into `style_guide` and per-pipeline params. |
| `run` | `id`, `project_id`, `kind` (`research`\|`atomic`\|`compilation`), `status` (`pending`\|`running`\|`completed`\|`failed`\|`partial`), `topic`, `pipeline`, `params` (json), `error`, `cost_usd`, `search_calls`, `tokens_in`, `tokens_out`, `created_at`, `finished_at` | Replaces the in-memory `tasks` dict. Survives restart. |
| `research_brief` | `id`, `run_id`, `project_id`, `topic`, `normalized_topic`, `summary` (text), `key_findings` (json), `trends` (json), `audience_impact` (json), `keyword_report` (json), `embedding` (blob), `created_at`, `expires_at` (now + `recency_days`), `superseded_by` (nullable → newer brief id) | The reusable asset. Dedupe on `(project_id, normalized_topic)` where `expires_at > now AND superseded_by IS NULL`. |
| `source` | `id`, `brief_id`, `url`, `title`, `domain`, `published_at`, `takeaway` (one sentence), `snippet` (captured text used for verification), `embedding` (blob), `credibility` (nullable: `supported`\|`weak`\|`unsupported`) | Provenance for every claim. |
| `document` | `id`, `run_id`, `project_id`, `type` (`blog_post`\|`social_thread`\|`repurpose`\|`newsletter`\|`podcast_script`\|`guide`), `title`, `content_json`, `section_embeddings` (blob/json), `rendered_path`, `rendered_format`, `based_on_brief_ids` (json), `based_on_document_ids` (json), `review_status`, `review_notes` (text), `created_at` | Output. Re-render from `content_json` with no LLM/search calls. |
| `cost_event` | `id`, `run_id`, `kind` (`llm`\|`search`\|`embedding`), `provider`, `model`, `tokens_in`, `tokens_out`, `calls`, `usd`, `created_at` | Feeds the cost ledger (Phase 10). |
| `serper_cache` | `key` (hash of normalized query + type + n), `query`, `search_type`, `result_json`, `stored_at` | Cross-run Serper cache. TTL by `search_type` (24 h `news`, 7 d otherwise). |
| `brief_fts` / `doc_fts` | FTS5 virtual tables (BM25) over brief summaries + source takeaways + document text | Keyword half of hybrid retrieval; kept in sync by triggers. |

`data/` (db, rendered output, backups) is git-ignored. One-time importer folds any existing
`config/projects/*.yaml` into `project` (currently none).

---

## 5. The two pipeline tiers

### Tier 1 — Atomic run

**Input:** project · topic · artifact selection (blog post / social thread / repurpose
snippets) · `force_fresh_research` toggle.

1. `RunService.start_atomic(...)` → `run` (`kind=atomic`).
2. **Research resolution.** Look for a `research_brief` in this project with matching
   `normalized_topic`, not expired, not superseded. Hit → reuse. Miss (or `force_fresh`) →
   **research pipeline**:
   - `keyword_agent` — *no search tool.* Query variants / angles from the model +
     `project.subject_focus` + recent brief summaries (§7) → `KeywordReport`.
   - `research_agent` — `SearchProvider` tool, **budget-capped**, honours `recency_days`,
     `exclude_domains`, `prefer_domains`, `min_sources` → raw results + `SourceCandidate[]`.
   - `synthesis_agent` — no tool. Distils results → `ResearchBrief`. Persist brief + `source`
     rows; embed summary + takeaways.
3. **Fact-check the brief.** `fact_checker_agent` extracts the brief's atomic claims, checks
   each against its `source.snippet`, sets `source.credibility`, drops/flags `key_findings`
   with no `supported` source. Tiny optional search budget for spot-checks.
4. **Compose** each selected artifact (brief only, no web search):
   - blog post: `blog_writer_agent` → `BlogContent` draft → `editor_agent` (style guide,
     banned phrases, structure, word count, claim-to-brief check) → `audience_critic_agent`
     (reads as the target audience; flags confusion / unexplained jargon) → `editor_agent`
     applies critic + fact-check notes → `voice_agent` (sentence-level rewrite to strip
     AI-tell patterns — see §6) → final `BlogContent`.
   - social thread: `social_thread_agent` → `voice_agent` → `SocialThread`.
   - repurpose: `repurpose_agent` → `voice_agent` → `Snippet[]` (platform-tagged: X,
     LinkedIn, IG caption, newsletter blurb).
   - a cheap final consistency check confirms `voice_agent` dropped no claim or cited source.
   - `metadata_agent` → title options, `meta_description`, slug, tags, **internal-link
     suggestions** drawn from prior `document`s in the same project.
5. **Render** via each `Renderer`; write to `data/output/<project>/<date>-<slug>.<ext>`;
   persist `document` rows with `based_on_brief_ids`.
6. Record `cost_event`s; finalize `run` (`completed`, or `partial` if a cap tripped).

**Result:** one paid research pass → 3+ artifacts, all sharing one fact-checked brief, all
provenance-linked.

### Tier 2 — Compilation run

**Input:** project · long-form type (dropdown: newsletter / podcast script / guide-PDF) ·
corpus-scope control · optional framing angle.

**Corpus-scope control** ("how much previous content"), combinable:
- last *N* days, or
- last *N* runs, or
- explicit multi-select of prior runs / documents, plus
- optional tag / sub-topic filter.

1. `RunService.start_compilation(...)` → `run` (`kind=compilation`).
2. **Gather corpus.** Pull selected `research_brief` + `document` rows; add
   `KnowledgeStore.retrieve(project, angle, budget)` hits. Token-budget the context —
   summarise older items if the total is too large.
3. **Optional gap-research** (opt-in, capped): one small `research_agent` pass if the angle
   needs something absent from the corpus; persisted as its own brief.
4. **Compose:**
   - `outline_agent` → `Outline`, mapping each section to the corpus items that support it.
   - `longform_writer_agent` → the structured doc (`Newsletter` / `PodcastScript` / `Guide`),
     section by section against the outline.
   - `fact_checker_agent` + `audience_critic_agent` + `editor_agent` → every claim traces to
     the corpus; nothing asserted beyond the briefs; style enforced.
   - `voice_agent` → strips AI-tell patterns from the long-form draft; final consistency
     check confirms no claim/source was lost.
   - `metadata_agent` → title / description / internal links.
5. **Render:** newsletter → Markdown + HTML (email-ready); podcast script → Markdown with
   segment/speaker cues; guide → Markdown → **PDF** (WeasyPrint). Persist `document` with
   `based_on_document_ids` + `based_on_brief_ids`.
6. `cost_event`s; finalize.

**Result:** long-form assembled from already-paid-for research, citing exactly the prior work
you selected.

---

## 6. Agent roster (all built this campaign)

Each agent is `(name, system_prompt_template, model, tools, output_schema)`. Run by a shared
`agent_loop` doing the OpenAI tool-calling loop with `max_iterations` / `max_tool_calls`
caps, emitting `cost_event`s.

| # | Agent | Tools | Output | Role |
|---|---|---|---|---|
| 1 | `keyword_agent` | none | `KeywordReport` | Query / angle generation. gpt-4o-mini does this well without search — roughly halves search volume vs. today. |
| 2 | `research_agent` | `SearchProvider` | raw results + `SourceCandidate[]` | The only agent that spends search credits. Strategy-aware, budget-capped. |
| 3 | `synthesis_agent` | none | `ResearchBrief` | Raw results → deterministic structured brief. Re-synthesise without re-searching. |
| 4 | `fact_checker_agent` | optional tiny `SearchProvider` budget | `FactCheckReport` | **Extracts the atomic claims** from a brief or draft (merged-in `claims_extractor`), verifies each against its source snippet / the brief, assigns verdicts, removes or flags unsupported specifics. Runs on the brief once and on every composed draft. |
| 5 | `editor_agent` | none | corrected `Document` + `editor_notes` | Enforces `style_guide`, `banned_phrases`, tone, structure, word count, jargon. Applies critic + fact-check notes. Keeps the writer's draft as a sidecar. |
| 6 | `audience_critic_agent` | none | `CritiqueReport` | **Standalone.** Reads the near-final draft as the target audience; flags what's confusing, unexplained, or unconvincing. Output feeds `editor_agent`; never edits directly. |
| 7 | `voice_agent` | none | rewritten `Document` + `voice_notes` | **Standalone, own agent** (not folded into editor/critic — it's a rewrite pass with its own checklist, and the editor is already carrying style guide + claims + critic notes). Runs last in every compose flow. Sentence-level rewrite to remove AI-tell patterns: reflexive hedging, tricolons, "it's not just X — it's Y", "in today's landscape", hollow transitions, restated-summary sentences, uniform paragraph rhythm, em-dash overuse, "delve / tapestry / testament / underscore". Hard-constrained to **preserve every claim and cited source in meaning** — it rephrases, it does not add or drop facts; the §5 consistency check enforces this. `banned_phrases` (exact strings) stays the editor's job; this is stylistic pattern detection. |
| 8 | `metadata_agent` | none | `DocumentMetadata` | Titles, `meta_description`, slug, tags, and **internal-link suggestions** from prior project documents. Improves publishability and cross-linking of the growing corpus. |
| 9 | `brief_updater_agent` | `SearchProvider` (capped) | updated `ResearchBrief` (a diff) | Given an existing brief + a fresh capped search: what's new / changed / no longer true. The mechanism behind "the project gets smarter" — re-research a topic and build on what was known instead of starting over. Sets `superseded_by`. |
| 10 | `blog_writer_agent` / `social_thread_agent` / `repurpose_agent` | none | `BlogContent` / `SocialThread` / `Snippet[]` | Per-format writers, brief-only. |
| 11 | `outline_agent` + `longform_writer_agent` | none | `Outline` / `Newsletter`\|`PodcastScript`\|`Guide` | Long-form. Outline-first keeps compilations coherent and provenance-honest. |

---

## 7. "Projects get smarter over time"

All per-project:

1. **Retention.** Every `research_brief`, `source`, and `document` is kept, embedded, and
   FTS-indexed.
2. **`project.subject_focus`** (a paragraph on the project's domain) is injected into
   `keyword_agent`, `research_agent`, `synthesis_agent` so research stays on the project's
   beat.
3. **Context priming.** Before any new research the pipeline receives: the subject focus, the
   *K* most recent brief summaries, and `KnowledgeStore.retrieve(project, new_topic, budget)`
   hits. Agents are told: *"here is what this project already established — find what's new or
   changed, don't re-derive what's known."*
4. **Supersession.** A re-run on the same `normalized_topic` writes a new brief and links the
   old via `superseded_by`, giving each topic a time-series that feeds `brief_updater_agent`.
5. **`KnowledgeStore` — hybrid retrieval**
   (`retrieve(project_id, query, token_budget) -> list[Excerpt]`):
   - **Keyword channel:** FTS5 BM25 over brief summaries / source takeaways / document text.
   - **Semantic channel:** `text-embedding-3-small` on write; query embedding vs. stored
     vectors, brute-force cosine (fine for personal scale — thousands of rows, not millions).
   - **Fusion:** reciprocal-rank fusion of the two rankings, then trim to `token_budget`.
   - Interface hides all of it — swap to `sqlite-vec` / a local embedder later with no caller
     changes.

Net effect: Serper spend drops (known ground isn't re-searched), briefs compound, and
compilations get richer as the corpus grows.

---

## 8. Providers & the agent loop

- `LLMProvider.complete(messages, tools=None, response_model=None) -> LLMResult`
  (`.content`, `.tool_calls`, `.tokens_in/out`). `OpenAIProvider` wraps the OpenAI SDK's
  function-calling + structured output. Per-agent model override; `project.default_model`
  (closes future-ideas #6).
- `EmbeddingProvider.embed(texts) -> list[vector]` + token accounting.
  `OpenAIEmbeddingProvider` (`text-embedding-3-small`).
- `SearchProvider.search(query, search_type="search", recency_days=None) -> list[SearchResult]`.
  `SerperSearchProvider`:
  - normalises the query (lowercase, strip punctuation, sort tokens),
  - checks `serper_cache` (TTL by type),
  - on miss calls Serper, stores **non-empty** results only,
  - applies `exclude_domains` / `prefer_domains` post-filter,
  - increments a per-run counter the loop reads for the budget cap.
  `NullSearchProvider` returns fixtures for offline tests.
- `Renderer.render(document) -> RenderedArtifact(path, bytes, mime)` — one per output type.
- `agent_loop(llm, agent, context, budget)`:
  1. build messages from `agent.system_prompt_template.format(**context)` + context blocks,
  2. `llm.complete(..., tools=agent.tools, response_model=agent.output_schema)`,
  3. execute tool calls (respecting `budget.max_tool_calls` + per-run search cap), append
     results, loop,
  4. stop at final structured output or `budget.max_iterations`; emit `cost_event`s.

  ~120 lines — the entire replacement for CrewAI's orchestration for a typed linear/DAG
  chain.

---

## 9. Deployment, security & CLI

### 9.1 Deployment — local-first (my recommendation, with reasoning)

This is a single-operator tool that runs occasional batch jobs and accumulates a valuable,
long-lived knowledge base. It is not a public service and gains nothing from managed hosting
— which actively hurts here because Render free / Cloud Run / HF Spaces all have **ephemeral
disk**, and the entire "smarter over time" design depends on durable local state.

- **Primary mode:** run `uvicorn contentforge.web:app` on your own machine (or an always-on
  mini-PC / home server). `data/app.db` on local disk. Zero hosting cost, no cold starts, API
  keys never leave your machine.
- **Backups:** a `contentforge backup` CLI command — SQLite `.backup` into
  `data/backups/app-<timestamp>.db`, keeping the last *N*. Run it from a cron/Task Scheduler
  entry. (Optionally also copy `data/output/`.)
- **Optional remote:** keep a slim `Dockerfile` (normalise port 7860 → 8000, mount `/data` as
  a volume) for running on a personal VPS / Fly.io / Railway with a persistent volume — one
  instance, volume-backed. Documented as optional in a rewritten `DEPLOYMENT.md`.
- **Remove:** `render.yaml`, `GOOGLE_CLOUD_RUN_DEPLOYMENT.md`, `HUGGINGFACE_DEPLOYMENT.md`,
  README HF front-matter, `start_web.py`'s `input()` prompt (not usable headless).

### 9.2 Security (personal scale)

- **Auth.** One static key in env (`CONTENTFORGE_API_KEY`). A FastAPI dependency guards every
  mutating / generating route (`/api/generate`, `/api/compile`, all `/api/projects` writes,
  `/api/runs` mutations, `/api/briefs` mutations). Read-only `/health` stays open.
- **CORS.** `allow_origins` → `["http://localhost:8000"]`, env-configurable. Not `*`.
- **Rate limit.** In-process per-minute counter on `/api/generate` + `/api/compile` (closes
  future-ideas #2) — guards against a runaway script, enough for one user.
- **Budget caps.** Per-run `max_search_calls` and `max_usd` (env defaults, per-project
  override). Hard stop → run finishes `partial`, keeping completed artifacts, surfacing which
  step stopped.

### 9.3 CLI (`typer`)

`contentforge generate` (atomic) · `compile` (long-form) · `project [list|add|edit|rm]` ·
`runs [list|show]` · `brief [list|show|update]` · `render <document_id>` (re-render, no LLM) ·
`backup`. Closes future-ideas #7 and #8.

---

## 10. Web UI plan

Current UI: `index.html` (topic + project dropdown → progress poll), `admin.html` (project
CRUD). Keep vanilla JS but reorganise per-page; adopt **htmx** for the polling / run-history
fragments to delete most of the hand-rolled `fetch`/render code in `app.js`/`admin.js`.

New / reworked screens:

1. **Generate (atomic)** — topic field · artifact checkboxes (blog / thread / repurpose) ·
   `force fresh research` toggle. A **research-status line** before you commit: *"✓ fresh
   brief from 3 days ago will be reused — no search cost"* vs *"will run new research (~N
   Serper credits, ~$X)"*. Surfacing cost pre-commit is the single biggest UX win.
2. **Compile (long-form)** — new page. project → long-form type dropdown → **corpus picker**:
   a scrollable list of recent runs/documents with checkboxes, quick filters (last 7/30/90
   days, by tag), and a live *"12 briefs · ~8k tokens selected"* counter · optional angle
   field.
3. **Run history** — new page. Table: date · kind · topic · status · cost · artifacts. Row
   actions: open documents, **re-render**, **update research** (`brief_updater`) on research
   runs.
4. **Document view** — rendered preview · provenance panel (which briefs / sources / prior
   docs) · per-claim fact-check badges (`supported` / `weak` / `unsupported`) · download.
5. **Project editor** — grouped sections: *Identity* (name, audience, author, subject focus),
   *Voice* (style guide textarea, banned-phrases tag input), *Research strategy*
   (recency-days, min-sources, prefer/exclude-domains tag lists, default model). Autosave
   drafts.
6. **Cost widget** — small persistent "this project, this month: $X · N searches" header
   element, backed by `/api/costs`.

Tech changes: replace the 1 s poll loop with a Server-Sent Events endpoint
(`GET /api/runs/{id}/stream`) driven off the `run` table; all job state read from SQLite, not
the in-memory dict. Keep `static/tests/` (vitest) coverage for the new JS modules.

---

## 11. Phased execution

Each phase is independently shippable, ends with `pytest` green (network-free) and a manual
smoke run. Ordered so the risky middle (CrewAI removal, DB) has a correct reference output on
either side.

**Progress:** Phase 1 ✅ · Phase 2 ✅ · Phase 3 ✅ · Phase 4 → next.

### Phase 1 — Correct the current output (reference baseline) · ~45 min · ✅ done
Minimal slice of the old plan's Phase 1 — only what carries forward:
- `render_jekyll_markdown`: emit `meta_description`, `content.tags`, `content.sources` (write
  it clean — this logic becomes `JekyllMarkdownRenderer`).
- One-line fix: pass the keyword report into the writer's context, so the baseline is
  representative.
- **Characterization tests**: snapshot current `/api/generate` → `/api/result` shape and a
  rendered `.md` for a fixed fake result. These lock behaviour across the rewrite.
- Skip the `tasks.yaml` / `crew.py` context-vs-YAML cleanup — that code is deleted in Phase 4.

### Phase 2 — Rename the package · ~1 hr · ✅ done
`ai_news_aggregator` → `contentforge`. Mechanical: `src/contentforge/`, all imports,
`pyproject.toml` (`name`, scripts, drop `[tool.crewai]`), `app.py`, `Dockerfile` (port →
8000). **Delete** `render.yaml`, the two cloud deployment guides, README HF front-matter. Own
commit, no behaviour change.

### Phase 3 — Provider protocols + agent loop + schemas · ~half day · ✅ done
Shipped in `src/contentforge/`:
- `providers/base.py` — `LLMProvider`, `EmbeddingProvider`, `SearchProvider`, `SearchCache`,
  `Renderer` protocols + the data types that cross them (`LLMResult`, `ToolCall`, `ToolSpec`,
  `SearchResult`, `SearchBudget`, `RenderedArtifact`).
- `providers/openai_provider.py` — `OpenAIProvider` (chat + tool calls + structured output via
  `chat.completions.parse`), `OpenAIEmbeddingProvider`. Lazy client, no key needed to import.
- `providers/serper.py` — `SerperSearchProvider` (normalised-query cache, `SearchBudget`,
  recency→`tbs`, prefer/exclude domains, injectable transport), `NullSearchProvider`,
  `InMemorySearchCache`, `normalize_query`.
- `providers/fakes.py` — `FakeLLMProvider` (scripted turns, records calls), `FakeEmbeddingProvider`.
- `agents/base.py` — `Agent`, `Tool`, `AgentBudget`, `render_prompt`, `search_tool`.
- `agent_loop.py` — `run_agent(llm, agent, task, …)`: tool-calling loop with iteration /
  tool-call caps, emits LLM cost events. ~120 lines; the whole CrewAI replacement.
- `cost.py` — `CostEvent` / `CostLedger` with a per-model price table.
- `schemas.py` — added `KeywordReport`, `Source`, `KeywordCoverage`, `ResearchBrief`,
  `ClaimVerdict`, `FactCheckReport`, `CritiqueReport`, `DocumentMetadata` (shapes kept
  strict-structured-output-safe: no open-ended `dict` maps).

Deviations from the sketch above, both deliberate:
- The `serper_cache` **table** needs the DB, which lands in Phase 5. Phase 3 ships the
  `SearchCache` **protocol** + `InMemorySearchCache`; Phase 5 adds the SQLite impl behind the
  same interface.
- `agent_loop` records **LLM** cost only. Search-call cost is derived from
  `SearchBudget.calls_made` by the orchestrator so cache hits are never charged.

49 new tests, network-free (fakes + injected transport). Nothing wired into the app yet.

### Phase 4 — Replace CrewAI: research + blog pipelines · ~1–1.5 days
- `agents/`: `keyword`, `research`, `synthesis`, `blog_writer`, `editor`.
- `pipelines/research.py`, `pipelines/blog_post.py`.
- `RunService` (in-memory first — DB in Phase 5) producing a `BlogContent` through the new
  path; `JekyllMarkdownRenderer`.
- Delete `crew.py`, `config/agents.yaml`, `config/tasks.yaml`; drop `crewai*` from
  `pyproject.toml`.
- **Gate:** the new blog post for a fixed topic is qualitatively equivalent to the Phase 1
  baseline; full suite green with `crewai` uninstalled.

### Phase 5 — SQLite + persistent RunService · ~1–1.5 days
- `db/` module, `schema.sql`, migration runner.
- `project` table replaces the `projects.py` YAML CRUD (keep the function names / API shape;
  swap storage). One-time YAML importer.
- `run` table replaces the in-memory `tasks` dict; `/api/status` + `/api/result` read it;
  SSE stream endpoint.
- Persist `research_brief` + `source` + `document` + `cost_event`.
- **Research resolution:** reuse a fresh brief for `(project, normalized_topic)`.
- `contentforge backup` command.
- **Gate:** generate → restart process → run history + briefs still present; `render`
  re-produces the `.md` with no LLM/search calls.

### Phase 6 — Project enrichment + hybrid KnowledgeStore + brief_updater · ~1–1.5 days
- Extend `project`: `subject_focus`, `style_guide`, `banned_phrases`, `recency_days`,
  `min_sources`, `prefer_domains`, `exclude_domains`, `default_model` (+ admin UI / API /
  CLI).
- Embeddings on write; `brief_fts` / `doc_fts`; `KnowledgeStore` hybrid retrieval (FTS5 +
  cosine + RRF).
- Context priming in the research pipeline (§7.3); `brief_updater_agent` + `brief update`
  CLI / UI action.
- **Gate:** a second run on a related topic demonstrably references prior findings (inspect
  agent context + brief linkage).

### Phase 7 — Fact-checker, editor, critic, voice, metadata + multi-artifact atomic runs · ~2 days
- `fact_checker_agent` (with merged claim extraction) on briefs and drafts;
  `source.credibility` + `document.review_status` / `review_notes` populated.
- `audience_critic_agent` (standalone) + `voice_agent` (standalone, natural-voice rewrite,
  §6 #7) + `metadata_agent` wired into the compose flow, in that order, with the post-`voice`
  claim/source consistency check.
- `social_thread` + `repurpose` pipelines + agents + renderers.
- Atomic run emits blog + thread + snippets + metadata from one brief.
- Build a small **AI-tell regression fixture**: a few known-slop paragraphs + assertions that
  `voice_agent` removes the patterns without changing the fact set.
- **Gate:** one atomic run → all artifacts, all fact-checked and voice-passed, **zero** extra
  search calls for artifacts 2+.

### Phase 8 — Compilation runs (all three long-form formats) · ~2 days
- `outline_agent`, `longform_writer_agent`; `Newsletter`, `PodcastScript`, `Guide` schemas.
- Corpus-selection API + UI (dropdown + scope controls, §5 Tier 2).
- Renderers: newsletter (MD + HTML), podcast script (MD w/ cues), guide (**WeasyPrint PDF**).
- Provenance: `document.based_on_document_ids` / `based_on_brief_ids`.
- **Gate:** select 3 prior runs → newsletter citing only those briefs; podcast script renders
  with cues; PDF guide renders.

### Phase 9 — Web UI rework + auth + CLI · ~1.5–2 days
- API-key dependency; CORS lock; `/api/generate` + `/api/compile` rate limit.
- `typer` CLI (§9.3).
- Rebuild the six screens in §10; htmx for run-history/progress; SSE progress; vitest
  coverage for new JS.
- README rewrite; `DEPLOYMENT.md` → local-first + optional Docker/volume.

### Phase 10 — Cost ledger + polish · ~half day
- `/api/costs` + per-project / per-run rollups; the cost widget.
- `future-ideas.md`: close #1 (train/replay → runs + re-render + brief_updater), #2, #3, #4,
  #5, #6, #7, #8. Delete the dead `train`/`replay`/`test` entry points.
- Optional: swap brute-force cosine for `sqlite-vec` if the corpus has grown enough to matter.

**Rough total: ~12–16 working days.** Phases 1–2 are safe warm-ups; 4 and 5 carry the
structural risk; 7 and 8 deliver the new capabilities.

---

## 12. Cross-cutting concerns

- **Tests stay network-free.** `NullSearchProvider` + fake LLM + fake embedder + a `tmp_path`
  SQLite fixture. Every phase adds tests; Phase 1 characterization snapshots guard the
  rewrite.
- **Cost visibility from day one.** `cost_event` rows land in Phase 5, before the dashboard —
  query spend immediately.
- **Graceful degradation.** Budget cap hit → `run.status = partial`; keep completed
  artifacts; surface the stopping step.
- **`data/output/` files kept** for Jekyll convenience, but the DB is the source of truth;
  files are regenerable via `render`.
- **This worktree can't currently import `crewai`** (`appdirs` missing) — irrelevant after
  Phase 4; do Phases 1–3 in the real project venv.

---

## 13. What this closes from `future-ideas.md`

| # | Item | Addressed by |
|---|---|---|
| 1 | `train`/`replay`/`test` CLI | Replaced by `run` history + `render` + `brief_updater`. Dead entry points removed (Phase 10). |
| 2 | API rate limiting | Phase 9 |
| 3 | CORS narrowing | Phase 9 |
| 4 | Persistent task queue | Phase 5 (`run` table) |
| 5 | Response / generation caching | Phases 4 + 5 (Serper cache table + brief reuse) |
| 6 | Configurable model | Phases 3 / 6 (`project.default_model`, per-agent override) |
| 7 | CLI project selection / args | Phase 9 (`typer`) |
| 8 | CLI project management | Phase 9 (`project` subcommand) |
