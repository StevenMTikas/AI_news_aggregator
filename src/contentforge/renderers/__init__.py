"""Renderers turn a structured document into a publishable artifact.

Phase 4 ships the Jekyll blog renderer; newsletter / podcast / PDF / LinkedIn renderers
arrive in Phases 7-8.
"""

from .jekyll import JekyllMarkdownRenderer

__all__ = ["JekyllMarkdownRenderer"]
