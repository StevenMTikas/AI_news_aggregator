from pathlib import Path

import pytest

from src.contentforge import cli
from src.contentforge.projects import ProjectNotFoundError, ProjectProfile


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


# --------------------------------------------------------------------- typer app


from typer.testing import CliRunner  # noqa: E402

from src.contentforge.cli import app  # noqa: E402

runner = CliRunner()


def test_cli_project_lifecycle():
    assert "No projects yet" in runner.invoke(app, ["project", "list"]).output

    r = runner.invoke(app, ["project", "add", "acme", "--name", "Acme", "--audience", "devs",
                            "--tone", "warm", "--author", "Sam"])
    assert r.exit_code == 0 and "created" in r.output

    assert "acme" in runner.invoke(app, ["project", "list"]).output
    assert '"slug": "acme"' in runner.invoke(app, ["project", "show", "acme"]).output

    r = runner.invoke(app, ["project", "rm", "acme", "--yes"])
    assert r.exit_code == 0 and "deleted" in r.output


def test_cli_generate_uses_run_service(monkeypatch, tmp_path):
    from src.contentforge import cli as cli_mod
    from src.contentforge.pipelines.base import Document
    from src.contentforge.run_service import RunResult
    from src.contentforge.schemas import BlogContent, Section

    runner.invoke(app, ["project", "add", "acme", "--name", "Acme", "--audience", "d",
                        "--tone", "t", "--author", "S"])
    captured = {}

    class Svc:
        def run_atomic(self, project, topic, *, artifacts, force_fresh):
            captured.update(topic=topic, artifacts=artifacts, fresh=force_fresh)
            content = BlogContent(title="T", meta_description="m", hook="h",
                                  sections=[Section(heading="A", body="b")], key_points=["k"],
                                  tags=[], sources=[])
            return RunResult(brief=None, documents=[(Document(type="blog_post", content=content), tmp_path / "x.md")],
                             document_ids=["d1"])

    monkeypatch.setattr(cli_mod, "default_run_service", lambda output_dir: Svc())
    r = runner.invoke(app, ["generate", "acme", "AI for teams", "-a", "blog_post", "-a", "linkedin_post", "--fresh"])
    assert r.exit_code == 0
    assert captured == {"topic": "AI for teams", "artifacts": ["blog_post", "linkedin_post"], "fresh": True}


def test_cli_backup(tmp_path, monkeypatch):
    from src.contentforge import db

    r = runner.invoke(app, ["backup"])
    assert r.exit_code == 0 and "backup written" in r.output
    assert (db.db_path().parent / "backups").exists()
