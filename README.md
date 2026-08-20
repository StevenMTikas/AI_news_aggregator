---
title: AI News Aggregator
emoji: 📰
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# AI News Aggregator - Blog Post Generator

An AI-powered content generator that creates structured, ready-to-publish blog posts for any of
your own **projects** — each with its own audience, tone, and branding. Built with CrewAI and
powered by GPT-4o-mini.

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

The `crewai run` / `ai_news_aggregator` console scripts call
[`main.run()`](src/ai_news_aggregator/main.py), which now **requires a project slug** — there's
no way to pass one through those bare commands yet (tracked in
[future-ideas.md](future-ideas.md)), so run it directly instead:

```bash
python -c "from ai_news_aggregator.main import run; run('your-project-slug', 'Your topic here')"
```

### 3. Find Your Blog Post

The generated blog post will be saved to:
```
output/YYYY-MM-DD-[topic-slug]-blog-post.md
```

## 📝 Output Format

Each generation produces a structured object (title, hook, sections with optional pull-quotes,
key takeaways, an optional call to action, tags, and sources) — see the **Structured Output &
the API** section below. That structure is rendered to a Jekyll-ready `.md` file for `output/`,
using the selected project's author and category tags:

```markdown
---
title: "Your Blog Post Title"
date: 2026-08-14
categories: [Productivity, SaaS]
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
```

## 🤖 The AI Agents

### Keyword Researcher Agent
- **Model**: GPT-4o-mini
- **Role**: Finds relevant, trending keywords for the topic and the project's audience
- **Output**: Keyword research report used to guide the researcher and blog writer

### Researcher Agent
- **Model**: GPT-4o-mini
- **Role**: Finds latest developments and real-world applications relevant to the project's audience, guided by the keyword research

### Blog Writer Agent
- **Model**: GPT-4o-mini
- **Role**: Writes a structured post in the project's tone, for the project's audience, attributed to the project's author
- **Output**: A `BlogContent` object (see **Structured Output & the API** below) — not freeform markdown

All three agents are parameterized by the selected project — audience, tone, author, category
tags, and target word count come from the `ProjectProfile` you set up in `/admin`, not from
hardcoded text in the YAML config.

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
AI_news_aggregator/
├── app.py                           # FastAPI web application
├── start_web.py                     # Web server launcher
├── pyproject.toml                   # Project dependencies + pytest config
├── render.yaml                      # Render deployment config (installs via pyproject.toml)
├── Dockerfile                       # Container image (Cloud Run / HF Spaces)
├── .dockerignore                    # Files excluded from the Docker build
├── .env                             # Your API keys (create this)
├── ENV_TEMPLATE.txt                 # Template for .env
├── DEPLOYMENT.md                    # Render deployment guide
├── GOOGLE_CLOUD_RUN_DEPLOYMENT.md   # Google Cloud Run deployment guide (free, private)
├── HUGGINGFACE_DEPLOYMENT.md        # Hugging Face Spaces guide (requires paid PRO)
├── future-ideas.md                  # Features referenced in docs but not yet built
├── package.json                     # JS test tooling (vitest + jsdom)
├── vitest.config.js
├── static/                          # Web interface files
│   ├── index.html                   # Generator page (requires picking a project)
│   ├── admin.html                   # Project management dashboard
│   ├── style.css
│   ├── app.js
│   ├── admin.js
│   └── tests/                       # Vitest tests for app.js/admin.js
├── src/ai_news_aggregator/          # Core application
│   ├── main.py                      # Pipeline entry point (build_default_inputs, run_pipeline)
│   ├── cli.py                       # Command-line entry point
│   ├── crew.py                      # Agent and task definitions
│   ├── projects.py                  # ProjectProfile model + YAML-backed CRUD storage
│   ├── schemas.py                   # BlogContent/Section structured output models
│   ├── tools/                       # Custom CrewAI tools (currently empty)
│   └── config/
│       ├── agents.yaml              # Agent configurations
│       ├── tasks.yaml               # Task definitions
│       └── projects/                # One YAML file per project (created via /admin)
├── tests/                           # Pytest test suite
└── output/                          # Generated blog posts
    └── YYYY-MM-DD-[topic]-blog-post.md
