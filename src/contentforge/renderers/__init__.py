"""Renderers turn a structured document into a publishable artifact."""

from .jekyll import JekyllMarkdownRenderer
from .social import LinkedInRenderer, RepurposeRenderer, SocialThreadRenderer

DEFAULT_RENDERERS = {
    "blog_post": JekyllMarkdownRenderer(),
    "linkedin_post": LinkedInRenderer(),
    "social_thread": SocialThreadRenderer(),
    "repurpose": RepurposeRenderer(),
}

__all__ = [
    "JekyllMarkdownRenderer",
    "LinkedInRenderer",
    "SocialThreadRenderer",
    "RepurposeRenderer",
    "DEFAULT_RENDERERS",
]
