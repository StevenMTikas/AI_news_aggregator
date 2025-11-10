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

### Researcher Agent
- **Model**: GPT-4o-mini
- **Role**: Finds latest AI developments and real-world applications
- **Focus**: How AI impacts everyday life (home, work, health, education)

### Blog Writer Agent
- **Model**: GPT-4o-mini
- **Role**: Creates engaging, conversational blog posts
- **Style**: Warm, friendly, accessible to non-technical readers
- **Length**: 800-1200 words

## 💰 Cost

Using GPT-4o-mini, each blog post costs approximately **$0.01-0.05** to generate.

## 📁 Project Structure

```
AI_news_aggregator/
├── app.py                           # FastAPI web application
├── start_web.py                     # Web server launcher
├── pyproject.toml                   # Project dependencies
├── requirements.txt                 # Render deployment dependencies
├── render.yaml                      # Render deployment config
├── .env                             # Your API keys (create this)
├── ENV_TEMPLATE.txt                 # Template for .env
├── static/                          # Web interface files
│   ├── index.html
│   ├── style.css
│   └── app.js
├── src/ai_news_aggregator/          # Core application
│   ├── main.py                      # Entry point
│   ├── crew.py                      # Agent definitions
│   └── config/
│       ├── agents.yaml              # Agent configurations
│       └── tasks.yaml               # Task definitions
├── output/                          # Generated blog posts
│   └── YYYY-MM-DD-[topic]-blog-post.md
└── knowledge/                       # Keyword tracking
    └── keywords_tracker.json
```

## 🎨 Customization

### Change the Topic

Edit `ai_news_aggregator/src/ai_news_aggregator/main.py`:

```python
inputs = {
    'topic': 'Your custom topic here',
    'current_year': str(now.year),
    'current_date_and_time': now.strftime('%Y-%m-%d %H:%M:%S')
}
```

### Modify Agent Behavior

Edit the YAML files in `ai_news_aggregator/src/ai_news_aggregator/config/`:
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

## 🔧 Troubleshooting

### "No module named 'crewai'"
```bash
cd ai_news_aggregator
pip install -e .
```

### "OpenAI API key not found"
Make sure you created `.env` file in `ai_news_aggregator/` directory with your API key.

### "Permission denied" when creating output folder
The script will automatically create the `output/` folder in the root directory.

## 📚 Learn More

- [CrewAI Documentation](https://docs.crewai.com)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [GitHub Pages Documentation](https://docs.github.com/en/pages)

## 🌐 Deploy to Production

Ready to deploy your AI News Aggregator to the web?

See the complete deployment guide: **[DEPLOYMENT.md](DEPLOYMENT.md)**

Deploy to Render in minutes:
1. Push to GitHub
2. Connect Render to your repository
3. Set environment variables
4. Deploy!

Your app will be live at: `https://your-app.onrender.com`

## 🎉 Next Steps

1. **Test locally** - Run the web interface with `python start_web.py`
2. **Generate content** - Create your first AI blog post
3. **Customize** - Adjust agents and tasks to match your style
4. **Deploy** - Follow the [DEPLOYMENT.md](DEPLOYMENT.md) guide
5. **Publish** - Share your AI-generated blog posts!

---

**Ready to get started?**
- 🌐 **Web Interface**: `python start_web.py` → http://localhost:8000
- 💻 **Command Line**: `crewai run`
- 🚀 **Deploy**: See [DEPLOYMENT.md](DEPLOYMENT.md)

