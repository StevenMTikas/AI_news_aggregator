> **Superseded by [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md)** (the full-rewrite master
> plan). This document's Phase 1 survives as that plan's Phase 1; Phases 2–5 are folded into
> the rewrite (CrewAI is being removed, so the `crew.py` / `tasks.yaml` edits below no longer
> apply). Kept for the detailed reasoning on the Serper cache, `cache_function`, and the
> garbled-prompt inventory.

# Prompt Chain & Serper Cost — Detailed Implementation Plan

Expands the five-phase outline from the general chat into concrete, file-level steps.
Source review: [crew.py](src/ai_news_aggregator/crew.py),
[tasks.yaml](src/ai_news_aggregator/config/tasks.yaml),
[agents.yaml](src/ai_news_aggregator/config/agents.yaml),
[main.py](src/ai_news_aggregator/main.py), [schemas.py](src/ai_news_aggregator/schemas.py),
plus the installed `crewai` / `crewai-tools` source.

## Environment facts (verified against the installed packages)

| Fact | Value | Where checked |
|---|---|---|
| `crewai` | **0.201.1** (not 0.203) | `importlib.metadata` |
| `crewai-tools` | **0.76.0** | `importlib.metadata` |
| `BaseTool.max_usage_count` | exists, `int | None = None` | `crewai/tools/base_tool.py` |
| `BaseTool.current_usage_count` | exists, `int = 0` | same |
| `BaseTool.cache_function` | exists, default `lambda _args=None, _result=None: True` | same |
| YAML `context:` key | **is** resolved to real `Task` objects by `CrewBase._map_task_variables` (`crew_base.py:262`)… | `crewai/project/crew_base.py` |
| …but explicit `context=` kwarg in `crew.py` **wins** | confirmed at runtime in the general chat (`blog_writer_task: context=['research_task']`) | prior session |
| `@task` decorator | memoized (`memoize(wrapper)`), so the same `Task` instance is reused everywhere it is referenced | `crewai/project/annotations.py` |
| `SERPER_TOOL` | single module-level instance shared by both search agents → shared usage counter | `crew.py:10,27,35` |
| CrewAI cache handler | in-memory `CacheHandler`, rebuilt per `Crew` instance; `main.py` builds a fresh `AiNewsAggregator()` per run → **zero cross-run reuse** | prior session |
| agent `max_iter` | not set → CrewAI default (25) | `crew.py` |
| this worktree | **cannot import `crewai`** (`ModuleNotFoundError: appdirs`). Run all verification in the real project venv, not here. | — |

---

## Phase 1 — Correctness, no new abstractions (~1 hr)

Goal: make the code do what the config and prompts already claim. No new schemas, no
credit spend to verify — everything is checkable against `crewai`'s interpolation step and
the existing `output/*.md` renderer tests.

### 1.1 Give the blog writer the keyword research

**File:** [crew.py](src/ai_news_aggregator/crew.py) — `blog_writer_task` (lines 59-65).

```python
@task
def blog_writer_task(self) -> Task:
    return Task(
        config=self.tasks_config["blog_writer_task"],  # type: ignore[index]
        context=[self.research_task(), self.keyword_research_task()],
    )
```

- `self.research_task()` and `self.keyword_research_task()` return the memoized instances,
  so this does not create duplicate tasks or re-run anything.
- Order: research first (richer, more recent), keyword report second.
- Remove the now-unused local `research = self.research_task()` binding style if you prefer,
  or keep it — cosmetic.

**Decision — single source of truth for `context`:** keep the wiring in Python (matches the
existing pattern in `crew.py`; explicit kwargs already win over YAML). Then delete the YAML
`context:` keys in step 1.2 so the two don't drift again. (Alternative, not chosen: delete
the Python `context=` kwargs and let `crew_base.py` resolve the YAML names. Fewer lines, but
moves wiring away from where every other task field lives.)

### 1.2 Delete dead YAML keys

**File:** [tasks.yaml](src/ai_news_aggregator/config/tasks.yaml).

- Remove `verbose: true` from all three tasks — not a `Task` field in 0.201.1, silently
  dropped. Verbosity is already set at the `Crew` level (`crew.py:74`).
