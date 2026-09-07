"""In-memory cost accounting.

The agent loop records an event per LLM turn / search / embedding call. Phase 5 persists
these to a ``cost_event`` table; for now a ``CostLedger`` accumulates them for a run and can
price them with a simple per-model table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

CostKind = Literal["llm", "search", "embedding"]

# USD per 1M tokens (input, output). Search is priced per call. Update as pricing changes;
# unknown models fall back to 0.0 so accounting never crashes a run.
_LLM_PRICES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
}
_EMBED_PRICES: dict[str, float] = {  # USD per 1M tokens
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
}
_SEARCH_PRICE_PER_CALL = 0.001  # Serper credit ~ this order of magnitude


def _model_key(model: str) -> str:
    for known in _LLM_PRICES:
        if model.startswith(known):
            return known
    return model


@dataclass(frozen=True)
class CostEvent:
    kind: CostKind
    provider: str
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    calls: int = 1

    @property
    def usd(self) -> float:
        if self.kind == "llm":
            pin, pout = _LLM_PRICES.get(_model_key(self.model), (0.0, 0.0))
            return self.tokens_in / 1e6 * pin + self.tokens_out / 1e6 * pout
        if self.kind == "embedding":
            return self.tokens_in / 1e6 * _EMBED_PRICES.get(self.model, 0.0)
        return self.calls * _SEARCH_PRICE_PER_CALL


@dataclass
class CostLedger:
    events: list[CostEvent] = field(default_factory=list)

    def record(self, event: CostEvent) -> CostEvent:
        self.events.append(event)
        return event

    def record_llm(self, provider: str, model: str, tokens_in: int, tokens_out: int) -> CostEvent:
        return self.record(CostEvent("llm", provider, model, tokens_in, tokens_out))

    def record_search(self, provider: str, model: str = "", calls: int = 1) -> CostEvent:
        return self.record(CostEvent("search", provider, model, calls=calls))

    def record_embedding(self, provider: str, model: str, tokens: int) -> CostEvent:
        return self.record(CostEvent("embedding", provider, model, tokens_in=tokens))

    @property
    def usd(self) -> float:
        return sum(e.usd for e in self.events)

    @property
    def tokens_in(self) -> int:
        """LLM prompt tokens only; embedding tokens are tracked but not rolled up here."""
        return sum(e.tokens_in for e in self.events if e.kind == "llm")

    @property
    def tokens_out(self) -> int:
        return sum(e.tokens_out for e in self.events if e.kind == "llm")

    @property
    def embedding_tokens(self) -> int:
        return sum(e.tokens_in for e in self.events if e.kind == "embedding")

    @property
    def search_calls(self) -> int:
        return sum(e.calls for e in self.events if e.kind == "search")
