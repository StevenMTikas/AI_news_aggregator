"""Renderers for the Tier 2 long-form artifacts.

- Newsletter: Markdown (primary) + a simple email-ready HTML sibling.
- Podcast script: Markdown with bracketed segment cues.
- Guide: a PDF -- WeasyPrint if it is installed (HTML/CSS), otherwise a pure-Python ReportLab
  fallback so it works out of the box on Windows without system libraries.
"""

from __future__ import annotations

import html
from datetime import date
from typing import Any, Mapping

from ..providers.base import RenderedArtifact
from ..projects import slugify
from ..schemas import Guide, Newsletter, PodcastScript


def _stamp(context: Mapping[str, Any] | None) -> str:
    return (context or {}).get("current_date") or date.today().isoformat()


# ----------------------------------------------------------------- newsletter


class NewsletterRenderer:
    document_type = "newsletter"
    mime = "text/markdown"

    def render(self, document: Newsletter, *, context: Mapping[str, Any] | None = None):
        stamp = _stamp(context)
        name = slugify(document.subject)[:50] or "newsletter"

        md = [f"# {document.subject}", "", document.intro, ""]
        for item in document.items:
            md.append(f"## {item.heading}")
            md.append("")
            md.append(item.body)
            if item.source_url:
                md.append(f"\n[Source]({item.source_url})")
            md.append("")
        if document.sign_off:
            md.append(f"---\n\n{document.sign_off}")
        markdown = "\n".join(md).rstrip() + "\n"

        body_html = [f"<h1>{html.escape(document.subject)}</h1>",
                     f"<p>{html.escape(document.intro)}</p>"]
        for item in document.items:
            body_html.append(f"<h2>{html.escape(item.heading)}</h2><p>{html.escape(item.body)}</p>")
            if item.source_url:
                body_html.append(f'<p><a href="{html.escape(item.source_url)}">Source</a></p>')
        if document.sign_off:
            body_html.append(f"<hr><p>{html.escape(document.sign_off)}</p>")
        page = (
            "<!doctype html><html><head><meta charset=\"utf-8\"><style>"
            "body{font-family:Georgia,serif;max-width:640px;margin:2rem auto;line-height:1.5}"
            "h1{font-size:1.6rem}h2{font-size:1.2rem;margin-top:1.6rem}</style></head><body>"
            + "".join(body_html) + "</body></html>"
        )
        return [
            RenderedArtifact(f"{stamp}-{name}-newsletter.md", markdown.encode("utf-8"), "text/markdown"),
            RenderedArtifact(f"{stamp}-{name}-newsletter.html", page.encode("utf-8"), "text/html"),
        ]


# -------------------------------------------------------------- podcast script


class PodcastScriptRenderer:
    document_type = "podcast_script"
    mime = "text/markdown"

    def render(self, document: PodcastScript, *, context: Mapping[str, Any] | None = None) -> RenderedArtifact:
        lines = [f"# {document.title}", ""]
        if document.hook:
            lines += ["**Cold open:** " + document.hook, ""]
        for seg in document.segments:
            head = seg.cue if seg.cue.startswith("[") else f"[{seg.cue}]"
            if seg.duration_estimate:
                head += f"  _{seg.duration_estimate}_"
            lines += [f"## {head}", "", seg.script, ""]
        if document.outro:
            lines += ["## [OUTRO]", "", document.outro, ""]
        text = "\n".join(lines).rstrip() + "\n"
        name = slugify(document.title)[:50] or "podcast"
        return RenderedArtifact(f"{_stamp(context)}-{name}-podcast.md", text.encode("utf-8"), self.mime)


# --------------------------------------------------------------------- guide


class GuidePdfRenderer:
    document_type = "guide"
    mime = "application/pdf"

    def render(self, document: Guide, *, context: Mapping[str, Any] | None = None) -> RenderedArtifact:
        name = slugify(document.title)[:50] or "guide"
        pdf = _guide_pdf(document)
        return RenderedArtifact(f"{_stamp(context)}-{name}-guide.pdf", pdf, self.mime)


def _guide_html(document: Guide) -> str:
    parts = [f"<h1>{html.escape(document.title)}</h1>"]
    if document.subtitle:
        parts.append(f"<p class='sub'>{html.escape(document.subtitle)}</p>")
    parts.append(f"<p>{html.escape(document.introduction)}</p>")
    for s in document.sections:
        parts.append(f"<h2>{html.escape(s.heading)}</h2><p>{html.escape(s.body)}</p>")
        if s.key_takeaway:
            parts.append(f"<p class='take'><strong>Takeaway:</strong> {html.escape(s.key_takeaway)}</p>")
    if document.checklist:
        parts.append("<h2>Checklist</h2><ol>" + "".join(f"<li>{html.escape(c)}</li>" for c in document.checklist) + "</ol>")
    if document.sources:
        parts.append("<h2>Sources</h2><ul>" + "".join(f"<li>{html.escape(u)}</li>" for u in document.sources) + "</ul>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'><style>"
        "body{font-family:Georgia,serif;line-height:1.5;margin:2.5cm}h1{font-size:22pt}"
        "h2{font-size:14pt;margin-top:1.4em}.sub{color:#555;font-size:12pt}.take{color:#333}"
        "</style></head><body>" + "".join(parts) + "</body></html>"
    )


def _guide_pdf(document: Guide) -> bytes:
    try:  # pragma: no cover - depends on optional system libs
        from weasyprint import HTML

        return HTML(string=_guide_html(document)).write_pdf()
    except Exception:
        return _guide_pdf_reportlab(document)


def _guide_pdf_reportlab(document: Guide) -> bytes:
    import io

    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=LETTER, topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    take = ParagraphStyle("take", parent=styles["Normal"], textColor="#333333", spaceBefore=4, alignment=TA_LEFT)

    def esc(text: str) -> str:
        return html.escape(text).replace("\n", "<br/>")

    story = [Paragraph(esc(document.title), styles["Title"])]
    if document.subtitle:
        story.append(Paragraph(esc(document.subtitle), styles["Italic"]))
    story.append(Spacer(1, 12))
    if document.introduction:
        story.append(Paragraph(esc(document.introduction), styles["BodyText"]))
    for s in document.sections:
        story += [Spacer(1, 12), Paragraph(esc(s.heading), styles["Heading2"]),
                  Paragraph(esc(s.body), styles["BodyText"])]
        if s.key_takeaway:
            story.append(Paragraph("<b>Takeaway:</b> " + esc(s.key_takeaway), take))
    if document.checklist:
        story += [Spacer(1, 12), Paragraph("Checklist", styles["Heading2"]),
                  ListFlowable([ListItem(Paragraph(esc(c), styles["BodyText"])) for c in document.checklist],
                               bulletType="1")]
    if document.sources:
        story += [Spacer(1, 12), Paragraph("Sources", styles["Heading2"]),
                  ListFlowable([ListItem(Paragraph(esc(u), styles["BodyText"])) for u in document.sources],
                               bulletType="bullet")]
    doc.build(story)
    return buf.getvalue()
