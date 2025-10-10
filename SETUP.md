# Quick Setup Guide

## ✅ What's Been Configured

Your AI News Aggregator is now set up to:
- ✅ Use **GPT-4o-mini** for cost-effective blog generation
- ✅ Generate **GitHub Pages-ready** blog posts with Jekyll front matter
- ✅ Save posts to `output/` folder in the root directory
- ✅ Write in a **conversational, blog-style** tone
- ✅ Focus on **AI's impact on everyday life**

## 🚀 To Get Started

### 1. Create Your .env File

```bash
cd ai_news_aggregator
cp .env.example .env
```

### 2. Add Your OpenAI API Key

Edit `ai_news_aggregator/.env`:
```
OPENAI_API_KEY=sk-your-actual-key-here
```

Get your key from: https://platform.openai.com/api-keys

### 3. Run the Generator

```bash
cd ai_news_aggregator
crewai run
```

### 4. Check Your Blog Post

Look in the `output/` folder:
```
output/2025-10-10-ai-blog-post.md
```

## 📝 What the Agents Do

### Researcher Agent (GPT-4o-mini)
- Searches for latest AI developments
- Finds 5+ real-world examples
- Focuses on everyday life impact
- Gathers sources and references

### Blog Writer Agent (GPT-4o-mini)
- Writes 800-1200 word blog posts
- Conversational, friendly tone
- Includes Jekyll front matter
- Ready for GitHub Pages

## 💰 Cost Per Post

Approximately **$0.01-0.05** per blog post using GPT-4o-mini.

## 🎨 Blog Post Format

```markdown
---
title: "How AI is Transforming Your Daily Life"
date: 2025-10-10
categories: [AI, Technology, Everyday Life]
author: AI News Aggregator
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

### Change the Topic
Edit `ai_news_aggregator/src/ai_news_aggregator/main.py`:
```python
'topic': 'Your custom topic here'
```

### Adjust Writing Style
Edit `ai_news_aggregator/src/ai_news_aggregator/config/agents.yaml`:
- Modify the `blog_writer` backstory
- Change the tone and style description

### Change Output Location
Edit `ai_news_aggregator/src/ai_news_aggregator/crew.py`:
```python
output_dir = 'your/custom/path'
```

## ✨ Next Steps

1. **Test it** - Generate your first blog post
2. **Review** - Check the quality in the `output/` folder
3. **Adjust** - Tweak agents/tasks if needed
4. **Publish** - Upload to GitHub Pages when ready

---

**Ready to generate your first blog post?** 🚀

```bash
cd ai_news_aggregator
crewai run
```

