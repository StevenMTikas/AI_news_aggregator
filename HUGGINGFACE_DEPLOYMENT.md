# 🤗 Deployment Guide for Hugging Face Spaces

> ⚠️ **This is no longer a free option.** Hugging Face now requires a paid **PRO** plan
> ($9/mo) to create Docker (or Gradio) Spaces at all — free personal accounts are limited to
> Gradio Spaces on ZeroGPU, which doesn't fit this app. This guide is kept for reference if
> you're already on PRO or that changes again. **For a free deployment, see
> [GOOGLE_CLOUD_RUN_DEPLOYMENT.md](GOOGLE_CLOUD_RUN_DEPLOYMENT.md) instead.**

This guide walks through deploying the AI News Aggregator to Hugging Face Spaces as a
**private**, Docker-based deployment — a good fit if you don't want strangers spending your
OpenAI/Serper budget and don't mind the PRO plan cost.

## Prerequisites

1. ✅ A [Hugging Face account](https://huggingface.co/join) (free)
2. ✅ An [OpenAI API key](https://platform.openai.com/api-keys)
3. ✅ A [Serper API key](https://serper.dev/api-key)
4. ✅ `git` installed locally

## 📋 Pre-Deployment Checklist

Make sure these are present in the repo (already set up by this change):
- ✅ `Dockerfile` — builds the app and listens on port `7860` (the port Spaces expect)
- ✅ `.dockerignore` — keeps `.venv`, `.env`, `output/`, etc. out of the build context
- ✅ `README.md` — starts with the Spaces metadata block (`sdk: docker`, `app_port: 7860`, etc.). Spaces read this to configure the build; don't remove it.

## 🌐 Deployment Steps

### Step 1: Create the Space

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space)
2. Fill in:
   - **Space name**: e.g. `ai-news-aggregator`
   - **SDK**: **Docker**
   - **Visibility**: **Private** ⚠️ — this is the important one. Public Spaces are visible/discoverable by anyone, and every visitor could trigger `/api/generate`, which spends your API credits. Private restricts access to your account (and anyone you explicitly add as a collaborator).
   - **Hardware**: CPU basic (free tier is enough for this app)
3. Click **Create Space**

### Step 2: Add Your API Keys as Secrets

1. In your new Space, go to **Settings** → **Variables and secrets**
2. Add two **Secrets** (not plain variables — secrets are hidden from logs and the UI):
   - `OPENAI_API_KEY` = your OpenAI key
   - `SERPER_API_KEY` = your Serper key

⚠️ Never commit these to the repo. They're injected as environment variables at container runtime, same as `.env` does locally.

### Step 3: Push the Code

Spaces are git repositories. Add the Space as a second remote and push:

```bash
git remote add space https://huggingface.co/spaces/<your-username>/<space-name>
git push space main
```

You'll be prompted for credentials — use your Hugging Face username and a
[access token](https://huggingface.co/settings/tokens) (with **write** scope) as the password,
or set up the `huggingface-cli` git credential helper (`huggingface-cli login`).

### Step 4: Watch It Build

Go to your Space's **Logs** tab to watch the Docker build and container startup. First build
takes a few minutes (installing crewai and its dependencies).

## 🔍 Verify Deployment

Once built, your app is available at two URLs:
- Space page (Hugging Face UI wrapper): `https://huggingface.co/spaces/<your-username>/<space-name>`
- Direct app URL (what you'll actually use): `https://<your-username>-<space-name>.hf.space`

Since the Space is private, you'll need to be logged into Hugging Face with an account that has
access to see either one.

Check `/health` on the direct app URL — you should see the same JSON response you'd get locally.

## ⚠️ Ephemeral Storage — Read This

Unlike a VM, a free-tier Space's filesystem is **not guaranteed to persist** across rebuilds or
restarts (a new push, a manual restart, or Hugging Face infrastructure maintenance can reset it
to a fresh copy of the repo). This affects two things this app writes at runtime:

- **`output/`** — generated blog posts. Download the file (or copy the "View Content" preview)
  during the same session you generate it; don't rely on it still being there days later.
- **`knowledge/keywords_tracker.json`** — used to avoid repeating recently-covered topics. It
  may periodically reset, which just means the duplicate-avoidance logic loses its memory
  occasionally — not a functional break, just a minor loss of history.

If this becomes a problem, Hugging Face offers a paid **Persistent Storage** add-on per Space,
or you could point the app at an external store instead (see `future-ideas.md` item #4 on a
persistent task queue — the same gap applies to these files).

## 🐛 Troubleshooting

**Build fails with a compiler error**
The Dockerfile already installs `build-essential` for crewai's native dependencies. Check the
Logs tab for the specific missing package and add it to the `apt-get install` line if needed.

**App builds but won't start / "port already in use" type errors**
Confirm nothing in the Dockerfile or app code overrides the `--port 7860` the `CMD` sets —
Spaces route traffic to port 7860 specifically.

**"OPENAI_API_KEY is not set" at runtime**
Double-check the secret names in Settings → Variables and secrets exactly match
`OPENAI_API_KEY` and `SERPER_API_KEY` (case-sensitive).

**Can't push to the Space remote**
You need a Hugging Face access token with write scope, not your account password — generate one
at [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens).

## 💰 Cost

- **Hosting**: $9/mo minimum (HF PRO plan, required to create a Docker Space) plus compute billed hourly on top ($0.40/hr+ depending on hardware tier).
- **API costs**: same as before — OpenAI (~$0.01–$0.05/post on gpt-4o-mini) and Serper (free
  tier: 2,500 searches/month). Keeping the Space private is what keeps these costs under your
  control, since only you (or people you add) can trigger generation.

## 🔄 Updating Your Deployment

```bash
git push space main
```

Hugging Face rebuilds the container automatically on push.
