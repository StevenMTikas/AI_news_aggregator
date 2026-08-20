from datetime import datetime
from pathlib import Path

import pytest

from src.ai_news_aggregator import main
from src.ai_news_aggregator.projects import ProjectProfile
from src.ai_news_aggregator.schemas import BlogContent, Section


class FakeResult:
    def __init__(self, pydantic: BlogContent):
        self.pydantic = pydantic


def make_project(**overrides) -> ProjectProfile:
    defaults = dict(
        slug="acme-launch",
        name="Acme Launch",
        audience="solo developers",
        tone="conversational",
        category_tags=["Productivity", "SaaS"],
        author="Jane Doe",
        target_word_count=700,
    )
    defaults.update(overrides)
    return ProjectProfile(**defaults)


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


def test_build_default_inputs_includes_project_fields():
    fixed_now = datetime(2026, 8, 6, 12, 30, 0)
    project = make_project()
    inputs = main.build_default_inputs("Custom Topic", project, now=fixed_now)

    assert inputs["topic"] == "Custom Topic"
    assert inputs["topic_slug"] == "Custom Topic"
    assert inputs["current_year"] == "2026"
    assert inputs["current_date"] == "2026-08-06"
    assert inputs["current_date_and_time"] == "2026-08-06 12:30:00"
    assert inputs["project_name"] == "Acme Launch"
    assert inputs["audience"] == "solo developers"
    assert inputs["tone"] == "conversational"
    assert inputs["author"] == "Jane Doe"
    assert inputs["category_tags"] == "Productivity, SaaS"
    assert inputs["target_word_count"] == "700"


def test_build_default_inputs_uses_explicit_topic_slug():
    project = make_project()
    inputs = main.build_default_inputs("Topic", project, topic_slug="custom-slug")
    assert inputs["topic_slug"] == "custom-slug"


def test_render_jekyll_markdown_includes_front_matter_and_sections():
    project = make_project()
    content = make_content()

    markdown = main.render_jekyll_markdown(content, project, "2026-08-06")

    assert 'title: "How AI Helps Restaurants"' in markdown
    assert "date: 2026-08-06" in markdown
    assert "categories: [Productivity, SaaS]" in markdown
    assert "author: Jane Doe" in markdown
    assert "## Section One" in markdown
    assert "Body text." in markdown
    assert "> A quote." in markdown
    assert "- Point one" in markdown
    assert "Try it today." in markdown


def test_save_blog_post_writes_file(tmp_path: Path):
    project = make_project()
    result = FakeResult(make_content(title="My Great Post"))

    output_path = main.save_blog_post(result, project, "2026-08-06", output_dir=tmp_path)

    assert output_path.exists()
    assert output_path.name == "2026-08-06-my-great-post-blog-post.md"
    assert "My Great Post" in output_path.read_text(encoding="utf-8")


def test_save_blog_post_creates_output_dir(tmp_path: Path):
    project = make_project()
    nested_dir = tmp_path / "nested" / "output"
    result = FakeResult(make_content())

    output_path = main.save_blog_post(result, project, "2026-08-06", output_dir=nested_dir)

    assert nested_dir.exists()
    assert output_path.parent == nested_dir


def test_save_blog_post_raises_without_structured_output(tmp_path: Path):
    project = make_project()
    result = FakeResult(None)

    with pytest.raises(ValueError):
        main.save_blog_post(result, project, "2026-08-06", output_dir=tmp_path)


def test_run_pipeline_saves_crew_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project = make_project()
    fake_result = FakeResult(make_content(title="Pipeline Post"))
    captured_inputs = {}

    class FakeCrew:
        def kickoff(self, inputs):
            captured_inputs.update(inputs)
            return fake_result

    class FakeAiNewsAggregator:
        def crew(self):
            return FakeCrew()

    monkeypatch.setattr(main, "AiNewsAggregator", FakeAiNewsAggregator)

    inputs = main.build_default_inputs("Pipeline Topic", project)
    result, output_path = main.run_pipeline(inputs, project, output_dir=tmp_path)

    assert result is fake_result
    assert captured_inputs["topic"] == "Pipeline Topic"
    assert captured_inputs["audience"] == "solo developers"
    assert output_path.exists()
    assert output_path.name == f"{inputs['current_date']}-pipeline-post-blog-post.md"
