from pathlib import Path

import pytest

from src.contentforge import projects
from src.contentforge.projects import (
    ProjectNotFoundError,
    ProjectProfile,
    ProjectSlugConflictError,
)


@pytest.fixture(autouse=True)
def isolated_projects_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(projects, "PROJECTS_DIR", tmp_path)


def make_profile(**overrides) -> ProjectProfile:
    defaults = dict(
        slug="acme-launch",
        name="Acme Launch",
        audience="solo developers",
        tone="conversational",
        category_tags=["Productivity", "SaaS"],
        author="Jane Doe",
        target_word_count=700,
        notes="Keep it punchy",
    )
    defaults.update(overrides)
    return ProjectProfile(**defaults)


def test_list_projects_empty_when_no_dir():
    assert projects.list_projects() == []


def test_create_and_get_project_round_trips_all_fields():
    profile = make_profile()
    projects.create_project(profile)

    fetched = projects.get_project("acme-launch")
    assert fetched == profile


def test_create_project_rejects_duplicate_slug():
    projects.create_project(make_profile())
    with pytest.raises(ProjectSlugConflictError):
        projects.create_project(make_profile())


def test_get_project_raises_for_unknown_slug():
    with pytest.raises(ProjectNotFoundError):
        projects.get_project("does-not-exist")


def test_list_projects_returns_all_created():
    projects.create_project(make_profile(slug="a", name="A"))
    projects.create_project(make_profile(slug="b", name="B"))

    slugs = {p.slug for p in projects.list_projects()}
    assert slugs == {"a", "b"}


def test_update_project_changes_fields_but_keeps_slug():
    projects.create_project(make_profile())

    updated = projects.update_project("acme-launch", make_profile(name="Acme Relaunch", tone="playful"))

    assert updated.slug == "acme-launch"
    assert updated.name == "Acme Relaunch"
    assert updated.tone == "playful"
    assert projects.get_project("acme-launch").name == "Acme Relaunch"


def test_update_project_raises_for_unknown_slug():
    with pytest.raises(ProjectNotFoundError):
        projects.update_project("does-not-exist", make_profile())


def test_delete_project_removes_it():
    projects.create_project(make_profile())
    projects.delete_project("acme-launch")

    with pytest.raises(ProjectNotFoundError):
        projects.get_project("acme-launch")


def test_delete_project_raises_for_unknown_slug():
    with pytest.raises(ProjectNotFoundError):
        projects.delete_project("does-not-exist")


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Acme Launch", "acme-launch"),
        ("  Weird   Spacing  ", "weird-spacing"),
        ("Special!!Characters??", "special-characters"),
        ("", "project"),
    ],
)
def test_slugify(name, expected):
    assert projects.slugify(name) == expected
