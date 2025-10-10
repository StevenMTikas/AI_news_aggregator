# AI News Aggregator - Blog Post Generator

An AI-powered blog post generator that creates engaging, conversational articles about AI and its impact on everyday life. Built with CrewAI and powered by GPT-4o-mini.

## 🎯 What It Does

This project uses AI agents to:
1. **Research** the latest AI developments and their real-world applications
2. **Write** engaging blog posts formatted for GitHub Pages (Jekyll)
3. **Save** posts to the `output/` folder, ready for publishing

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd ai_news_aggregator
pip install -e .
```

### 2. Set Up API Key

Create a `.env` file in the `ai_news_aggregator/` directory:

```bash
cd ai_news_aggregator
cp .env.example .env
```

Edit `.env` and add your OpenAI API key:
```
OPENAI_API_KEY=your-actual-api-key-here
```

Get your API key from: https://platform.openai.com/api-keys

### 3. Run the Generator

```bash
cd ai_news_aggregator
crewai run
```

Or using Python directly:
```bash
cd ai_news_aggregator
python src/ai_news_aggregator/main.py
```

### 4. Find Your Blog Post

The generated blog post will be saved to:
```
output/YYYY-MM-DD-ai-blog-post.md
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
├── ai_news_aggregator/              # CrewAI project
│   ├── .env                         # Your API keys (create this)
│   ├── .env.example                 # Template for .env
│   ├── pyproject.toml               # Dependencies
│   ├── src/ai_news_aggregator/
│   │   ├── main.py                  # Entry point
│   │   ├── crew.py                  # Agent definitions
│   │   └── config/
│   │       ├── agents.yaml          # Agent configurations
│   │       └── tasks.yaml           # Task definitions
│   └── README.md                    # CrewAI documentation
└── output/                          # Generated blog posts (auto-created)
    └── YYYY-MM-DD-ai-blog-post.md
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

## 🎉 Next Steps

1. **Test the output** - Review the generated blog posts in the `output/` folder
2. **Customize** - Adjust agents and tasks to match your style
3. **Publish** - Upload blog posts to your GitHub Pages site
4. **Automate** - Set up scheduled runs to generate regular content

---

**Ready to generate your first AI blog post?** Just run `crewai run` from the `ai_news_aggregator/` directory! 🚀

