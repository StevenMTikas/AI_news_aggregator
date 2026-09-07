"""Shared types for compose pipelines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Mapping, Optional, Protocol, runtime_checkable

from pydantic import BaseModel

from ..schemas import ResearchBrief


@dataclass
class Document:
    """One composed artifact, in memory. Becomes a ``document`` row in Phase 5."""

    type: str
    content: BaseModel  # BlogContent, LinkedInPost, ...
    title: str = ""
    based_on_brief_ids: List[str] = field(default_factory=list)
    based_on_document_ids: List[str] = field(default_factory=list)
    review_notes: str = ""


@runtime_checkable
class ComposePipeline(Protocol):
    """`compose` never changes shape: `source=None` is a sibling take off the research,
    `source=<Document>` is repurposing an existing artifact.
    """

    document_type: str
    default_target_words: Optional[int]

    def compose(
        self,
        brief: ResearchBrief,
        project: Any,
        *,
        corpus: Any | None = None,
        source: Document | None = None,
        context: Mapping[str, Any] | None = None,
    ) -> Document: ...


def resolve_target_words(pipeline_default: Optional[int], project: Any, document_type: str) -> Optional[int]:
    """Length is a property of the recipe. A project may override per recipe via
    ``length_overrides`` (added to the project model in Phase 5); until then we fall back to
    the legacy ``target_word_count`` and finally the pipeline default.
    """
    overrides = getattr(project, "length_overrides", None) or {}
    if document_type in overrides:
        return overrides[document_type]
    legacy = getattr(project, "target_word_count", None)
    if legacy:
        return legacy
    return pipeline_default
