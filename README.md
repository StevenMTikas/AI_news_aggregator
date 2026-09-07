# ContentForge

An AI content generator that creates structured, ready-to-publish blog posts for any of your
own **projects** — each with its own audience, tone, and branding. Built in plain Python on the
OpenAI API (GPT-4o-mini). A larger rewrite adding persisted research, SQLite, and multi-format
output (LinkedIn, newsletter, podcast script, PDF guide) is in progress — see
[ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md); Phases 1–4 are done.

## 🎯 What It Does

This project uses AI agents to:
1. **Research** current developments, trends, and real-world examples for your topic
2. **Write** a structured post (title, hook, sections with pull-quotes, key takeaways, tags,
   sources) tailored to a specific project's audience and tone
3. **Save** a Jekyll-ready `.md` file to `output/`, and expose the full structured content over
   the API for other tools (e.g. a social-media repurposing tool) to consume

Content generation is organized around **projects** — reusable profiles (audience, tone,
category tags, author, target word count) you set up once via the admin dashboard and select
each time you generate content. This is what lets the same generator serve multiple unrelated
projects instead of always writing in one fixed voice.

## 🌐 Two Ways to Use

### Option 1: Web Interface (Recommended)
Beautiful, user-friendly web interface with real-time progress tracking.

### Option 2: Command Line
Direct command-line execution for automation and scripting.

## 🚀 Quick Start - Web Interface

### 1. Install Dependencies

```bash
pip install -e .
```

### 2. Set Up Environment Variables

Create a `.env` file in the root directory (see `ENV_TEMPLATE.txt`):

```bash
OPENAI_API_KEY=your-actual-api-key-here
SERPER_API_KEY=your-actual-serper-key-here
```

Get your API keys:
- **OpenAI**: https://platform.openai.com/api-keys
- **Serper**: https://serper.dev/api-key (free tier available)

### 3. Start the Web Server

```bash
python start_web.py
```

### 4. Create a Project

Open **http://localhost:8000/admin** and create at least one project (audience, tone, category
tags, author, target word count). Generation requires selecting a project — there's no more
generic fallback.

### 5. Generate Content

Navigate to: **http://localhost:8000**

- ✅ Pick your project
- ✅ Enter your blog topic
- ✅ Watch real-time progress
- ✅ Download generated blog posts
- ✅ View blog content in your browser

---

## 🚀 Quick Start - Command Line

### 1. Install, Configure, and Create a Project

Follow steps 1-2 and 4 from the Web Interface section above (a project must exist before you can
generate anything — creating one is currently only possible through `/admin` or the
`/api/projects` API, not the CLI).

### 2. Run the Generator

The `contentforge` console script calls [`main.run()`](src/contentforge/main.py), which
**requires a project slug** — there's no argument parsing on the bare command yet (a proper
CLI lands in Phase 9 of [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md)), so run it directly:

```bash
python -c "from contentforge.main import run; run('your-project-slug', 'Your topic here')"
```

### 3. Find Your Blog Post

The generated blog post will be saved to:
```
output/YYYY-MM-DD-[topic-slug]-blog-post.md
```

## 📝 Output Format

Each generation produces a structured object (title, meta description, hook, sections with
optional pull-quotes, key takeaways, an optional call to action, tags, and sources) — see the
**Structured Output & the API** section below. That structure is rendered to a Jekyll-ready
`.md` file for `output/`. Front matter carries the post's meta description and keyword-derived
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
| `blog_writer_agent` | — | `BlogContent` | Drafts the post from the brief, in the project's tone/audience/voice. |
| `editor_agent` | — | `BlogContent` | Checks claims against the brief, tightens length and structure, removes jargon. |

The research pipeline (keyword → research → synthesis) produces a `ResearchBrief`; the blog
pipeline (writer → editor) composes from it. Audience, tone, author, category tags, and word
count come from the selected project.

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

Manage projects at **http://localhost:8000/admin** (list, create, edit, delete — deleting a
project only removes its profile, already-generated `output/*.md` files are untouched). The same
operations are available as a JSON API at `/api/projects` if you want to manage projects
programmatically.

## 🔌 Structured Output & the API

Generation no longer returns freeform markdown from the API — `GET /api/result/{task_id}`
returns a typed `BlogContent` object:

```json
{
  "task_id": "...",
  "download_url": "/download/2026-08-14-my-post-blog-post.md",
  "content": {
    "title": "...",
    "meta_description": "...",
    "hook": "...",
    "sections": [{"heading": "...", "body": "...", "pull_quote": "..."}],
    "key_points": ["..."],
    "call_to_action": "...",
    "tags": ["..."],
    "sources": ["..."]
  }
}
```

This is meant to be consumed by other tools (e.g. something that chops a post into
platform-specific social posts) without having to re-parse markdown. Full interactive API docs,
including the project CRUD endpoints, are auto-generated by FastAPI at **`/docs`**.

## 💰 Cost

