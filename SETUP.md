# Quick Setup Guide

## ✅ What's Been Configured

Your AI News Aggregator is set up to:
- ✅ Use **GPT-4o-mini** for cost-effective blog generation
- ✅ Research keywords first (tracked in `knowledge/keywords_tracker.json` to avoid repeating topics)
- ✅ Generate **GitHub Pages-ready** blog posts with Jekyll front matter
- ✅ Save posts to the `output/` folder in the project root
- ✅ Write in a **conversational, blog-style** tone
- ✅ Focus on **AI's impact on everyday life** for small/medium business owners

## 🚀 To Get Started

### 1. Create Your .env File

Copy `ENV_TEMPLATE.txt` to `.env` in the project root and fill in your keys:

```bash
cp ENV_TEMPLATE.txt .env
```

### 2. Add Your API Keys

Edit `.env`:
```
OPENAI_API_KEY=sk-your-actual-key-here
SERPER_API_KEY=your-serper-key-here
```

Get your keys from:
- OpenAI: https://platform.openai.com/api-keys
- Serper: https://serper.dev/api-key

### 3. Install Dependencies

```bash
pip install -e .
```

### 4. Run the Generator

Web interface (recommended):
```bash
python start_web.py
```
Then open http://localhost:8000.

Command line:
```bash
crewai run
```

### 5. Check Your Blog Post

Look in the `output/` folder:
```
output/2026-08-06-your-topic-blog-post.md
```

## 📝 What the Agents Do

### Keyword Researcher Agent (GPT-4o-mini)
- Checks `knowledge/keywords_tracker.json` to avoid repeating recent topics
- Finds trending, relevant keywords for the topic
- Updates `keywords_tracker.json` with the new keywords

### Researcher Agent (GPT-4o-mini)
- Searches for latest AI developments, guided by the keyword research
- Finds 5+ real-world examples
- Focuses on everyday life impact
- Gathers sources and references

### Blog Writer Agent (GPT-4o-mini)
- Writes 600-1000 word blog posts
- Conversational, friendly tone
- Includes Jekyll front matter
- Ready for GitHub Pages

## 💰 Cost Per Post

Approximately **$0.01-0.05** per blog post using GPT-4o-mini.

## 🎨 Blog Post Format

```markdown
---
title: "How AI is Transforming Your Daily Life"
date: 2026-08-06
categories: [AI, Technology, Everyday Life]
author: Steven Tikas
layout: post
---

Engaging introduction...

## Section 1
Content with real-world examples...

## Section 2
More practical applications...

## Conclusion
Key takeaways...
```

## 🔧 Customization

### Change the Default Topic
Edit `src/ai_news_aggregator/main.py`:
```python
DEFAULT_TOPIC = "Your custom topic here"
DEFAULT_SLUG = "Your custom topic here"
```

### Adjust Writing Style
Edit `src/ai_news_aggregator/config/agents.yaml`:
- Modify the `blog_writer` backstory
- Change the tone and style description

### Change Output Location
Edit `OUTPUT_DIR` in `src/ai_news_aggregator/main.py`, or pass `output_dir` to `run_pipeline()`.

## ✨ Next Steps

1. **Test it** - Generate your first blog post
2. **Review** - Check the quality in the `output/` folder
3. **Adjust** - Tweak agents/tasks if needed
4. **Publish** - Upload to GitHub Pages when ready

---

**Ready to generate your first blog post?** 🚀

```bash
python start_web.py
```
