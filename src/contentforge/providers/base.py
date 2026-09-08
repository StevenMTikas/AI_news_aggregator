"""Provider protocols and the plain data types that cross their boundaries.

These are deliberately small and vendor-neutral. The agent loop (``contentforge.agent_loop``)
and, later, the pipelines depend only on what is declared here -- swapping Serper for another
search API, or gpt-4o-mini for a different model, is a one-file change under this package.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence, runtime_checkable

from pydantic import BaseModel

# --------------------------------------------------------------------------- LLM


@dataclass(frozen=True)
class ToolSpec:
    """A tool offered to the model, in the shape every major API expects."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the arguments object


@dataclass(frozen=True)
class ToolCall:
    """A single tool invocation the model asked for."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LLMResult:
    content: str | None
    tool_calls: tuple[ToolCall, ...] = ()
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    finish_reason: str = "stop"


@runtime_checkable
class LLMProvider(Protocol):
    def complete(
        self,
        messages: Sequence[Mapping[str, Any]],
        *,
        tools: Sequence[ToolSpec] | None = None,
        response_model: type[BaseModel] | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> LLMResult:
        """One turn. When ``response_model`` is given and the model returns no tool calls,
        ``content`` must be JSON that validates against that model.
        """
        ...


# --------------------------------------------------------------------- Embeddings


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: tuple[tuple[float, ...], ...]
    tokens: int = 0
    model: str = ""


@runtime_checkable
class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str], *, model: str | None = None) -> EmbeddingResult: ...


# ------------------------------------------------------------------------- Search


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    published: str | None = None
    source: str = ""  # publisher/site label when the API supplies one
    kind: str = "organic"  # "organic" | "news"


class SearchBudget:
    """A mutable per-run ceiling on live search calls. ``None`` limit means unlimited.

    Shared across every agent in a run so the total is bounded, not just per-agent.
    """

    def __init__(self, max_calls: int | None = None) -> None:
        self.max_calls = max_calls
        self.calls_made = 0

    @property
    def exhausted(self) -> bool:
        return self.max_calls is not None and self.calls_made >= self.max_calls

    def record(self, n: int = 1) -> None:
        self.calls_made += n


@runtime_checkable
class SearchCache(Protocol):
    """Keyed store for raw provider responses. Phase 5 adds a SQLite-backed implementation;
    until then :class:`~contentforge.providers.serper.InMemorySearchCache` is the only impl.
    """

    def get(self, key: str) -> list[SearchResult] | None: ...

    def put(self, key: str, results: Sequence[SearchResult]) -> None: ...


@runtime_checkable
class SearchProvider(Protocol):
    def search(
        self,
        query: str,
        *,
        kind: str = "organic",
        recency_days: int | None = None,
        limit: int = 10,
    ) -> list[SearchResult]: ...


# ----------------------------------------------------------------------- Renderer


@dataclass(frozen=True)
class RenderedArtifact:
    """The bytes plus enough metadata to persist or serve them."""

    filename: str
    content: bytes
    mime: str

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")


@runtime_checkable
class Renderer(Protocol):
    """Turns a structured document into a publishable artifact -- or a list of them (the
    newsletter renderer emits Markdown + HTML). The first is treated as primary.
    """

    document_type: str

    def render(
        self, document: BaseModel, *, context: Mapping[str, Any] | None = None
    ) -> "RenderedArtifact | list[RenderedArtifact]": ...


# ---------------------------------------------------------------------------- misc

__all__ = [
    "ToolSpec",
    "ToolCall",
    "LLMResult",
    "LLMProvider",
    "EmbeddingResult",
    "EmbeddingProvider",
    "SearchResult",
    "SearchBudget",
    "SearchCache",
    "SearchProvider",
    "RenderedArtifact",
    "Renderer",
]
