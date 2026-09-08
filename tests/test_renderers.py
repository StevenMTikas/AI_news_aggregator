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


# --------------------------------------------------------------------- short-form


def test_linkedin_renderer_plain_text_and_first_comment_link():
    from src.contentforge.renderers.social import LinkedInRenderer
    from src.contentforge.schemas import LinkedInPost

    art = LinkedInRenderer().render(
        LinkedInPost(hook="A hook line.", body=["stanza one", "stanza two"], cta="What do you think?",
                     hashtags=["ai", "#restaurants"], link_url="https://ex.test/x"),
        context=CTX,
    )
    text = art.text
    assert "A hook line." in text and "stanza one\n\nstanza two" in text
    assert "#ai #restaurants" in text
    assert "--- first comment ---\nhttps://ex.test/x" in text
    assert art.filename.endswith("-linkedin.txt") and art.mime == "text/plain"
    assert "##" not in text and "*" not in text  # no markdown


def test_linkedin_renderer_body_link_when_configured():
    from src.contentforge.renderers.social import LinkedInRenderer
    from src.contentforge.schemas import LinkedInPost

    text = LinkedInRenderer().render(
        LinkedInPost(hook="h", body=["b"], link_url="https://ex.test/x", link_placement="body"),
    ).text
    assert "first comment" not in text and text.rstrip().endswith("https://ex.test/x")


def test_social_thread_renderer_numbers_posts():
    from src.contentforge.renderers.social import SocialThreadRenderer
    from src.contentforge.schemas import SocialThread

    text = SocialThreadRenderer().render(
        SocialThread(posts=["hook", "middle", "cta"], hashtags=["ai"]), context=CTX
    ).text
    assert text.startswith("1/3 hook") and "2/3 middle" in text and "#ai" in text


def test_repurpose_renderer_groups_by_platform():
    from src.contentforge.renderers.social import RepurposeRenderer
    from src.contentforge.schemas import RepurposePack, Snippet

    text = RepurposeRenderer().render(
        RepurposePack(snippets=[Snippet(platform="x", text="one"), Snippet(platform="x", text="two"),
                                Snippet(platform="linkedin", text="three")]),
    ).text
    assert "## x" in text and "## linkedin" in text and "- one" in text