- Remove `context: [keyword_research_task]` from `research_task` and
  `context: [research_task, keyword_research_task]` from `blog_writer_task` — overridden by
  the Python kwargs; keeping them documents behavior that isn't happening.
- Leave `agent:` and `output_pydantic:` — those *are* consumed from YAML by `crew_base.py`.

### 1.3 Render the fields the schema already produces

**File:** [main.py](src/ai_news_aggregator/main.py) — `render_jekyll_markdown` (lines 43-69).

Currently emitted: `title`, `date`, `categories` (from `project.category_tags`), `author`,
`layout`, hook, sections, pull quotes, key points, CTA.
Dropped on the floor: `content.meta_description`, `content.tags`, `content.sources`.

Changes:

1. **Front matter** — add:
   - `description: "{content.meta_description}"` (Jekyll/SEO standard key; also used by most
     social-card plugins).
   - `tags: [{", ".join(content.tags)}]` — post-specific, keyword-derived. Keep
     `categories:` sourced from `project.category_tags` (stable taxonomy). This is the
     conventional Jekyll categories-vs-tags split; documenting it in the README (1.5) avoids
     confusion.
   - Escape/quote values that may contain `:` or `"` (title already unquoted-then-quoted;
     `meta_description` is free text — wrap in quotes and escape embedded quotes).

