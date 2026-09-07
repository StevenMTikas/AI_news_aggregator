"""Render ``BlogContent`` to a Jekyll-ready Markdown file.

This is the Phase 1 ``render_jekyll_markdown`` logic, moved behind the ``Renderer`` seam and
made responsible for its own filename.
"""

from __future__ import annotations

from datetime import date
from typing import Any, List, Mapping

from ..providers.base import RenderedArtifact
from ..projects import slugify
from ..schemas import BlogContent


def _yaml_double_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _yaml_flow_list(values: List[str]) -> str:
    return "[" + ", ".join(values) + "]"


class JekyllMarkdownRenderer:
    document_type = "blog_post"
    mime = "text/markdown"

    def render(
        self, document: BlogContent, *, context: Mapping[str, Any] | None = None
    ) -> RenderedArtifact:
        ctx = context or {}
        author: str = ctx.get("author", "")
        category_tags: List[str] = list(ctx.get("category_tags", []))
        current_date: str = ctx.get("current_date") or date.today().isoformat()

        body_sections = "\n\n".join(
            f"## {section.heading}\n\n{section.body}"
            + (f"\n\n> {section.pull_quote}" if section.pull_quote else "")
            for section in document.sections
        )
        key_points = "\n".join(f"- {point}" for point in document.key_points)
        cta = f"\n\n{document.call_to_action}" if document.call_to_action else ""
        sources = ""
        if document.sources:
            source_lines = "\n".join(f"- {source}" for source in document.sources)
            sources = f"\n\n## Sources\n\n{source_lines}"

        markdown = f"""---
title: {_yaml_double_quote(document.title)}
description: {_yaml_double_quote(document.meta_description)}
date: {current_date}
categories: {_yaml_flow_list(category_tags)}
tags: {_yaml_flow_list(document.tags)}
author: {author}
layout: post
---

{document.hook}

{body_sections}

## Key Takeaways

{key_points}{cta}{sources}
"""
        filename = f"{current_date}-{slugify(document.title)[:50]}-blog-post.md"
        return RenderedArtifact(filename=filename, content=markdown.encode("utf-8"), mime=self.mime)
