from datetime import datetime
from pathlib import Path

import pytest

from src.ai_news_aggregator import main


class FakeResult:
    def __init__(self, raw: str):
        self.raw = raw


def test_slugify_title_extracts_quoted_title():
    content = '---\ntitle: "How AI Helps Restaurants"\ndate: 2026-01-01\n---\nBody'
    assert main.slugify_title(content) == "how-ai-helps-restaurants"


def test_slugify_title_extracts_unquoted_title():
    content = "---\ntitle: How AI Helps Restaurants\n---\nBody"
    assert main.slugify_title(content) == "how-ai-helps-restaurants"


def test_slugify_title_strips_markdown_fence():
    content = '```markdown\n---\ntitle: "Fenced Title"\n---\nBody\n```'
    assert main.slugify_title(content) == "fenced-title"


def test_slugify_title_no_match_returns_default():
    assert main.slugify_title("No front matter here") == "ai-blog-post"


def test_slugify_title_custom_default():
    assert main.slugify_title("No front matter here", default="custom") == "custom"


def test_slugify_title_removes_special_characters_and_truncates():
    long_title = "A" * 60 + "!!! Special & Characters???"
    content = f'title: "{long_title}"'
    result = main.slugify_title(content)
    assert len(result) <= 50
    assert "!" not in result
    assert "&" not in result


def test_build_default_inputs_defaults():
    fixed_now = datetime(2026, 8, 6, 12, 30, 0)
    inputs = main.build_default_inputs(now=fixed_now)
    assert inputs["topic"] == main.DEFAULT_TOPIC
    assert inputs["topic_slug"] == main.DEFAULT_SLUG
    assert inputs["current_year"] == "2026"
    assert inputs["current_date"] == "2026-08-06"
    assert inputs["current_date_and_time"] == "2026-08-06 12:30:00"


def test_build_default_inputs_custom_topic():
    fixed_now = datetime(2026, 1, 1)
    inputs = main.build_default_inputs(topic="Custom Topic", topic_slug="custom-slug", now=fixed_now)
    assert inputs["topic"] == "Custom Topic"
    assert inputs["topic_slug"] == "custom-slug"


def test_save_blog_post_writes_file(tmp_path: Path):
    result = FakeResult('---\ntitle: "My Great Post"\n---\nHello world')
    output_path = main.save_blog_post(result, "2026-08-06", output_dir=tmp_path)

    assert output_path.exists()
    assert output_path.name == "2026-08-06-my-great-post-blog-post.md"
    assert output_path.read_text(encoding="utf-8") == result.raw


def test_save_blog_post_creates_output_dir(tmp_path: Path):
    nested_dir = tmp_path / "nested" / "output"
    result = FakeResult("title: Some Post\nBody text")

    output_path = main.save_blog_post(result, "2026-08-06", output_dir=nested_dir)

    assert nested_dir.exists()
    assert output_path.parent == nested_dir


def test_run_pipeline_saves_crew_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_result = FakeResult('title: "Pipeline Post"\nBody')
    captured_inputs = {}

    class FakeCrew:
        def kickoff(self, inputs):
            captured_inputs.update(inputs)
            return fake_result

    class FakeAiNewsAggregator:
        def crew(self):
            return FakeCrew()

    monkeypatch.setattr(main, "AiNewsAggregator", FakeAiNewsAggregator)

    inputs = main.build_default_inputs(topic="Pipeline Topic")
    result, output_path = main.run_pipeline(inputs, output_dir=tmp_path)

    assert result is fake_result
    assert captured_inputs["topic"] == "Pipeline Topic"
    assert output_path.exists()
    assert output_path.name == f"{inputs['current_date']}-pipeline-post-blog-post.md"
