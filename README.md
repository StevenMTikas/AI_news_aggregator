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

An AI-powered blog post generator that creates engaging, conversational articles about AI and its impact on everyday life. Built with CrewAI and powered by GPT-4o-mini.

## 🎯 What It Does

This project uses AI agents to:
1. **Research** the latest AI developments and their real-world applications
2. **Write** engaging blog posts formatted for GitHub Pages (Jekyll)
3. **Save** posts to the `output/` folder, ready for publishing

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

### 4. Open Your Browser

Navigate to: **http://localhost:8000**

You'll see a beautiful web interface where you can:
- ✅ Enter your blog topic
- ✅ Watch real-time progress
- ✅ Download generated blog posts
- ✅ View blog content in your browser

---

## 🚀 Quick Start - Command Line

### 1. Install and Configure

Follow steps 1-2 from the Web Interface section above.

### 2. Run the Generator

```bash
crewai run
```

Or using Python directly:
```bash
python -m ai_news_aggregator.main
```

### 3. Find Your Blog Post

The generated blog post will be saved to:
```
output/YYYY-MM-DD-[topic-slug]-blog-post.md
```

## 📝 Output Format

Blog posts are formatted for GitHub Pages with Jekyll front matter:

```markdown
---
title: "Your Blog Post Title"
date: 2025-10-10
categories: [AI, Technology, Everyday Life]
author: AI News Aggregator
layout: post
---

Your engaging blog content here...
```

## 🤖 The AI Agents

### Keyword Researcher Agent
- **Model**: GPT-4o-mini
- **Role**: Finds relevant, trending keywords for the topic, checking `knowledge/keywords_tracker.json` to avoid duplicating recently covered topics
- **Output**: Keyword research report used to guide the researcher and blog writer

### Researcher Agent
- **Model**: GPT-4o-mini
- **Role**: Finds latest AI developments and real-world applications, guided by the keyword research
- **Focus**: How AI impacts everyday life (home, work, health, education)

### Blog Writer Agent
- **Model**: GPT-4o-mini
- **Role**: Creates engaging, conversational blog posts
- **Style**: Warm, friendly, accessible to non-technical readers
- **Length**: 600-1000 words

## 💰 Cost

Using GPT-4o-mini, each blog post costs approximately **$0.01-0.05** to generate.

## 📁 Project Structure

```
AI_news_aggregator/
├── app.py                           # FastAPI web application
├── start_web.py                     # Web server launcher
├── pyproject.toml                   # Project dependencies + pytest config
├── requirements.txt                 # Render deployment dependencies
├── render.yaml                      # Render deployment config
├── Dockerfile                       # Container image (Cloud Run / HF Spaces)
├── .dockerignore                    # Files excluded from the Docker build
├── .env                             # Your API keys (create this)
├── ENV_TEMPLATE.txt                 # Template for .env
├── DEPLOYMENT.md                    # Render deployment guide
├── GOOGLE_CLOUD_RUN_DEPLOYMENT.md   # Google Cloud Run deployment guide (free, private)
├── HUGGINGFACE_DEPLOYMENT.md        # Hugging Face Spaces guide (requires paid PRO)
├── future-ideas.md                  # Features referenced in docs but not yet built
├── static/                          # Web interface files
│   ├── index.html
│   ├── style.css
│   └── app.js
├── src/ai_news_aggregator/          # Core application
│   ├── main.py                      # Pipeline entry point (build_default_inputs, run_pipeline)
│   ├── cli.py                       # Command-line entry point
│   ├── crew.py                      # Agent and task definitions
│   ├── tools/                       # Custom CrewAI tools (currently empty)
│   └── config/
│       ├── agents.yaml              # Agent configurations
│       └── tasks.yaml               # Task definitions
├── tests/                           # Pytest test suite (test_main.py, test_app.py)
├── output/                          # Generated blog posts
│   └── YYYY-MM-DD-[topic]-blog-post.md
└── knowledge/                       # Keyword tracking
    └── keywords_tracker.json
```

## 🎨 Customization

### Change the Topic

For the web interface, just enter your topic in the form.

For the command line, pass a topic to `run()`, or edit the default in [`src/ai_news_aggregator/main.py`](src/ai_news_aggregator/main.py):

```python
DEFAULT_TOPIC = "Your custom topic here"
DEFAULT_SLUG = "Your custom topic here"
```

### Modify Agent Behavior

Edit the YAML files in `src/ai_news_aggregator/config/`:
- `agents.yaml` - Change agent roles, goals, and backstories
- `tasks.yaml` - Modify task descriptions and expected outputs

### Change the AI Model

Edit `agents.yaml` and change the `llm` field:
```yaml
llm: gpt-4o  # or gpt-4, gpt-3.5-turbo, etc.
```

## 📊 Example Output

The blog posts are designed to be:
- ✅ **Engaging** - Conversational tone, like talking to a friend
- ✅ **Accessible** - No technical jargon, easy to understand
- ✅ **Practical** - Real-world examples and applications
- ✅ **Current** - Based on latest developments
- ✅ **Ready to Publish** - Formatted for GitHub Pages

## 🧪 Running Tests

```bash
pip install -e ".[test]"
pytest -v
```

Covers the helper functions in `main.py` (topic slugging, output saving) and the FastAPI
endpoints in `app.py` (mocked so it never makes real OpenAI/Serper calls).

## 🔧 Troubleshooting

### "No module named 'crewai'"
```bash
pip install -e .
```

### "OpenAI API key not found"
Make sure you created a `.env` file in the project's root directory with your API key.

### "Permission denied" when creating output folder
The script will automatically create the `output/` folder in the root directory.

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
- 🌐 **Web Interface**: `python start_web.py` → http://localhost:8000
- 💻 **Command Line**: `crewai run`
- 🚀 **Deploy**: See [GOOGLE_CLOUD_RUN_DEPLOYMENT.md](GOOGLE_CLOUD_RUN_DEPLOYMENT.md)

