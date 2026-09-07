# Running ContentForge

ContentForge is a single-operator tool. It keeps a growing, long-lived store of research and
generated content, so it is designed to **run locally** (or on one always-on machine you
control) with persistent disk — not on ephemeral-disk platforms like Render's free tier,
Cloud Run, or Hugging Face Spaces.

> This guide will be expanded in Phase 9 of [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md)
> (auth, CLI, the SQLite data directory, and the `contentforge backup` command). For now it
> covers the local web server.

## Local (recommended)

```bash
pip install -e .
cp ENV_TEMPLATE.txt .env      # then fill in OPENAI_API_KEY and SERPER_API_KEY
uvicorn app:app --host 127.0.0.1 --port 8000
```

Open http://localhost:8000. Generated posts are written to `output/` (this becomes
`data/output/` once Phase 5 lands).

For auto-reload during development:

```bash
uvicorn app:app --reload
```

## Optional: personal server / VPS via Docker

Use this only if you want ContentForge reachable when you're away from your main machine. Run
a single instance and mount a volume so state survives restarts.

```bash
docker build -t contentforge .
docker run -d --name contentforge \
  -p 8000:8000 \
  --env-file .env \
  -v contentforge-data:/app/data \
  -v contentforge-output:/app/output \
  contentforge
```

Any host with a persistent volume works (a small VPS, Fly.io with a volume, Railway). Avoid
platforms that reset disk between deploys.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | yes | LLM calls |
| `SERPER_API_KEY` | yes | web search during research |
| `OPENAI_MODEL_NAME` | no | overrides the default model (wired up in a later phase) |
| `PORT` | no | server port when using `start_web.py` |
