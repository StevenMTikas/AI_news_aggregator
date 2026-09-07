"""Search providers.

``SerperSearchProvider`` is the real implementation: normalised-query caching, a per-run call
budget, optional recency filtering, and domain preference/exclusion. ``NullSearchProvider``
returns canned results for offline tests and dev.

The cache here is in-memory only; Phase 5 of ARCHITECTURE_PLAN.md adds a SQLite-backed
``SearchCache`` so results survive across runs.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Iterable, Sequence

from .base import SearchBudget, SearchCache, SearchResult

_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, sort tokens.

    Makes "AI tools for restaurants" and "restaurants AI tools" hit the same cache entry.
    """
    lowered = _PUNCT.sub(" ", query.lower())
    tokens = sorted(t for t in _WS.sub(" ", lowered).strip().split(" ") if t)
    return " ".join(tokens)


def cache_key(query: str, *, kind: str, limit: int) -> str:
    return f"{kind}:{limit}:{normalize_query(query)}"


class SearchBudgetExceeded(RuntimeError):
    """Raised when a live search is attempted after the run's SearchBudget is spent."""


class InMemorySearchCache(SearchCache):
    def __init__(self) -> None:
        self._store: dict[str, list[SearchResult]] = {}

    def get(self, key: str) -> list[SearchResult] | None:
        hit = self._store.get(key)
        return list(hit) if hit is not None else None

    def put(self, key: str, results: Sequence[SearchResult]) -> None:
        if results:  # never cache an empty/failed response
            self._store[key] = list(results)

    def __len__(self) -> int:  # convenience for tests
        return len(self._store)


class NullSearchProvider:
    """Returns the same canned results for every query. For tests and offline runs."""

    def __init__(self, canned: Iterable[SearchResult] | None = None) -> None:
        self._canned = list(canned or ())

    def search(
        self,
        query: str,
        *,
        kind: str = "organic",
        recency_days: int | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        return [r for r in self._canned if r.kind == kind][:limit]


def _qdr(recency_days: int | None) -> str | None:
    if not recency_days:
        return None
    if recency_days <= 1:
        return "qdr:d"
    if recency_days <= 7:
        return "qdr:w"
    if recency_days <= 31:
        return "qdr:m"
    if recency_days <= 366:
        return "qdr:y"
    return None


def _domain(url: str) -> str:
    m = re.match(r"https?://([^/]+)", url or "")
    return (m.group(1).lower().removeprefix("www.")) if m else ""


class SerperSearchProvider:
    ENDPOINTS = {"organic": "search", "news": "news"}

    def __init__(
        self,
        api_key: str,
        *,
        cache: SearchCache | None = None,
        budget: SearchBudget | None = None,
        prefer_domains: Sequence[str] = (),
        exclude_domains: Sequence[str] = (),
        base_url: str = "https://google.serper.dev",
        timeout: float = 10.0,
        transport: Any | None = None,
    ) -> None:
        self.api_key = api_key
        self.cache = cache
        self.budget = budget
        self.prefer_domains = {d.lower().removeprefix("www.") for d in prefer_domains}
        self.exclude_domains = {d.lower().removeprefix("www.") for d in exclude_domains}
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        # ``transport`` lets tests inject a callable(url, payload, headers) -> dict
        self._transport = transport or self._http_post

    def search(
        self,
        query: str,
        *,
        kind: str = "organic",
        recency_days: int | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        if kind not in self.ENDPOINTS:
            raise ValueError(f"unknown search kind: {kind!r}")
        key = cache_key(query, kind=kind, limit=limit)
        if self.cache is not None:
            cached = self.cache.get(key)
            if cached is not None:
                return self._filter(cached)

        if self.budget is not None and self.budget.exhausted:
            raise SearchBudgetExceeded(
                f"search budget of {self.budget.max_calls} calls is spent"
            )

        payload: dict[str, Any] = {"q": query, "num": limit}
        tbs = _qdr(recency_days)
        if tbs:
            payload["tbs"] = tbs
        raw = self._transport(
            f"{self.base_url}/{self.ENDPOINTS[kind]}",
            payload,
            {"X-API-KEY": self.api_key, "Content-Type": "application/json"},
        )
        if self.budget is not None:
            self.budget.record()

        results = self._parse(raw, kind)
        if self.cache is not None:
            self.cache.put(key, results)
        return self._filter(results)

    # -- internals ---------------------------------------------------------------

    def _http_post(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network path
            detail = exc.read().decode("utf-8", "replace")
            raise RuntimeError(f"Serper HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network path
            raise RuntimeError(f"Serper request failed: {exc.reason}") from exc

    @staticmethod
    def _parse(raw: dict[str, Any], kind: str) -> list[SearchResult]:
        rows = raw.get("news" if kind == "news" else "organic") or []
        out: list[SearchResult] = []
        for row in rows:
            link = row.get("link", "")
            if not link:
                continue
            out.append(
                SearchResult(
                    title=row.get("title", ""),
                    url=link,
                    snippet=row.get("snippet", ""),
                    published=row.get("date"),
                    source=row.get("source", _domain(link)),
                    kind="news" if kind == "news" else "organic",
                )
            )
        return out

    def _filter(self, results: Sequence[SearchResult]) -> list[SearchResult]:
        kept = [r for r in results if _domain(r.url) not in self.exclude_domains]
        if self.prefer_domains:
            kept.sort(key=lambda r: 0 if _domain(r.url) in self.prefer_domains else 1)
        return kept
