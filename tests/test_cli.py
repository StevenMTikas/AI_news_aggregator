from pathlib import Path

import pytest

from src.ai_news_aggregator import cli
from src.ai_news_aggregator.projects import ProjectNotFoundError, ProjectProfile


class FakeResult:
    pass


def make_project(**overrides) -> ProjectProfile:
    defaults = dict(
        slug="acme-launch",
        name="Acme Launch",
        audience="solo developers",
        tone="conversational",
        category_tags=["Productivity"],
        author="Jane Doe",
        target_word_count=700,
    )
    defaults.update(overrides)
    return ProjectProfile(**defaults)


def test_run_success_prints_banner_and_success(monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path):
    project = make_project()
    fake_result = FakeResult()
    output_path = tmp_path / "post.md"

    monkeypatch.setattr(cli, "get_project", lambda slug: project)
    monkeypatch.setattr(cli, "run_pipeline", lambda inputs, proj: (fake_result, output_path))

    result = cli.run("acme-launch", topic="My Topic")

    assert result is fake_result
    captured = capsys.readouterr()
    assert "My Topic" in captured.out
    assert "SUCCESS" in captured.out
    assert str(output_path) in captured.out


def test_run_unknown_project_raises_runtime_error_with_friendly_output(
    monkeypatch: pytest.MonkeyPatch, capsys
):
    def fake_get_project(slug):
        raise ProjectNotFoundError(slug)

    monkeypatch.setattr(cli, "get_project", fake_get_project)

    with pytest.raises(RuntimeError) as exc_info:
        cli.run("does-not-exist", topic="My Topic")

    assert isinstance(exc_info.value.__cause__, ProjectNotFoundError)
    captured = capsys.readouterr()
    assert "ERROR" in captured.out


def test_run_pipeline_failure_raises_runtime_error_with_friendly_output(
    monkeypatch: pytest.MonkeyPatch, capsys
):
    project = make_project()
    monkeypatch.setattr(cli, "get_project", lambda slug: project)

    def failing_pipeline(inputs, proj):
        raise ValueError("boom")

    monkeypatch.setattr(cli, "run_pipeline", failing_pipeline)

    with pytest.raises(RuntimeError):
        cli.run("acme-launch", topic="My Topic")

    captured = capsys.readouterr()
    assert "ERROR" in captured.out
    assert "boom" in captured.out
