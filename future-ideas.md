# Future Ideas

Features or hooks that are referenced somewhere in this project (docs, config, scaffolding)
but aren't actually implemented yet. Compiled by scanning the codebase and docs for things
promised but not built.

## 1. `train` / `replay` / `test` CLI commands

`pyproject.toml` registers these as installable console scripts:

```toml
train = "ai_news_aggregator.main:train"
replay = "ai_news_aggregator.main:replay"
test = "ai_news_aggregator.main:test"
```

None of `train`, `replay`, or `test` exist in [`src/ai_news_aggregator/main.py`](src/ai_news_aggregator/main.py) —
only `build_default_inputs`, `slugify_title`, `save_blog_post`, `run_pipeline`, and `run` are defined.
Running any of these three commands today fails immediately. This is CrewAI's standard project
scaffolding (train the crew over N iterations, replay a specific task from a previous run, test
outputs against different LLMs) — worth either implementing them (CrewAI's `Crew` object has
built-in `train()`/`test()` support and `replay_from_task_id`) or removing the entry points from
`pyproject.toml` if they're not wanted.

## 2. Rate limiting on the public API

[DEPLOYMENT.md](DEPLOYMENT.md) (Security Best Practices) suggests adding rate limiting to
`/api/generate` to prevent abuse, with `pip install slowapi` as the suggested approach. Not
implemented — `slowapi` isn't in `requirements.txt`/`pyproject.toml`, and `app.py` has no
per-IP or per-key throttling. Since each generation call costs real OpenAI/Serper spend, an
unthrottled public endpoint is a real cost-abuse risk.

## 3. Restrict CORS to a specific domain in production

[DEPLOYMENT.md](DEPLOYMENT.md) explicitly documents narrowing CORS before going to production:

```python
allow_origins=["https://your-domain.com"],  # Replace with your domain
```

`app.py` currently hardcodes `allow_origins=["*"]` unconditionally — the production-hardening
step described in the deployment guide was never applied to the code.

## 4. Persistent/shared task queue (e.g. Redis)

[DEPLOYMENT_CHANGES_SUMMARY.md](DEPLOYMENT_CHANGES_SUMMARY.md) (Optimization Options) lists
"Add Redis for task queue (if scaling needed)." Today, task state lives entirely in an
in-memory Python dict in `app.py` (`tasks: Dict[str, Dict] = {}`), which means all in-flight
and completed task records are lost on restart and can't be shared across multiple worker
processes/instances.

## 5. Response/generation caching

Mentioned in both [DEPLOYMENT_CHANGES_SUMMARY.md](DEPLOYMENT_CHANGES_SUMMARY.md)
("Implement caching for repeated queries") and
[PRE_DEPLOYMENT_CHECKLIST.md](PRE_DEPLOYMENT_CHECKLIST.md) ("Use caching for API responses if
applicable"). No caching layer exists anywhere in `app.py` or `crew.py` — every request re-runs
the full keyword research → research → writing pipeline, even for a repeated/similar topic.

## 6. Configurable model via `OPENAI_MODEL_NAME` env var

[ENV_TEMPLATE.txt](ENV_TEMPLATE.txt) documents an optional override:

```
# OPENAI_MODEL_NAME=gpt-4o-mini
```

But nothing in the code reads this variable — the model is hardcoded as `llm: gpt-4o-mini`
directly in each agent's config in
[`src/ai_news_aggregator/config/agents.yaml`](src/ai_news_aggregator/config/agents.yaml).
Changing the model today requires editing the YAML, not setting an env var, despite the
template implying otherwise.
