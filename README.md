# ContentForge

A single-operator content engine. Research a topic once, then compose many artifacts from that
one saved brief — blog post, LinkedIn post, social thread, repurposed snippets — and later
assemble a newsletter, podcast script, or PDF guide from several past runs. Plain Python on the
OpenAI API + Serper; SQLite for everything it remembers. Built over the plan in
[ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md).

## 🎯 How it works

1. **Research** — keyword → web research → synthesis → fact-check, producing a `ResearchBrief`
   that is cached per project (so re-running a topic is free, and each project gets "smarter"
   as its research corpus grows).
2. **Compose** — each artifact composes from that brief. Blog and LinkedIn run a full review
   chain (fact-check → audience critique → edit → de-AI voice pass); thread and repurpose run
   a lighter voice-only pass.
3. **Render** — blog to Jekyll Markdown, LinkedIn/thread to plain text, guide to PDF, etc.
   Files land in `data/output/`; the structured content, run history, and cost ledger are in
   `data/app.db`.

Everything is organized around **projects** — a reusable profile (audience, voice/style guide,
banned phrases, research strategy, subject focus) you set up once and select each run.

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Set Up Environment Variables

Copy `ENV_TEMPLATE.txt` to `.env` and fill in:

```bash
OPENAI_API_KEY=your-actual-api-key-here   # https://platform.openai.com/api-keys
SERPER_API_KEY=your-actual-serper-key-here # https://serper.dev/api-key (free tier)
```

Optional, all documented in `ENV_TEMPLATE.txt`: `CONTENTFORGE_API_KEY` (locks the
mutating/generating routes behind an `X-API-Key` header; unset = open, for local use),
`CONTENTFORGE_MAX_USD_PER_RUN` / `CONTENTFORGE_MAX_SEARCH_CALLS` (spend caps — a run that hits
one finishes `partial` with whatever completed), `CONTENTFORGE_RATE_LIMIT_PER_MIN`,
`CONTENTFORGE_CORS_ORIGINS`, `CONTENTFORGE_DB`.

### 3. Start the Web Server

```bash
python start_web.py
```

### 4. Create a Project

Open **http://localhost:8000/admin** and create at least one project (audience, tone, category
tags, author, target word count). Generation requires selecting a project — there's no more
generic fallback.

### 5. Use it

| Page | What it's for |
|---|---|
| `/` | Generate — pick a project + topic, choose artifacts (blog / LinkedIn / thread / repurpose), watch progress |
| `/compile` | Assemble a newsletter / podcast script / guide-PDF from prior runs |
| `/runs` | Run history + cost, re-render a document, open past output |
| `/admin` | Create and edit projects |

Generated files land in `data/output/`; everything else (projects, run history, cached
research, cost ledger) is in `data/app.db`.

---

## 🚀 Command Line

```bash
contentforge project add mysite --name "My Site" --audience "..." --author "Me"
contentforge generate mysite "AI tools for small teams" -a blog_post -a linkedin_post
contentforge compile mysite newsletter --last-runs 5 --angle "what changed this month"
contentforge runs list --project mysite
contentforge brief list --project mysite
contentforge brief update <brief-id>          # re-research against the existing brief
contentforge render <document-id>             # re-render a stored doc, no LLM/search
contentforge backup                           # snapshot data/app.db
```

`contentforge --help` lists everything.

## 📝 Output Format

Each generation produces a structured object (title, meta description, hook, sections with
optional pull-quotes, key takeaways, an optional call to action, tags, and sources) — see the
**Structured Output & the API** section below. That structure is rendered to a Jekyll-ready
`.md` file for `data/output/`. Front matter carries the post's meta description and keyword-derived
`tags`; `categories` comes from the selected project's `category_tags`, and `author` from the
project:

```markdown
---
title: "Your Blog Post Title"
description: "The ~150-character meta description, reused as an SEO/social summary."
date: 2026-08-14
categories: [Productivity, SaaS]
tags: [ai keyword, long-tail phrase, related term]
author: Jane Doe
layout: post
---

Your engaging hook sentence...

## Section Heading
Section body...

> An optional pull-quote lifted from this section.

## Key Takeaways

- Key point one
- Key point two

## Sources

- https://example.com/article
```

(The `## Sources` section is omitted when the research returned no sources.)

## 🤖 The AI Agents

Defined in [`src/contentforge/agents/library.py`](src/contentforge/agents/library.py) as
prompt + output-schema pairs, run by a small tool-calling loop
([`agent_loop.py`](src/contentforge/agent_loop.py)). All use GPT-4o-mini.

