# Future Ideas — resolved

This file tracked eight gaps in the original `ai_news_aggregator` (dead CLI scaffolding,
no rate limiting, wide-open CORS, in-memory task state, no cross-run caching, hard-coded
model, no CLI). **All eight were closed by the rewrite** (Phases 1–9) — see the §13 mapping
in [ARCHITECTURE_PLAN.md](ARCHITECTURE_PLAN.md).

Genuinely new ideas for later:

- **`sqlite-vec` for retrieval.** `KnowledgeStore` does brute-force cosine over stored
  embeddings — fine at personal scale (hundreds–thousands of items). If a project's corpus
  grows large, swap in `sqlite-vec` behind the same interface.
- **Podcast audio.** `PodcastScriptRenderer` emits a script; a TTS step could produce audio.
- **Scheduled runs.** A cron-style "re-research these topics weekly" using `brief_updater`.
- **More search providers.** `SearchProvider` is a protocol; a fallback for when Serper
  credits run out.