2. **Body** — append a Sources section after Key Takeaways:

   ```python
   sources = ""
   if content.sources:
       source_lines = "\n".join(f"- {s}" for s in content.sources)
       sources = f"\n\n## Sources\n\n{source_lines}"
   ```

   Render bare URLs as-is; if a source looks like `Title — URL`, pass it through unchanged
   (don't over-parse). Empty list → omit the heading entirely.

3. Keep `call_to_action` handling as-is.

### 1.4 Rewrite the garbled leftover sentences in `tasks.yaml`

These are remnants of an earlier design where the keyword agent *chose* the topic. `{topic}`
now arrives from the user via `build_default_inputs`. Rewrite:

| Task | Current (garbled) | Problem | Suggested |
|---|---|---|---|
| `research_task` description | "Using the keyword research results provided, look for the {topic} **Search for** current news, trends, and real-world applications from {current_year}…" | dropped clause, two sentences fused | "Using the keyword research provided, search for current news, trends, and real-world applications of {topic} from {current_year} that relate to the primary keywords." |
| `research_task` expected_output | "A comprehensive research report about the {topic} **identified in the keyword research**…" | implies keyword research picks the topic | "A comprehensive research report on {topic}, organized around the primary keywords from the keyword research…" |
| `blog_writer_task` description | "Using the research provided, **look for the {topic} section from the keyword research task.** Write an engaging blog post about **this {topic} as the main topic.**" | refers to a "section" that doesn't exist; redundant phrasing | "Using the research and keyword report provided, write an engaging blog post about {topic}. Focus on the primary keywords identified in the keyword research." |

Also sweep the rest of `blog_writer_task.description` for "the primary keywords found in the
keyword research" phrasing — now literally true once 1.1 lands, so it can stay, but make sure
it reads coherently after the edits above.

### 1.5 Docs

- [README.md](README.md) lines ~110-137: the rendered-markdown example omits sources /
  description / tags — update it to match the new `render_jekyll_markdown` output.
- [README.md](README.md) "The AI Agents" section: the writer now genuinely receives the
  keyword report — no wording change needed, but confirm it's accurate.
- [future-ideas.md](future-ideas.md) #5 ("Response/generation caching") — leave for now;
  Phase 3 addresses the Serper half, not full-pipeline caching. Add a note pointing at this
  plan.

### 1.6 Tests (no API key, no LLM)

**File:** [tests/test_main.py](tests/test_main.py).

- Extend `test_render_jekyll_markdown_includes_front_matter_and_sections`:
  assert `description:` in front matter, `## Sources` and the source URL in body,
  `tags: [AI, Restaurants]` in front matter.
- Add `test_render_jekyll_markdown_omits_sources_when_empty` — `make_content(sources=[])`,
  assert `## Sources` **not** in output.
- `make_content` already sets `meta_description` / `tags` / `sources`, so fixtures are ready.

**File:** [tests/test_crew_config.py](tests/test_crew_config.py).

- Add `test_blog_writer_task_sees_keyword_and_research_context`:
  build the crew, find `blog_writer_task`, assert its `.context` names include both
  `keyword_research_task` and `research_task`.
- `test_all_placeholders_interpolate_without_error` already guards the YAML edits.

### 1.7 Verification (free)

```bash
python -m pytest -q
```

Then a single real run against a throwaway topic to eyeball the rendered `output/*.md`
(this does cost ~1 run of credits, but it's the only way to see the Sources section
populate). Diff the new `.md` against a pre-Phase-1 one for the same topic.

**Risk:** low. Worst case a front-matter value with an unescaped quote breaks the YAML block
— covered by the escaping in 1.3 and the new test.

---

## Phase 2 — Spend controls (~15-30 min)

Goal: put a hard ceiling on Serper spend *before* Phases 3-5 make you re-run the pipeline
repeatedly.

### 2.1 Split the shared tool instance

**File:** [crew.py](src/ai_news_aggregator/crew.py:10).

Today both agents share `SERPER_TOOL`, so any `max_usage_count` is a *combined* budget and
you can't later drop the tool from one agent cleanly. Replace with a small factory:

```python
def _serper_tool(max_usage_count: int) -> SerperDevTool:
    return SerperDevTool(
        max_usage_count=max_usage_count,
        cache_function=_cache_nonempty_results,
    )
```

and give each agent its own instance (`keyword_researcher` and `researcher`).

### 2.2 `max_usage_count`

Per-agent ceiling (BaseTool field, 0.76.0). Suggested starting values:
`keyword_researcher` → 3, `researcher` → 6. Tune after watching one verbose run. When the
cap is hit, CrewAI stops calling the tool and the agent must finish from what it has —
acceptable, and much better than an unbounded `max_iter=25` loop.

### 2.3 `cache_function` — don't cache failures/empties

**File:** [crew.py](src/ai_news_aggregator/crew.py).

```python
def _cache_nonempty_results(args=None, result=None) -> bool:
    if not isinstance(result, dict):
        return False
    return bool(result.get("organic") or result.get("news"))
```

Signature matches `BaseTool.cache_function`'s `(_args=None, _result=None)`. Stops the
in-memory cache from pinning an empty/error response for the rest of the run.

### 2.4 `max_rpm` on the crew

**File:** [crew.py](src/ai_news_aggregator/crew.py:70) — `Crew(..., max_rpm=…)`.

Serper's `/account` reports `"rateLimit": 5`. Set `max_rpm=30` (well under, leaves headroom
for OpenAI calls which don't count) — the goal is only to avoid 429 bursts, not to throttle
throughput. Note: `max_rpm` is enforced by CrewAI's `RPMController` across the whole crew.

### 2.5 Tests

- `test_crew_config.py`: assert each search agent's tool has `max_usage_count` set and a
  non-default `cache_function`; assert `crew().max_rpm` is set.
- Unit-test `_cache_nonempty_results` directly with `{}`, `{"organic": [...]}`,
  `{"news": [...]}`, `None`, `"error string"`.

### 2.6 Verification

One verbose run; grep the log for `Search the internet with Serper` invocations and confirm
the count stops at the cap. Check `curl .../account` balance before and after — delta should
be ≤ (3 + 6).

**Risk:** low. If a cap is too tight the agent produces thinner output — visible immediately,
one-line fix.

---

## Phase 3 — Persistent disk cache (~half day)

Goal: kill repeat Serper cost *across* runs. This is the actual answer to "can results be
cached the first time." Highest payoff during Phases 4-5 when the same topic is run
repeatedly.

### 3.1 `CachedSerperDevTool`

**New file:** `src/ai_news_aggregator/tools/cached_serper.py`.

```python
class CachedSerperDevTool(SerperDevTool):
    cache_dir: Path = ...
    ttl_seconds: int = 24 * 3600          # news
    evergreen_ttl_seconds: int = 7 * 24 * 3600
    enabled: bool = True

    def _run(self, **kwargs):
        if not self.enabled:
            return super()._run(**kwargs)
        key = self._key(kwargs)          # normalized
        hit = self._read(key)
        if hit is not None:
            return hit
        result = super()._run(**kwargs)
        if _cache_nonempty_results(result=result):
            self._write(key, result)
        return result
```

Details:

- **Key normalization:** lowercase, strip punctuation, collapse whitespace, sort tokens,
  then include `search_type` and `n_results`. Hash to a filename
  (`sha1(normalized).json`). Sorting tokens makes "restaurant AI tools" and
  "AI tools restaurant" hit the same entry — the exact-string-match miss the general chat
  flagged.
- **Store:** one JSON file per key under `.cache/serper/` (git-ignored). JSON over SQLite —
  no concurrency concerns (sequential crew), trivially inspectable, easy to blow away.
  Envelope: `{"stored_at": <epoch>, "search_type": ..., "query": ..., "result": {...}}`.
- **TTL:** `search_type == "news"` → `ttl_seconds`; otherwise `evergreen_ttl_seconds`.
  Expired entry → treat as miss, overwrite.
- **Reuse `_cache_nonempty_results`** from Phase 2 so failures are never persisted.
- Register in `tools/__init__.py` (`__all__`).

### 3.2 `--no-cache`

Plumb a boolean from entry points down to the tool:

- `crew.py`: `AiNewsAggregator` gains a way to receive `use_cache` (constructor arg or a
  class attribute set before `.crew()`); the factory passes `enabled=use_cache` to the tool.
  Because `@CrewBase` wraps `__init__`, prefer an explicit `__init__` override that calls
  `super().__init__()` then stores the flag, or a module-level default toggled by `main.py`.
- `main.py` `run_pipeline(inputs, project, output_dir=None, use_cache=True)` → pass through.
- `cli.run(..., use_cache: bool = True)` and `main.run(...)`.
- `app.py`: optional `no_cache: bool = False` on `BlogRequest`; pass into `run_pipeline`.
- This intersects [future-ideas.md](future-ideas.md) #7 (no real CLI arg parsing). Minimal:
  add a `--no-cache` flag with `argparse` in a thin `__main__` block, or just accept the
  Python-one-liner path for now and expose the flag via the API + a keyword arg.

### 3.3 Cache management

- `.gitignore`: add `.cache/`.
- Add a `scripts/clear_serper_cache.py` (or a `make`-style one-liner in the README):
  delete `.cache/serper/*.json`.
- Optional: log a one-line summary per run — `serper cache: 4 hits, 2 misses`.

### 3.4 Tests

- `tmp_path` cache dir. Monkeypatch `SerperDevTool._run` (the parent) to a counter-backed
  fake returning `{"organic": [...]}`.
- `test_second_call_same_query_hits_cache` — parent called once across two `_run`s.
- `test_token_order_normalized` — "a b" and "b a" share an entry.
- `test_expired_entry_refetches` — write envelope with old `stored_at`, assert refetch.
- `test_empty_result_not_cached` — parent returns `{}`, second call re-hits parent.
- `test_disabled_bypasses_cache` — `enabled=False` always calls parent.
- `test_no_cache_flag_threads_through` — `run_pipeline(use_cache=False)` builds a crew whose
  tools are disabled (inspect `crew().agents[*].tools[0].enabled`).

### 3.5 Verification

Run the same topic twice with cache on: second run should spend **0** Serper credits
(confirm via `/account` delta) and finish faster. Then once with `--no-cache`: full spend
again.

**Risk:** medium. Main hazards: (a) stale evergreen results served past their usefulness —
mitigated by TTL + `--no-cache`; (b) the `use_cache` flag not reaching the tool because of
`@CrewBase.__init__` wrapping — verify with the threading test in 3.4 before trusting it.

---

## Phase 4 — Structured intermediate outputs (~half day)

Goal: replace the two free-form prose blobs with schemas so handoffs are deterministic,
context is smaller, and intermediate results are serializable (needed for Phase 5 and for
any future replay/caching of research).

### 4.1 Schemas

**File:** [schemas.py](src/ai_news_aggregator/schemas.py).

```python
class KeywordReport(BaseModel):
    primary_keywords: List[str]          # 3-7, the ones downstream must focus on
    long_tail: List[str]
    trending: List[str]
    related_terms: List[str]
    by_intent: dict[str, List[str]]      # {"informational": [...], "commercial": [...], ...}
    notes: Optional[str] = None

class SourceRef(BaseModel):
    title: str
    url: str
    published: Optional[str] = None
    takeaway: str                        # one sentence: what this source establishes

class ResearchBrief(BaseModel):
    topic: str
    key_findings: List[str]
    trends: List[str]
    audience_impact: List[str]
    sources: List[SourceRef]             # >= 5, enforced in the prompt + a guardrail
    keyword_coverage: dict[str, str]     # primary keyword -> which finding(s) cover it
```

### 4.2 Wire them

**File:** [crew.py](src/ai_news_aggregator/crew.py).

- `output_pydantic(KeywordReport)` / `output_pydantic(ResearchBrief)` as module-level, same
  pattern as `BlogContent` (`crew.py:11`).
- Add `output_pydantic=` to `keyword_research_task` and `research_task`, or the YAML
  `output_pydantic:` key + an `@output_pydantic` class (matches the existing `BlogContent`
  wiring via `crew_base.py`).
- Trim the long bulleted `expected_output` wishlists in `tasks.yaml` — the schema now
  carries the structure; the prose just needs to say "fill every field."

### 4.3 Consume them

- `blog_writer_task.description`: reference `primary_keywords` and `sources` explicitly —
  "Write about each of the primary_keywords from the keyword report" / "Every factual claim
  must trace to a source in the research brief; copy those URLs into the `sources` field."
- `BlogContent.sources` can now be populated by copying `ResearchBrief.sources[].url`
  instead of the writer re-deriving them.
- `main.py`: `result.pydantic` is still `BlogContent` (last task) — renderer unchanged.
  But the intermediate `ResearchBrief` is now available via `result.tasks_output` if you
  want to write a `output/<slug>.research.json` sidecar for auditing.

### 4.4 The measurement: does `keyword_researcher` still need Serper?

Do this **after** 4.1-4.3 and **after** Phase 3 (so the A/B is free on cache hits).

- **A (current):** `keyword_researcher` has `CachedSerperDevTool`.
- **B:** drop the tool; `keyword_researcher` generates keyword variants from the model alone
  (gpt-4o-mini is fine at this), `researcher` does all the searching.

Run the same 3 topics through both. Compare: `KeywordReport` quality (are primary keywords
sensible?), final post's keyword coverage, total Serper credits, wall-clock. The general
chat's hypothesis is B is nearly as good for ~half the search volume. If confirmed, delete
the tool from `keyword_researcher` in `crew.py` and note it in the README agent table.

### 4.5 Tests

- Schema round-trip tests (`KeywordReport(**dict)` etc.).
- `test_crew_config.py`: assert `keyword_research_task.output_pydantic is KeywordReport`,
  `research_task.output_pydantic is ResearchBrief`.
- Update `test_all_placeholders_interpolate_without_error` if `expected_output` text changes
  placeholders (it shouldn't).

### 4.6 Verification

One full run; assert `result.tasks_output[0].pydantic` is a `KeywordReport` and
`[1].pydantic` is a `ResearchBrief` with ≥5 sources. Eyeball the final post for keyword drift
vs. Phase 1 baseline.

**Risk:** medium. gpt-4o-mini sometimes fills structured output lazily (empty lists). Add a
CrewAI `guardrail` on `research_task` requiring `len(sources) >= 5`, and keep
`expected_output` explicit about non-empty fields.

---

## Phase 5 — Reviewer / editor agent (~2-3 hrs, cheap after Phase 3)

Goal: close the "no reviewer" gap from the first general-chat turn. A fourth sequential
agent that checks the draft against the research and fixes drift. Cheap because it validates
against the **cached** `ResearchBrief` (Phase 4) / cached Serper store (Phase 3) instead of
issuing fresh searches.

### 5.1 Agent

**File:** [agents.yaml](src/ai_news_aggregator/config/agents.yaml).

```yaml
editor:
  role: >
    Editor and fact-checker for {project_name}
  goal: >
    Ensure every factual claim in the draft is supported by the research brief, the
    primary keywords are covered, the tone matches {tone}, and the {audience} can follow it
  backstory: >
    You're a meticulous editor who never lets an unsupported claim ship. You cut drift,
    fix jargon, and verify each statistic against its source.
  llm: gpt-4o-mini
```

Tool choice — two options:

- **No tool (recommended first cut):** the editor only has `ResearchBrief` + draft in
  context. It can flag/repair unsupported claims by removing or softening them. Zero extra
  spend.
- **`CachedSerperDevTool` with a tight `max_usage_count` (1-2):** lets it verify a specific
  disputed stat. Only add this if the no-tool version demonstrably lets errors through.

### 5.2 Task

**File:** [tasks.yaml](src/ai_news_aggregator/config/tasks.yaml) + [crew.py](src/ai_news_aggregator/crew.py).

```python
@task
def editor_task(self) -> Task:
    return Task(
        config=self.tasks_config["editor_task"],
        context=[self.blog_writer_task(), self.research_task(), self.keyword_research_task()],
        output_pydantic=BlogContent,
    )
```

- **Output shape decision:** the editor emits a corrected `BlogContent` (same schema as the
  writer). This keeps `main.py` unchanged — `result.pydantic` is still `BlogContent`, just
  from the last task. The alternative (a separate `EditorNotes` object + keep the writer's
  output as final) means the renderer would need to pick which task's output to use — more
  plumbing, less benefit.
- `editor_task` becomes the last task → `save_blog_post` automatically renders its output.
- Optionally also emit review notes as a sidecar: have the editor put a short changelog in a
  new optional `BlogContent` field (`editor_notes: Optional[str]`) or write
  `output/<slug>.review.md` from `result.tasks_output[-2:]`.

### 5.3 `expected_output`

Explicit checklist: every claim traceable to `ResearchBrief.sources`; unsupported specifics
removed or hedged; all `primary_keywords` represented; `sources` list = union of URLs
actually cited; tone/word-count within range.

### 5.4 Config / docs

- `crew.py`: the `@crew` method auto-collects tasks via `_original_tasks`, so just adding
  `editor_task` + the `editor` `@agent` is enough — `crew()` picks them up in definition
  order. Confirm order: keyword → research → writer → editor.
- `test_crew_config.py`: `len(crew.agents) == 4`, `len(crew.tasks) == 4`, last task's
  `output_pydantic is BlogContent`.
- README: add the Editor agent to the pipeline description and the agent table; update the
  "what you don't have: a reviewer" note (now you do).
- Cost: README "💰 Cost" — a 4th gpt-4o-mini pass adds roughly +25-40% tokens; still cents.

### 5.5 Verification

Run a topic known to have produced an unsupported claim pre-Phase-5 (the general chat cited
a sample post that dated a trend to "By 2026" with nothing backing it). Confirm the editor
removes or sources it. Diff writer output vs. editor output in `result.tasks_output`.

**Risk:** medium. The editor can over-cut and shrink the post below `target_word_count`, or
"correct" things that were fine. Mitigations: word-count floor in `expected_output`;
temperature low; keep the writer's draft as a sidecar so nothing is lost.

---

## Sequencing & independence

```
Phase 1 ──────────────► (correctness; unblocks everything)
Phase 2 ──────────────► (independent of 1; do early to bound spend)
        Phase 3 ──────► (needs 2's _cache_nonempty_results)
                Phase 4 ──────► (needs 1; benefits from 3 for free A/B)
                        Phase 5 ──────► (needs 4's ResearchBrief; cheap after 3)
```

- Phases 1 and 2 can land in either order, in the same afternoon, low risk.
- Do not start Phase 4's "drop the tool" measurement until Phase 3 is merged — otherwise the
  A/B costs real credits per iteration.
- Each phase ends with `python -m pytest -q` green **in the real venv** (this worktree is
  missing deps) and, for phases that touch runtime behavior, one verbose crew run with a
  before/after `output/*.md` diff.

## Out of scope here (tracked in [future-ideas.md](future-ideas.md))

`OPENAI_MODEL_NAME` env override (#6), API rate limiting (#2), CORS narrowing (#3),
persistent task queue (#4), full-pipeline (not just Serper) response caching (#5),
`train`/`replay`/`test` CLI commands (#1). Phase 3 partially addresses #5's Serper portion.
