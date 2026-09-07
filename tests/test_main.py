from datetime import datetime
from pathlib import Path

import pytest

from src.contentforge import main
from src.contentforge.pipelines.base import Document
from src.contentforge.projects import ProjectProfile
from src.contentforge.run_service import RunResult
from src.contentforge.schemas import BlogContent, Section


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
        sections=[Section(heading="Section One", body="Body text.")],
        key_points=["Point one"],
        tags=["AI"],
        sources=[],
    )
    defaults.update(overrides)
    return BlogContent(**defaults)


def test_build_default_inputs_includes_project_fields():
    fixed_now = datetime(2026, 8, 6, 12, 30, 0)
    inputs = main.build_default_inputs("Custom Topic", make_project(), now=fixed_now)

    assert inputs["topic"] == "Custom Topic"
    assert inputs["current_year"] == "2026"
    assert inputs["current_date"] == "2026-08-06"
    assert inputs["current_date_and_time"] == "2026-08-06 12:30:00"
    assert inputs["project_name"] == "Acme Launch"
    assert inputs["audience"] == "solo developers"
    assert inputs["author"] == "Jane Doe"
    assert inputs["category_tags"] == "Productivity, SaaS"
    assert inputs["target_word_count"] == "700"


def test_build_default_inputs_uses_explicit_topic_slug():
    inputs = main.build_default_inputs("Topic", make_project(), topic_slug="custom-slug")
    assert inputs["topic_slug"] == "custom-slug"


def test_run_pipeline_delegates_to_run_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    captured: dict = {}
    post_path = tmp_path / "post.md"
    post_path.write_text("x", encoding="utf-8")

    class FakeService:
        def run_atomic(self, project, topic, *, current_date=None, **kw):
            captured.update(topic=topic, current_date=current_date)
            doc = Document(type="blog_post", content=make_content(title="Pipeline Post"))
            return RunResult(brief=None, documents=[(doc, post_path)])

    monkeypatch.setattr(main, "default_run_service", lambda output_dir: FakeService())

    project = make_project()
    inputs = main.build_default_inputs("Pipeline Topic", project)
    result, output_path = main.run_pipeline(inputs, project, output_dir=tmp_path)

    assert captured["topic"] == "Pipeline Topic"
    assert captured["current_date"] == inputs["current_date"]
    assert output_path == post_path
    assert result.pydantic.title == "Pipeline Post"
