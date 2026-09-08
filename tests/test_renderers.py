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


# --------------------------------------------------------------------- long form


def test_newsletter_renderer_emits_markdown_and_html():
    from src.contentforge.renderers.longform import NewsletterRenderer
    from src.contentforge.schemas import Newsletter, NewsletterItem

    arts = NewsletterRenderer().render(
        Newsletter(subject="This week in restaurant AI", intro="Three things.",
                   items=[NewsletterItem(heading="Bookings", body="No-shows fell 22%.", source_url="https://ex.test/1")],
                   sign_off="Until next week."),
        context=CTX,
    )
    assert [a.mime for a in arts] == ["text/markdown", "text/html"]
    md, page = arts[0].text, arts[1].text
    assert md.startswith("# This week in restaurant AI") and "[Source](https://ex.test/1)" in md
    assert "<h1>This week in restaurant AI</h1>" in page and "<a href=" in page
    assert arts[0].filename.endswith("-newsletter.md") and arts[1].filename.endswith("-newsletter.html")


def test_podcast_renderer_has_cues():
    from src.contentforge.renderers.longform import PodcastScriptRenderer
    from src.contentforge.schemas import PodcastScript, PodcastSegment

    text = PodcastScriptRenderer().render(
        PodcastScript(title="Kitchen AI", hook="Your Friday rush, handled.",
                      segments=[PodcastSegment(cue="SEGMENT 1: bookings", script="AI predicts no-shows.", duration_estimate="~2 min")],
                      outro="Thanks for listening."),
        context=CTX,
    ).text
    assert "Cold open:" in text and "## [SEGMENT 1: bookings]" in text and "~2 min" in text and "[OUTRO]" in text


def test_guide_renderer_produces_a_pdf():
    from src.contentforge.renderers.longform import GuidePdfRenderer
    from src.contentforge.schemas import Guide, GuideSection

    art = GuidePdfRenderer().render(
        Guide(title="The Smart Kitchen Guide", subtitle="For independents", introduction="Why AI now.",
              sections=[GuideSection(heading="Bookings", body="AI cuts no-shows.", key_takeaway="Pilot one tool.")],
              checklist=["Pick a tool", "Run a 30-day trial"], sources=["https://ex.test/1"]),
        context=CTX,
    )
    assert art.mime == "application/pdf"
    assert art.content[:5] == b"%PDF-" and len(art.content) > 800
    assert art.filename == "2026-08-06-the-smart-kitchen-guide-guide.pdf"
