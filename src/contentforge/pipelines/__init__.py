"""Pipelines: the research pass and the per-format compose recipes.

`ResearchPipeline` produces a `ResearchBrief` (expensive, cached upstream). Compose pipelines
follow the `compose(brief, project, corpus=None, source=None) -> Document` shape. Blog and
LinkedIn run the full review chain; thread and repurpose run a light (voice-only) review.
"""

from .base import ComposePipeline, Document, resolve_target_words
from .blog_post import BlogPostPipeline
from .linkedin import LinkedInPipeline
from .research import ResearchPipeline
from .social import RepurposePipeline, SocialThreadPipeline

COMPOSE_PIPELINES = {
    "blog_post": BlogPostPipeline,
    "linkedin_post": LinkedInPipeline,
    "social_thread": SocialThreadPipeline,
    "repurpose": RepurposePipeline,
}

__all__ = [
    "ComposePipeline",
    "Document",
    "resolve_target_words",
    "BlogPostPipeline",
    "LinkedInPipeline",
    "SocialThreadPipeline",
    "RepurposePipeline",
    "ResearchPipeline",
    "COMPOSE_PIPELINES",
]
