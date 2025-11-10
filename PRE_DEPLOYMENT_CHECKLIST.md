# 📋 Pre-Deployment Checklist for Render

Use this checklist to ensure your application is ready for deployment.

## ✅ Files and Configuration

- [ ] `render.yaml` exists in the root directory
- [ ] `requirements.txt` exists in the root directory
- [ ] `pyproject.toml` exists in the root directory
- [ ] `app.py` exists in the root directory
- [ ] `start_web.py` exists in the root directory
- [ ] `static/` folder exists with `index.html`, `style.css`, and `app.js`
- [ ] `src/ai_news_aggregator/` folder contains all core application files
- [ ] `.env` file is in `.gitignore` (**CRITICAL** - never commit API keys!)
- [ ] `output/` folder is in `.gitignore`

## ✅ Environment Variables

Have these ready to add in Render Dashboard:

- [ ] `OPENAI_API_KEY` - Get from https://platform.openai.com/api-keys
- [ ] `SERPER_API_KEY` - Get from https://serper.dev/api-key

**Tip**: Test these keys locally first with `python start_web.py` to ensure they work.

## ✅ Code Review

- [ ] All Twitter/social media components removed (if applicable)
- [ ] No hardcoded API keys in code
- [ ] No sensitive data in code
- [ ] Logging is configured (app.py has logging setup)
- [ ] Error handling is in place
- [ ] Health check endpoint exists at `/health`

## ✅ Local Testing

Before deploying, test locally:

```bash
# Install dependencies
pip install -e .

# Set up environment variables
# Create .env file with your API keys

# Test web server
python start_web.py

# Visit http://localhost:8000
# Try generating a blog post
```

- [ ] Web interface loads successfully
- [ ] Can submit a blog post request
- [ ] Progress updates work
- [ ] Blog post generates successfully
- [ ] Can download the generated blog post
- [ ] No errors in terminal/console

## ✅ Git Repository

- [ ] Repository is pushed to GitHub
- [ ] `.gitignore` is properly configured
- [ ] No `.env` file in repository
- [ ] All necessary files are committed
- [ ] Repository is public or Render has access

## ✅ Render Configuration

### In `render.yaml`:

- [ ] `buildCommand` is correct: `pip install --upgrade pip && pip install -e .`
- [ ] `startCommand` is correct: `uvicorn app:app --host 0.0.0.0 --port $PORT`
- [ ] `healthCheckPath` is set to `/health`
- [ ] Environment variables are listed (but not values!)

### Expected Build Command Output:
```
Installing dependencies...
Running: pip install --upgrade pip && pip install -e .
Successfully installed crewai fastapi uvicorn ...
Build completed successfully
```

### Expected Start Command:
```
Starting service...
Running: uvicorn app:app --host 0.0.0.0 --port $PORT
INFO: Started server process
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:XXXXX
```

## ✅ API Key Verification

Before deployment, verify your API keys work:

### Test OpenAI:
```python
import openai
import os
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')

# Test with a simple completion
response = openai.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Hello"}]
)
print("OpenAI API: ✅ Working")
```

### Test Serper:
```python
import os
import requests
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv('SERPER_API_KEY')

url = "https://google.serper.dev/search"
payload = {"q": "test"}
headers = {
    'X-API-KEY': api_key,
    'Content-Type': 'application/json'
}

response = requests.post(url, json=payload, headers=headers)
if response.status_code == 200:
    print("Serper API: ✅ Working")
else:
    print(f"Serper API: ❌ Error {response.status_code}")
```

## ✅ Post-Deployment Testing

After deploying to Render:

- [ ] Service deploys successfully (check Render logs)
- [ ] Health check passes: Visit `https://your-app.onrender.com/health`
- [ ] Web interface loads: Visit `https://your-app.onrender.com/`
- [ ] Can submit a blog post request
- [ ] Blog post generates successfully
- [ ] Can download the generated file
- [ ] Check Render logs for any errors

## ✅ Performance Expectations

### Free Tier:
- ⏱️ **Cold start**: 30-60 seconds (first request after inactivity)
- ⏱️ **Warm response**: < 1 second
- ⏱️ **Blog generation**: 2-5 minutes (AI processing time)
- 💤 **Spin down**: After 15 minutes of inactivity

### Common Issues:

**Slow first load**: This is normal on free tier. The service "spins up" after inactivity.

**504 Gateway Timeout**: May occur during cold starts. Just refresh and try again.

**Blog generation takes long**: AI processing is inherently slow. 2-5 minutes is normal.

## 🚨 Security Checklist

- [ ] `.env` file is NOT in git repository
- [ ] API keys are set in Render dashboard, not in code
- [ ] `.gitignore` includes `.env` and sensitive files
- [ ] No passwords or secrets in code
- [ ] CORS is properly configured (restrict origins in production)

## 💡 Optimization Tips

### For Faster Deployments:
1. Use specific versions in `requirements.txt` (already done ✅)
2. Keep dependencies minimal
3. Test locally before each deployment

### For Better Performance:
1. Consider upgrading to paid Render plan (no cold starts)
2. Use caching for API responses if applicable
3. Monitor API usage to control costs

## 📞 Support Resources

If something goes wrong:

1. **Check Render Logs**: Dashboard → Your Service → Logs
2. **Review Deployment Guide**: See `DEPLOYMENT.md`
3. **Test Locally**: Reproduce the issue on your machine
4. **Environment Variables**: Most issues are due to missing/incorrect API keys

## ✅ Final Check

Everything checked off above? 

**🚀 You're ready to deploy!**

Follow the steps in [DEPLOYMENT.md](DEPLOYMENT.md) to deploy to Render.

---

**Last Updated**: November 10, 2025

