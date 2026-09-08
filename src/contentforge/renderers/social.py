"""Renderers for the short-form artifacts. Plain text -- these get pasted into a platform's
composer, so no markdown.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from ..providers.base import RenderedArtifact
from ..projects import slugify
from ..schemas import LinkedInPost, RepurposePack, SocialThread


def _stamp(context: Mapping[str, Any] | None) -> str:
    return (context or {}).get("current_date") or date.today().isoformat()


class LinkedInRenderer:
    document_type = "linkedin_post"
    mime = "text/plain"

    def render(self, document: LinkedInPost, *, context: Mapping[str, Any] | None = None) -> RenderedArtifact:
        blocks = [document.hook, *document.body]
        if document.cta:
            blocks.append(document.cta)
        if document.hashtags:
            blocks.append(" ".join(h if h.startswith("#") else f"#{h}" for h in document.hashtags))
        text = "\n\n".join(b for b in blocks if b)
        if document.link_url:
            if document.link_placement == "body":
                text += f"\n\n{document.link_url}"
            else:
                text += f"\n\n--- first comment ---\n{document.link_url}"
        name = slugify(document.hook.splitlines()[0] if document.hook else "linkedin-post")[:50]
        return RenderedArtifact(f"{_stamp(context)}-{name}-linkedin.txt", (text + "\n").encode("utf-8"), self.mime)


class SocialThreadRenderer:
    document_type = "social_thread"
    mime = "text/plain"

    def render(self, document: SocialThread, *, context: Mapping[str, Any] | None = None) -> RenderedArtifact:
        n = len(document.posts)
        lines = [f"{i}/{n} {post}" for i, post in enumerate(document.posts, 1)]
        if document.hashtags:
            lines.append(" ".join(h if h.startswith("#") else f"#{h}" for h in document.hashtags))
        text = "\n\n".join(lines)
        name = slugify(document.posts[0] if document.posts else "thread")[:50]
        return RenderedArtifact(f"{_stamp(context)}-{name}-thread.txt", (text + "\n").encode("utf-8"), self.mime)


class RepurposeRenderer:
    document_type = "repurpose"
    mime = "text/markdown"

    def render(self, document: RepurposePack, *, context: Mapping[str, Any] | None = None) -> RenderedArtifact:
        by_platform: dict[str, list[str]] = {}
        for s in document.snippets:
            by_platform.setdefault(s.platform, []).append(s.text)
        parts = []
        for platform, texts in by_platform.items():
            parts.append(f"## {platform}\n\n" + "\n\n".join(f"- {t}" for t in texts))
        text = "\n\n".join(parts) or "(no snippets)"
        return RenderedArtifact(f"{_stamp(context)}-repurpose-snippets.md", (text + "\n").encode("utf-8"), self.mime)
