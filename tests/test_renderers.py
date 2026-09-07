from src.contentforge.renderers.jekyll import JekyllMarkdownRenderer
from src.contentforge.schemas import BlogContent, Section

RENDERER = JekyllMarkdownRenderer()

CTX = {"author": "Jane Doe", "category_tags": ["Productivity", "SaaS"], "current_date": "2026-08-06"}


def make_content(**overrides) -> BlogContent:
    defaults = dict(
        title="How AI Helps Restaurants",
        meta_description="A short summary of the post.",
        hook="Restaurants are changing fast.",
        sections=[Section(heading="Section One", body="Body text.", pull_quote="A quote.")],
        key_points=["Point one", "Point two"],
        call_to_action="Try it today.",
        tags=["AI", "Restaurants"],
        sources=["https://example.com"],
    )
    defaults.update(overrides)
    return BlogContent(**defaults)


def test_render_includes_front_matter_body_and_sources():
    md = RENDERER.render(make_content(), context=CTX).text

    assert 'title: "How AI Helps Restaurants"' in md
    assert 'description: "A short summary of the post."' in md
    assert "date: 2026-08-06" in md
    assert "categories: [Productivity, SaaS]" in md
    assert "tags: [AI, Restaurants]" in md
    assert "author: Jane Doe" in md
    assert "## Section One" in md
    assert "> A quote." in md
    assert "- Point one" in md
    assert "Try it today." in md
    assert "## Sources" in md
    assert "- https://example.com" in md


def test_render_omits_sources_section_when_empty():
    md = RENDERER.render(make_content(sources=[]), context=CTX).text
    assert "## Sources" not in md


def test_render_escapes_quotes_in_front_matter():
    md = RENDERER.render(
        make_content(title='The "Best" AI Tools', meta_description='Why they call it "smart"'),
        context=CTX,
    ).text
    assert r'title: "The \"Best\" AI Tools"' in md
    assert r'description: "Why they call it \"smart\""' in md


def test_render_filename_uses_date_and_title_slug():
    artifact = RENDERER.render(make_content(title="My Great Post"), context=CTX)
    assert artifact.filename == "2026-08-06-my-great-post-blog-post.md"
    assert artifact.mime == "text/markdown"