| Agent | Tool | Output | Role |
|---|---|---|---|
| `keyword_agent` | — | `KeywordReport` | Generates the primary/long-tail/trending keyword set for the topic and audience (no search). |
| `research_agent` | web search | `ResearchNotes` | Searches for current, sourced information tied to the primary keywords. The only agent that spends search credits. |
| `synthesis_agent` | — | `ResearchBrief` | Distils the notes into a clean, source-backed brief. |
| `blog_writer_agent` / `linkedin_writer_agent` / `social_thread_agent` / `repurpose_agent` | — | `BlogContent` / `LinkedInPost` / `SocialThread` / `RepurposePack` | Per-format writers, each composing directly from the brief. |
| `fact_checker_agent` | (optional) web search | `FactCheckReport` | Extracts the atomic claims from a brief or draft and checks each against the research; flags what's unsupported. |
| `audience_critic_agent` | — | `CritiqueReport` | Reads the draft as the target audience; flags what's confusing or unconvincing (never edits). |
| `editor_agent` | — | same schema | Applies the fact-check and critique notes, enforces the style guide and banned phrases. |
| `voice_agent` | — | same schema | Sentence-level rewrite to strip AI-tell patterns, constrained to keep every fact and source. |
| `metadata_agent` | — | `DocumentMetadata` | Title options, meta description, slug, tags, and internal-link suggestions from prior project pieces. |
| `brief_updater_agent` | web search | `ResearchBrief` | Re-researches a topic against its existing brief — keeps what holds, revises what changed, adds what's new. |
| `outline_agent` | — | `Outline` | Plans a long-form piece from a corpus of the project's prior work. |
| `{newsletter,podcast_script,guide}_writer_agent` | — | `Newsletter` / `PodcastScript` / `Guide` | Writes the long-form piece from the outline + corpus. |

Per-project settings (`/admin`): `default_model` overrides the model for every agent;
`max_usd_per_run` / `max_search_calls` cap spend.

The research pipeline (keyword → research → synthesis → brief fact-check) produces a
`ResearchBrief`. Each output artifact then composes from that one brief: blog and LinkedIn
run the full review chain (fact-check → critique → edit → voice), thread and repurpose run a
lighter voice-only pass. One atomic run can emit several artifacts (`artifacts` in the
generate request) plus a metadata document — with no extra research.

**Compilations** (`/compile`, `POST /api/compile`) go the other way: pick several prior runs
(or a recent window) and assemble a **newsletter** (Markdown + HTML), **podcast script**
(with segment cues), or **guide** (PDF) from that corpus — again with no new research. The
long-form piece records which briefs and documents it drew on.

Audience, tone, style guide, and length come from the selected project.

## 🗂️ Projects

A project is a reusable content profile:

| Field | Purpose |
|---|---|
| `slug` | Unique ID, set at creation, immutable |
| `name` | Display name |
| `audience` | Who the content is for, e.g. "solo developers evaluating dev tools" |
| `tone` | e.g. "conversational", "technical", "playful" |
| `category_tags` | Default categories/hashtags for this project |
| `author` | Attribution used in generated front matter |
| `target_word_count` | Approximate length to aim for |
| `notes` | Anything else worth steering the agents with |
| `subject_focus` | What this project is *about* — steers research and which prior work gets reused |
| `style_guide` | Free-text voice rules (more expressive than `tone`) |
| `banned_phrases` | Exact strings the editor strips out |
| `recency_days` | Research recency window (blank = no limit) |
| `min_sources` | Minimum distinct sources the researcher must find |
| `prefer_domains` / `exclude_domains` | Bias / drop specific sites in research results |
| `default_model` | Model override for this project |
| `length_overrides` | `{recipe: word_count}` per-format length tweaks |

Manage projects at **http://localhost:8000/admin** (list, create, edit, delete — deleting a
project only removes its profile, already-generated files are untouched). The same operations
are available as a JSON API at `/api/projects`.

### Getting smarter over time