```

## 🎨 Customization

### Change Audience, Tone, or Branding

These are per-project now, not hardcoded — create or edit a project in `/admin` (or via
`/api/projects`) rather than editing YAML.

### Change the Topic

For the web interface, just enter your topic in the form alongside your chosen project.

For the command line, pass a topic to `run()`, or edit the default in [`src/ai_news_aggregator/main.py`](src/ai_news_aggregator/main.py):

```python
DEFAULT_TOPIC = "Your custom topic here"
DEFAULT_SLUG = "Your custom topic here"
```

### Modify Agent Behavior at the Prompt Level

Edit the YAML files in `src/ai_news_aggregator/config/`:
- `agents.yaml` - Change agent roles, goals, and backstories (these reference `{audience}`,
  `{tone}`, `{project_name}`, etc. — keep every placeholder you use here in sync with the keys
  `build_default_inputs()` supplies, or CrewAI will raise a `ValueError` on generation)
- `tasks.yaml` - Modify task descriptions and expected outputs. `blog_writer_task` also declares
  `output_pydantic: BlogContent`, which forces its output into the schema in
  [`schemas.py`](src/ai_news_aggregator/schemas.py) — change the schema and this reference
  together if you need different output fields.

### Change the AI Model

Edit `agents.yaml` and change the `llm` field:
```yaml
llm: gpt-4o  # or gpt-4, gpt-3.5-turbo, etc.
```

## 📊 Example Output

The blog posts are designed to be:
- ✅ **Engaging** - Tone matched to the project (conversational, technical, playful, etc.)
- ✅ **Accessible** - Written for the project's specific audience
- ✅ **Practical** - Real-world examples and applications
- ✅ **Current** - Based on latest developments
- ✅ **Ready to Publish** - Jekyll `.md` file, plus structured JSON via the API

## 🧪 Running Tests

**Python** (`app.py`, `main.py`, `cli.py`, `crew.py`, `projects.py`):
```bash
pip install -e ".[test]"
pytest -v
```
Covers project CRUD, the CLI, output rendering/saving, the crew's YAML config (agents/tasks
build correctly and every `{placeholder}` interpolates — catches drift between `agents.yaml`/
`tasks.yaml` and `build_default_inputs()` without an LLM call), and all `app.py` endpoints —
everything mocked so it never makes real OpenAI/Serper calls.

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

### "No module named 'crewai'"
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

- [CrewAI Documentation](https://docs.crewai.com)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)

## 🌐 Deploy to Production

Ready to deploy your AI News Aggregator to the web? Three options:

### Google Cloud Run (free, private, recommended)
See the complete guide: **[GOOGLE_CLOUD_RUN_DEPLOYMENT.md](GOOGLE_CLOUD_RUN_DEPLOYMENT.md)**
1. Enable Cloud Run + Secret Manager on a GCP project (billing account required, won't be charged within the free tier)
2. Store your API keys in Secret Manager
3. `gcloud run deploy` using the repo's `Dockerfile` — deployed as private (IAM-authenticated) so only you can trigger generation
4. Access it via `gcloud run services proxy` or a granted Google identity

### Render (paid to avoid cold starts/suspension)
See the complete guide: **[DEPLOYMENT.md](DEPLOYMENT.md)**
1. Push to GitHub
2. Connect Render to your repository
3. Set environment variables
4. Deploy!

Your app will be live at: `https://your-app.onrender.com`

### Hugging Face Spaces (requires a paid PRO plan)
See the complete guide: **[HUGGINGFACE_DEPLOYMENT.md](HUGGINGFACE_DEPLOYMENT.md)**. Docker Spaces
now require Hugging Face PRO ($9/mo+) — no longer a free option, kept here for reference.

## 🎉 Next Steps

1. **Test locally** - Run the web interface with `python start_web.py`
2. **Generate content** - Create your first AI blog post
3. **Customize** - Adjust agents and tasks to match your style
4. **Deploy** - Follow [GOOGLE_CLOUD_RUN_DEPLOYMENT.md](GOOGLE_CLOUD_RUN_DEPLOYMENT.md) (free, private) or [DEPLOYMENT.md](DEPLOYMENT.md) (Render)
5. **Publish** - Share your AI-generated blog posts!

Curious what's planned but not built yet? See [future-ideas.md](future-ideas.md).

---

**Ready to get started?**
- 🌐 **Web Interface**: `python start_web.py` → http://localhost:8000 (create a project at `/admin` first)
- 💻 **Command Line**: `python -c "from ai_news_aggregator.main import run; run('your-project-slug')"`
- 🚀 **Deploy**: See [GOOGLE_CLOUD_RUN_DEPLOYMENT.md](GOOGLE_CLOUD_RUN_DEPLOYMENT.md)

