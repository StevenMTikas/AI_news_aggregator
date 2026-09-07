"""Capability providers: thin protocols over vendors (LLM, embeddings, search) plus a
renderer seam. Concrete implementations live in sibling modules; nothing here is wired into
the app until Phase 4 of ARCHITECTURE_PLAN.md.
"""

from .base import (
    EmbeddingProvider,
    EmbeddingResult,
    LLMProvider,
    LLMResult,
    RenderedArtifact,
    Renderer,
    SearchBudget,
    SearchCache,
    SearchProvider,
    SearchResult,
    ToolCall,
    ToolSpec,
)
from .fakes import FakeEmbeddingProvider, FakeLLMProvider, ScriptedResponse
from .serper import InMemorySearchCache, NullSearchProvider, SerperSearchProvider, normalize_query

__all__ = [
    "EmbeddingProvider",
    "EmbeddingResult",
    "LLMProvider",
    "LLMResult",
    "RenderedArtifact",
    "Renderer",
    "SearchBudget",
    "SearchCache",
    "SearchProvider",
    "SearchResult",
    "ToolCall",
    "ToolSpec",
    "FakeEmbeddingProvider",
    "FakeLLMProvider",
    "ScriptedResponse",
    "InMemorySearchCache",
    "NullSearchProvider",
    "SerperSearchProvider",
    "normalize_query",
]