Using GPT-4o-mini, each blog post costs approximately **$0.01-0.05** to generate.

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
├── ARCHITECTURE_PLAN.md       # The in-progress rewrite plan
├── future-ideas.md            # Smaller gaps, most folded into ARCHITECTURE_PLAN.md
├── package.json               # JS test tooling (vitest + jsdom)
├── vitest.config.js
├── static/                    # Web interface files
│   ├── index.html             # Generator page (requires picking a project)
│   ├── admin.html             # Project management dashboard
│   ├── style.css
│   ├── app.js
│   ├── admin.js
│   └── tests/                 # Vitest tests for app.js/admin.js
├── src/contentforge/          # Core application
│   ├── main.py                # build_default_inputs, run_pipeline
│   ├── cli.py                 # command-line entry point
│   ├── run_service.py         # orchestration: research -> compose -> render -> write
│   ├── agent_loop.py          # the tool-calling loop that runs one agent
│   ├── cost.py                # token/search cost accounting
│   ├── projects.py            # ProjectProfile model + YAML-backed CRUD storage
│   ├── schemas.py             # structured-output models (BlogContent, ResearchBrief, ...)
│   ├── agents/                # Agent definitions (base + library) + tools
│   ├── pipelines/             # research pipeline + per-format compose recipes
│   ├── providers/             # LLM / embedding / search protocols + OpenAI & Serper impls
│   └── renderers/             # JekyllMarkdownRenderer (more formats coming)
├── tests/                     # Pytest test suite
└── output/                    # Generated blog posts
    └── YYYY-MM-DD-[topic]-blog-post.md
```

## 🎨 Customization

### Change Audience, Tone, or Branding

These are per-project now, not hardcoded — create or edit a project in `/admin` (or via
`/api/projects`) rather than editing YAML.

### Change the Topic

For the web interface, just enter your topic in the form alongside your chosen project.

For the command line, pass a topic to `run()`, or edit the default in [`src/contentforge/main.py`](src/contentforge/main.py):

```python
DEFAULT_TOPIC = "Your custom topic here"
DEFAULT_SLUG = "Your custom topic here"
```

### Modify Agent Behavior at the Prompt Level

Edit the agent definitions in
[`src/contentforge/agents/library.py`](src/contentforge/agents/library.py) — each is an
`Agent(name, system_prompt, output_schema, ...)`. `{placeholders}` in a prompt are filled
from the pipeline's context; unknown ones pass through untouched. The output schema (in
[`schemas.py`](src/contentforge/schemas.py)) is what the model is forced to return.

### Change the AI Model

Pass `default_model=` to `OpenAIProvider` (see
[`providers/openai_provider.py`](src/contentforge/providers/openai_provider.py)), or set a
per-agent `model=` on an `Agent`. A project-level default lands in a later phase.

## 📊 Example Output

The blog posts are designed to be:
- ✅ **Engaging** - Tone matched to the project (conversational, technical, playful, etc.)
- ✅ **Accessible** - Written for the project's specific audience
- ✅ **Practical** - Real-world examples and applications
- ✅ **Current** - Based on latest developments
- ✅ **Ready to Publish** - Jekyll `.md` file, plus structured JSON via the API

## 🧪 Running Tests

**Python:**
```bash
pip install -e ".[test]"
pytest -q
```
Covers project CRUD, the CLI, the provider protocols and agent loop, the research and blog
pipelines, the renderer, `RunService` orchestration (including brief reuse), and every
`app.py` endpoint — all against fakes and injected transports, so it never makes a real
OpenAI or Serper call.

**Frontend** (`static/app.js`, `static/admin.js`):
```bash
npm install
npm test
```
Covers the pure logic (topic-to-slug conversion, content preview rendering, HTML escaping) by
loading the real `index.html`/`admin.html` into jsdom, so a mismatched element ID would fail the
test too. The DOM-wiring/event-handling code itself isn't covered — that's verified manually in
a browser.

## 🔧 Troubleshooting

### "No module named 'openai'" / import errors
```bash
pip install -e .
```

### "OpenAI API key not found"
Make sure you created a `.env` file in the project's root directory with your API key.

### "Permission denied" when creating output folder
The script will automatically create the `output/` folder in the root directory.

### "Unknown project" / no projects in the dropdown
Generation requires an existing project. Create one at `/admin` first — the generator form will
show an error instead of a submittable form if none exist yet.

## 📚 Learn More

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)

## 🌐 Running It

ContentForge is a single-operator tool with a growing local store of research and content, so
it runs **locally** (or on one always-on machine you control), not on ephemeral-disk hosts.
See **[DEPLOYMENT.md](DEPLOYMENT.md)** for the local setup and the optional Docker path.

## 🎉 Next Steps

1. **Run locally** - `python start_web.py` → http://localhost:8000
2. **Generate content** - Create a project at `/admin`, then your first blog post
3. **Customize** - Adjust agents and tasks to match your style
4. **Publish** - Share your generated blog posts!

Curious where this is heading? See [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md); smaller gaps
are in [future-ideas.md](future-ideas.md).

---

**Ready to get started?**
- 🌐 **Web Interface**: `python start_web.py` → http://localhost:8000 (create a project at `/admin` first)
- 💻 **Command Line**: `python -c "from contentforge.main import run; run('your-project-slug')"`

