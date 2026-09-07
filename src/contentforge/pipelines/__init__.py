"""Pipelines: the research pass and the per-format compose recipes.

`ResearchPipeline` produces a `ResearchBrief` (expensive, cached upstream). Compose pipelines
follow the `compose(brief, project, corpus=None, source=None) -> Document` shape -- fixed here
so it never needs reworking when the second recipe lands.
"""

from .base import ComposePipeline, Document, resolve_target_words
from .blog_post import BlogPostPipeline
from .research import ResearchPipeline

__all__ = [
    "ComposePipeline",
    "Document",
    "resolve_target_words",
    "BlogPostPipeline",
    "ResearchPipeline",
]
