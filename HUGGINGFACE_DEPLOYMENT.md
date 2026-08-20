# 🤗 Deployment Guide for Hugging Face Spaces

> ⚠️ **This is no longer a free option.** Hugging Face now requires a paid **PRO** plan
> ($9/mo, plus hourly compute on top) to create a Docker Space at all — free personal accounts
> are limited to Gradio Spaces on ZeroGPU, which doesn't fit this app. Kept here as a condensed
> reference in case that changes. **For a free deployment, use
> [GOOGLE_CLOUD_RUN_DEPLOYMENT.md](GOOGLE_CLOUD_RUN_DEPLOYMENT.md) instead.**

## Prerequisites

A [Hugging Face account](https://huggingface.co/join) on PRO, an OpenAI + Serper API key, and
`git`. The repo's `Dockerfile` and `.dockerignore` already work as-is — Spaces expect the app on
port `7860`, which the `Dockerfile` already uses, and `README.md`'s top YAML block
(`sdk: docker`, `app_port: 7860`) is what Spaces reads to configure the build.

## Steps

1. [Create a Space](https://huggingface.co/new-space): SDK **Docker**, visibility **Private**
   (public Spaces let anyone trigger `/api/generate` and spend your API budget), hardware CPU
   basic.
2. Space Settings → Variables and secrets → add `OPENAI_API_KEY` and `SERPER_API_KEY` as
   **Secrets**.
3. Push this repo to the Space's git remote:
   ```bash
   git remote add space https://huggingface.co/spaces/<your-username>/<space-name>
   git push space main
   ```
   Use a Hugging Face [access token](https://huggingface.co/settings/tokens) (write scope) as
   the password, not your account password.
4. Watch the **Logs** tab for the build, then verify at
   `https://<your-username>-<space-name>.hf.space/health` (while logged into an account with
   access — the Space is private).

## Known gotchas

- **Ephemeral storage**: a free-tier Space's filesystem isn't guaranteed to persist across
  rebuilds/restarts, so `output/*.md` files can reset. Download generated posts promptly; don't
  rely on them surviving long-term without the paid Persistent Storage add-on. Project profiles
  under `src/ai_news_aggregator/config/projects/` are just as much at risk — back them up (or
  recreate them via `/api/projects`) if you rely on this.
- **Secret name typos** are the most common runtime failure — they must exactly match
  `OPENAI_API_KEY`/`SERPER_API_KEY` (case-sensitive).

## Cost

$9/mo PRO plan + hourly compute ($0.40/hr+ depending on hardware) on top of the usual OpenAI/
Serper API costs (~$0.01–$0.05/post on gpt-4o-mini).

## Updating

```bash
git push space main
```
