# Future Ideas

Features or hooks that are referenced somewhere in this project (docs, config, scaffolding)
but aren't actually implemented yet. Compiled by scanning the codebase and docs for things
promised but not built.

> Items 1–8 below are all scheduled to be resolved by the rewrite in
> [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md) — see its §13 mapping. This file will be
> pruned as those phases land. **Phases 1–9 done — all eight items are now resolved:**
> #1 (CLI scaffolding removed; `contentforge` is a real `typer` CLI), #2 (rate limiter on
> `/api/generate` + `/api/compile`), #3 (CORS locked to configurable origins), #4 (`run`
> table replaces the in-memory dict), #5 (SQLite cross-run search cache), #6
> (`project.default_model` + `max_usd_per_run` / `max_search_calls`), #7 & #8 (`contentforge
> project ...` / `generate` / `compile` / `runs` / `brief` subcommands). This file can be
> retired; Phase 10 folds anything remaining into the plan.

## 1. ~~`train` / `replay` / `test` CLI commands~~ — resolved (Phase 2)

These were CrewAI scaffolding entry points whose targets never existed. Removed from
`pyproject.toml` when CrewAI was dropped. Re-run / re-render capability is covered by the
`RunService` design in ARCHITECTURE_PLAN.md (Phase 5 `run` history + `render`, Phase 6
`brief_updater`).

## 2. Rate limiting on the public API

[DEPLOYMENT.md](DEPLOYMENT.md) (Security Best Practices) suggests adding rate limiting to
`/api/generate` to prevent abuse, with `pip install slowapi` as the suggested approach. Not
implemented — `slowapi` isn't in `pyproject.toml`'s dependencies, and `app.py` has no
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

Task state lives entirely in an in-memory Python dict in `app.py`
(`tasks: Dict[str, Dict] = {}`), which means all in-flight and completed task records are lost
on restart and can't be shared across multiple worker processes/instances. Worth revisiting if
this ever runs with more than one worker (Cloud Run deployment already pins `--max-instances 1`
specifically to work around this).

## 5. Response/generation caching

No caching layer exists anywhere in `app.py` or `crew.py` — every request re-runs the full
keyword research → research → writing pipeline, even for a repeated/similar topic within the
same project.

## 6. Configurable model via `OPENAI_MODEL_NAME` env var

[ENV_TEMPLATE.txt](ENV_TEMPLATE.txt) documents an optional override:

```
# OPENAI_MODEL_NAME=gpt-4o-mini
```

But nothing in the code reads this variable — the model is hardcoded as `llm: gpt-4o-mini`
directly in each agent's config in
[`src/contentforge/config/agents.yaml`](src/contentforge/config/agents.yaml).
Changing the model today requires editing the YAML, not setting an env var, despite the
template implying otherwise.

## 7. No CLI flag for selecting a project

`main.run()` and `cli.run()` now require a `project_slug` argument (added alongside the
multi-project feature), but the registered console scripts in `pyproject.toml`
(`contentforge` and `crewai run` itself) call `run()` with no arguments —
there's no argument parsing to supply a project slug from the command line. Today the only way
to run generation outside the web UI is a Python one-liner
(`python -c "from contentforge.main import run; run('slug')"`), documented as such in
[README.md](README.md). Worth adding real CLI argument parsing (`argparse`/`click`/`typer`) if
command-line usage becomes a real workflow, rather than just the web admin dashboard.

## 8. No way to create/edit projects from the CLI

Project management only exists via `/admin` or the `/api/projects` HTTP API
([`src/contentforge/projects.py`](src/contentforge/projects.py) has the underlying
`create_project`/`update_project`/`delete_project` functions) — there's no CLI equivalent. Minor
gap given the web dashboard covers the same ground, but worth noting for headless/scripted setups.
