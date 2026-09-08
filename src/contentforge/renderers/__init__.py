"""Renderers turn a structured document into a publishable artifact (or a list of them)."""

from .jekyll import JekyllMarkdownRenderer
from .longform import GuidePdfRenderer, NewsletterRenderer, PodcastScriptRenderer
from .social import LinkedInRenderer, RepurposeRenderer, SocialThreadRenderer

DEFAULT_RENDERERS = {
    "blog_post": JekyllMarkdownRenderer(),
    "linkedin_post": LinkedInRenderer(),
    "social_thread": SocialThreadRenderer(),
    "repurpose": RepurposeRenderer(),
    "newsletter": NewsletterRenderer(),
    "podcast_script": PodcastScriptRenderer(),
    "guide": GuidePdfRenderer(),
}

__all__ = [
    "JekyllMarkdownRenderer",
    "LinkedInRenderer",
    "SocialThreadRenderer",
    "RepurposeRenderer",
    "NewsletterRenderer",
    "PodcastScriptRenderer",
    "GuidePdfRenderer",
    "DEFAULT_RENDERERS",
]