Every research brief and generated document is kept and indexed per project (SQLite FTS5 +
embeddings). Before a new research pass, the pipeline is primed with the project's
`subject_focus`, recent brief summaries, and the most relevant prior findings — so it builds
on what the project already knows instead of starting over. `POST /api/briefs/{id}/update`
re-researches a topic against its existing brief (what's new / changed / gone) and supersedes
it.

## 🔌 The API

Full interactive docs are auto-generated at **`/docs`**. The main routes:

| Route | |
|---|---|
| `POST /api/generate` | start an atomic run (`{topic, project_slug, artifacts, force_fresh}`) |
| `POST /api/compile` | start a compilation (`{project_slug, longform_type, run_ids \| last_n_runs \| last_n_days, angle}`) |
| `GET /api/status/{id}` · `/stream` | run status (polling or SSE) |
| `GET /api/result/{id}` | the primary document's structured content once done |
| `GET /api/runs` · `/api/runs/{id}` · `/api/runs/{id}/documents` | run history + detail + cost breakdown |
| `POST /api/documents/{id}/render` | re-render a stored document (no LLM) |
| `POST /api/briefs/{id}/update` | re-research a brief |
| `GET /api/costs?project_slug=` | per-project spend rollup |
| `/api/projects` (CRUD) | project profiles |

With `CONTENTFORGE_API_KEY` set, the `POST`/`PUT`/`DELETE` routes require an `X-API-Key`
header; `GET` routes stay open.

## 💰 Cost

With GPT-4o-mini a blog post is a few cents; a multi-artifact run or a compilation more.
Every run's token/search spend is recorded and shown per project on `/runs`. Set
`CONTENTFORGE_MAX_USD_PER_RUN` (or per-project `max_usd_per_run`) to cap it — a run that hits
the cap finishes `partial` with whatever completed.

## 📁 Project Structure

```
contentforge/
├── app.py                     # FastAPI web application
├── start_web.py               # Web server launcher
├── pyproject.toml             # Project dependencies + pytest config
├── Dockerfile                 # Optional container image for a personal server (see DEPLOYMENT.md)
├── .dockerignore
├── .env                       # Your API keys (create this)
├── ENV_TEMPLATE.txt           # Template for .env
├── DEPLOYMENT.md              # How to run ContentForge (local-first)
├── ARCHITECTURE_PLAN.md       # design + the phased build log
├── CHANGELOG.md               # what changed from ai_news_aggregator
├── future-ideas.md            # ideas for later
├── package.json               # JS test tooling (vitest + jsdom)
├── vitest.config.js
├── static/                    # index / admin / compile / runs pages + vitest tests
├── src/contentforge/          # Core application
│   ├── main.py                # build_default_inputs, run_pipeline
│   ├── cli.py                 # typer CLI (+ the python -c run() shim)
│   ├── security.py            # API-key dependency, rate limiter, CORS origins
│   ├── run_service.py         # orchestration: research -> compose -> render -> write
│   ├── agent_loop.py          # the tool-calling loop that runs one agent
│   ├── cost.py                # token/search cost accounting + BudgetExceeded
│   ├── knowledge.py           # per-project hybrid retrieval (FTS5 + embeddings) + priming
│   ├── projects.py            # ProjectProfile model + SQLite-backed CRUD
│   ├── schemas.py             # structured-output models (BlogContent, ResearchBrief, ...)
│   ├── agents/                # Agent definitions (base + library)
│   ├── pipelines/             # research + blog/linkedin/social/compilation recipes + review chain
│   ├── providers/             # LLM / embedding / search protocols + OpenAI & Serper impls
│   ├── renderers/             # Jekyll (blog), LinkedIn, thread, repurpose, newsletter, podcast, guide-PDF
│   ├── corpus.py              # gather prior runs/briefs/documents for a compilation
│   └── db/                    # SQLite: migrations, runs, briefs, documents, sources, costs, backup
├── tests/                     # Pytest test suite
└── data/                      # git-ignored: app.db, output/, backups/
    ├── app.db
    └── output/YYYY-MM-DD-[topic]-blog-post.md
```

`data/` holds the SQLite database (projects, run history, cached research, generated
documents, cost ledger) and the rendered files. Back it up with
`python -m contentforge.db.backup`.

## 🎨 Customization

- **Voice / audience / research strategy** — per project, in `/admin` (or `PUT /api/projects/{slug}`).
- **Agent prompts** — [`src/contentforge/agents/library.py`](src/contentforge/agents/library.py);
  each is `Agent(name, system_prompt, output_schema, …)`. `{placeholders}` are filled from the
  pipeline context; unknown ones pass through.
- **Model** — `default_model` on the project (applies to every agent that run), or a per-agent
  `model=`.
- **Output shape** — the schemas in [`schemas.py`](src/contentforge/schemas.py); the model is
  forced to return them.
- **A new format** — add a schema, a `Pipeline`, and a `Renderer`; register it in
  `pipelines/COMPOSE_PIPELINES` and `renderers/DEFAULT_RENDERERS`.

## 🧪 Running Tests

```bash
pip install -e ".[test]" && pytest -q      # 182 tests, no network (fakes + injected transports)
npm install && npm test                    # 13 vitest, jsdom
```

## 🔧 Troubleshooting

| Symptom | Fix |
|---|---|
| `No module named 'openai'` / import errors | `pip install -e .` |
| `OPENAI_API_KEY … must be set` | create `.env` (copy `ENV_TEMPLATE.txt`) |
| No projects in the dropdown | create one at `/admin` first |
| A run finished `partial` | it hit `CONTENTFORGE_MAX_USD_PER_RUN` / `max_search_calls` — completed artifacts are kept |
| Nicer PDFs | `pip install -e ".[pdf]"` (WeasyPrint; needs system libs). Otherwise ReportLab is used. |

## 🌐 Running it beyond localhost

ContentForge keeps a growing local store, so it's built to run **locally** or on one
always-on machine you control — not on ephemeral-disk hosts. See
**[DEPLOYMENT.md](DEPLOYMENT.md)**. Set `CONTENTFORGE_API_KEY` before exposing it.

See [CHANGELOG.md](CHANGELOG.md) for what changed from the original `ai_news_aggregator`, and
[ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md) for the design.

