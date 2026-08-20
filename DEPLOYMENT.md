# 🚀 Deployment Guide for Render

This guide will walk you through deploying the AI News Aggregator to Render.

> If your Render account is suspended or you'd rather not pay to avoid cold starts, see
> [GOOGLE_CLOUD_RUN_DEPLOYMENT.md](GOOGLE_CLOUD_RUN_DEPLOYMENT.md) for a free, private
> alternative using the same `Dockerfile`.

## Prerequisites

Before deploying, make sure you have:

1. ✅ A [Render account](https://render.com) (free tier is sufficient)
2. ✅ An [OpenAI API key](https://platform.openai.com/api-keys)
3. ✅ A [Serper API key](https://serper.dev/api-key) (for Google search)
4. ✅ Your code pushed to a GitHub repository

## 📋 Pre-Deployment Checklist

### 1. Verify All Files Are Present

Make sure these files exist in your repository:
- ✅ `render.yaml` - Render configuration
- ✅ `pyproject.toml` - Project configuration and dependencies
- ✅ `app.py` - FastAPI application
- ✅ `static/` folder with `index.html`, `style.css`, `app.js`
- ✅ `src/ai_news_aggregator/` - Core application code

### 2. Check Your .gitignore

Ensure these are in your `.gitignore`:
```
.env
output/
__pycache__/
*.pyc
```

### 3. Verify Environment Variables Template

Review `ENV_TEMPLATE.txt` to understand what environment variables you'll need to set in Render.

## 🌐 Deployment Steps

### Step 1: Push to GitHub

```bash
# If you haven't initialized git yet
git init
git add .
git commit -m "Prepare for Render deployment"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### Step 2: Connect Render to GitHub

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **"New +"** → **"Blueprint"**
3. Connect your GitHub account if you haven't already
4. Select your repository

### Step 3: Configure Environment Variables

Render will read the `render.yaml` file, but you need to set the API keys:

1. In the Render dashboard, go to your service
2. Navigate to **Environment** tab
3. Add these environment variables:

```
OPENAI_API_KEY=sk-your-actual-openai-key-here
SERPER_API_KEY=your-actual-serper-key-here
```

⚠️ **IMPORTANT**: These are sensitive keys! Never commit them to your repository.

### Step 4: Deploy

1. Render will automatically detect the `render.yaml` configuration
2. Click **"Apply"** to start the deployment
3. Wait for the build to complete (this may take 5-10 minutes)

## 🔍 Verify Deployment

Once deployed, your app will be available at:
```
https://ai-news-aggregator-XXXXX.onrender.com
```

### Test the Health Endpoint

Visit: `https://your-app-url.onrender.com/health`

You should see:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-10T...",
  "active_tasks": 0
}
```

### Test the Web Interface

Visit: `https://your-app-url.onrender.com/`

You should see the AI News Aggregator web interface.

## 🐛 Troubleshooting

### Common Issues

#### 1. Build Fails

**Error**: `No module named 'crewai'`

**Solution**: Check that `pyproject.toml`'s dependencies are correct and committed to your repository.

#### 2. Application Crashes on Startup

**Error**: Application fails to start

**Solution**: 
- Check Render logs: Go to your service → **Logs** tab
- Verify environment variables are set correctly
- Ensure both `OPENAI_API_KEY` and `SERPER_API_KEY` are configured

#### 3. Health Check Fails

**Error**: Health check endpoint returns 404

**Solution**: Make sure your `render.yaml` has the correct `startCommand`:
```yaml
startCommand: uvicorn app:app --host 0.0.0.0 --port $PORT
```

#### 4. Blog Generation Fails

**Error**: "OPENAI_API_KEY is not set"

**Solution**: 
1. Go to Render Dashboard → Your Service → Environment
2. Add the missing environment variable
3. Save and trigger a manual deploy

### View Logs

To debug issues:
1. Go to your Render Dashboard
2. Select your service
3. Click **"Logs"** tab
4. Look for error messages in red

## 📊 Monitoring

### Check Application Health

The app includes a health check endpoint that Render uses to monitor your service:

```bash
curl https://your-app-url.onrender.com/health
```

### View Active Tasks

The health endpoint also shows how many blog generation tasks are currently running:

```json
{
  "status": "healthy",
  "timestamp": "2025-11-10T12:00:00",
  "active_tasks": 2
}
```

## 💰 Cost Considerations

### Free Tier Limitations

Render's free tier includes:
- ✅ 750 hours/month of runtime
- ✅ Services spin down after 15 minutes of inactivity
- ✅ Cold starts take ~30 seconds when spinning up

⚠️ **Note**: First request after inactivity will be slow. Consider upgrading to a paid plan for production use.

### API Costs

- **OpenAI API**: Charges per token used (GPT-4o-mini is ~$0.15/$0.60 per 1M tokens)
- **Serper API**: Free tier includes 2,500 searches/month

## 🔒 Security Best Practices

### 1. Protect Your API Keys

- ✅ Never commit `.env` files to git
- ✅ Use Render's environment variable feature
- ✅ Rotate keys regularly

### 2. Configure CORS

In production, update `app.py` to restrict CORS origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-domain.com"],  # Replace with your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Rate Limiting

Consider adding rate limiting to prevent abuse:

```bash
pip install slowapi
```

## 🔄 Updating Your Deployment

To deploy updates:

```bash
git add .
git commit -m "Your update message"
git push origin main
```

Render will automatically detect the changes and redeploy.

### Manual Redeployment

If automatic deployment doesn't trigger:
1. Go to Render Dashboard
2. Select your service
3. Click **"Manual Deploy"** → **"Deploy latest commit"**

## 📚 Additional Resources

- [Render Documentation](https://render.com/docs)
- [FastAPI Deployment Guide](https://fastapi.tiangolo.com/deployment/)
- [CrewAI Documentation](https://docs.crewai.com/)

## 🆘 Getting Help

If you encounter issues:

1. **Check Render Logs**: Most issues are visible in the logs
2. **Review this guide**: Make sure all steps were followed
3. **Check Environment Variables**: Ensure all required variables are set
4. **Test Locally First**: Run `python start_web.py` locally to verify it works

---

**🎉 Congratulations!** Your AI News Aggregator is now deployed to Render and accessible from anywhere in the world!

