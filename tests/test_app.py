from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module
from src.contentforge import projects
from src.contentforge.projects import ProjectProfile
from src.contentforge.schemas import BlogContent, Section

client = TestClient(app_module.app)


class FakeResult:
    def __init__(self, pydantic: BlogContent):
        self.pydantic = pydantic


def make_content(**overrides) -> BlogContent:
    defaults = dict(
        title="Fake Blog Post",
        meta_description="A short summary.",
        hook="A hook sentence.",
        sections=[Section(heading="Section", body="Body.", pull_quote=None)],
        key_points=["Point one"],
        call_to_action=None,
        tags=["AI"],
        sources=["https://example.com"],
    )
    defaults.update(overrides)
    return BlogContent(**defaults)


def fake_run_pipeline(inputs, project, output_dir=None):
    output_dir = Path(output_dir or app_module.OUTPUT_DIR)
    output_path = output_dir / "fake-blog-post.md"
    return FakeResult(make_content()), output_path


@pytest.fixture(autouse=True)
def fake_api_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("SERPER_API_KEY", "test-serper-key")


@pytest.fixture(autouse=True)
def isolated_projects_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(projects, "PROJECTS_DIR", tmp_path)


@pytest.fixture()
def existing_project() -> ProjectProfile:
    profile = ProjectProfile(
        slug="acme-launch",
        name="Acme Launch",
        audience="solo developers",
        tone="conversational",
        category_tags=["Productivity"],
        author="Jane Doe",
        target_word_count=700,
    )
    projects.create_project(profile)
    return profile


def test_read_root_serves_index_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "ContentForge" in response.text or "<html" in response.text.lower()


def test_read_admin_serves_admin_html():
    response = client.get("/admin")
    assert response.status_code == 200


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "timestamp" in body
    assert isinstance(body["active_tasks"], int)


def test_generate_blog_rejects_short_topic(existing_project):
    response = client.post("/api/generate", json={"topic": "ai", "project_slug": existing_project.slug})
    assert response.status_code == 400


def test_generate_blog_requires_project_slug():
    response = client.post("/api/generate", json={"topic": "AI tools for small business"})
    assert response.status_code == 422


def test_generate_blog_rejects_unknown_project():
    response = client.post(
        "/api/generate", json={"topic": "AI tools for small business", "project_slug": "does-not-exist"}
    )
    assert response.status_code == 400


def test_generate_blog_success(monkeypatch: pytest.MonkeyPatch, existing_project):
    monkeypatch.setattr(app_module, "run_pipeline", fake_run_pipeline)

    response = client.post(
        "/api/generate",
        json={"topic": "AI tools for small business", "project_slug": existing_project.slug},
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    task = app_module.tasks[task_id]
    assert task["status"] == "completed"
    assert task["progress"] == 100
    assert task["result"]["title"] == "Fake Blog Post"
    assert task["download_url"] == "/download/fake-blog-post.md"


def test_generate_blog_failure_when_pipeline_raises(monkeypatch: pytest.MonkeyPatch, existing_project):
    def failing_pipeline(inputs, project, output_dir=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "run_pipeline", failing_pipeline)

    response = client.post(
        "/api/generate",
        json={"topic": "AI tools for small business", "project_slug": existing_project.slug},
    )
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    task = app_module.tasks[task_id]
    assert task["status"] == "failed"
    assert "boom" in task["message"]


def test_run_blog_generation_project_deleted_after_validation(monkeypatch: pytest.MonkeyPatch):
    """
    generate_blog validates the project exists, then queues run_blog_generation as a
    background task. If the project is deleted in the gap between those two steps, the
    background task's own get_project() call should fail gracefully (not crash the
    background task silently) rather than assume the earlier validation still holds.
    """
    task_id = "race-condition-task"
    app_module.tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "Task created, starting soon...",
        "result": None,
        "download_url": None,
        "created_at": "2026-08-06T00:00:00",
    }

    def project_now_missing(slug):
        raise projects.ProjectNotFoundError(slug)

    monkeypatch.setattr(app_module, "get_project", project_now_missing)

    app_module.run_blog_generation(task_id=task_id, topic="AI tools", project_slug="acme-launch")

    task = app_module.tasks[task_id]
    assert task["status"] == "failed"
    assert "acme-launch" in task["message"]


def test_get_status_not_found():
    response = client.get("/api/status/does-not-exist")
    assert response.status_code == 404


def test_get_result_not_found():
    response = client.get("/api/result/does-not-exist")
    assert response.status_code == 404


def test_get_result_returns_structured_content(monkeypatch: pytest.MonkeyPatch, existing_project):
    monkeypatch.setattr(app_module, "run_pipeline", fake_run_pipeline)

    gen_response = client.post(
        "/api/generate",
        json={"topic": "AI tools for small business", "project_slug": existing_project.slug},
    )
    task_id = gen_response.json()["task_id"]

    response = client.get(f"/api/result/{task_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["content"]["title"] == "Fake Blog Post"
    assert body["content"]["sections"][0]["heading"] == "Section"
    assert body["download_url"] == "/download/fake-blog-post.md"


def test_get_result_shape_is_stable(monkeypatch: pytest.MonkeyPatch, existing_project):
    """
    Characterization test: pins the /api/result contract so the architecture rewrite can't
    silently drop or rename a field. If this needs updating, that's an API change -- make it
    deliberately.
    """
    monkeypatch.setattr(app_module, "run_pipeline", fake_run_pipeline)
    task_id = client.post(
        "/api/generate",
        json={"topic": "AI tools for small business", "project_slug": existing_project.slug},
    ).json()["task_id"]

    body = client.get(f"/api/result/{task_id}").json()

    assert set(body) == {"task_id", "content", "download_url"}
    assert set(body["content"]) == {
        "title",
        "meta_description",
        "hook",
        "sections",
        "key_points",
        "call_to_action",
        "tags",
        "sources",
    }
    assert set(body["content"]["sections"][0]) == {"heading", "body", "pull_quote"}


def test_get_result_not_completed():
    task_id = "pending-task"
    app_module.tasks[task_id] = {
        "task_id": task_id,
        "status": "processing",
        "progress": 30,
        "message": "in progress",
        "result": None,
        "download_url": None,
        "created_at": "2026-08-06T00:00:00",
    }

    response = client.get(f"/api/result/{task_id}")
    assert response.status_code == 400


def test_download_file_not_found():
    response = client.get("/download/does-not-exist.md")
    assert response.status_code == 404


def test_download_file_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(app_module, "OUTPUT_DIR", tmp_path)
    file_path = tmp_path / "2026-08-06-my-post-blog-post.md"
    file_path.write_text("---\ntitle: My Post\n---\nHello world", encoding="utf-8")

    response = client.get(f"/download/{file_path.name}")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "Hello world" in response.text


# --- Project CRUD ---

def test_list_projects_empty():
    response = client.get("/api/projects")
    assert response.status_code == 200
    assert response.json() == []


def test_create_project():
    response = client.post(
        "/api/projects",
        json={
            "slug": "acme-launch",
            "name": "Acme Launch",
            "audience": "solo developers",
            "tone": "conversational",
            "category_tags": ["Productivity"],
            "author": "Jane Doe",
            "target_word_count": 700,
        },
    )
    assert response.status_code == 201
    assert response.json()["slug"] == "acme-launch"


def test_create_project_duplicate_slug_conflicts(existing_project):
    response = client.post(
        "/api/projects",
        json={
            "slug": existing_project.slug,
            "name": "Duplicate",
            "audience": "x",
            "tone": "x",
            "author": "x",
        },
    )
    assert response.status_code == 409


def test_get_project(existing_project):
    response = client.get(f"/api/projects/{existing_project.slug}")
    assert response.status_code == 200
    assert response.json()["name"] == "Acme Launch"


def test_get_project_not_found():
    response = client.get("/api/projects/does-not-exist")
    assert response.status_code == 404


def test_update_project(existing_project):
    response = client.put(
        f"/api/projects/{existing_project.slug}",
        json={
            "name": "Acme Relaunch",
            "audience": "solo developers",
            "tone": "playful",
            "category_tags": ["Productivity"],
            "author": "Jane Doe",
            "target_word_count": 700,
        },
    )
    assert response.status_code == 200
    assert response.json()["tone"] == "playful"
    assert response.json()["slug"] == existing_project.slug


def test_update_project_not_found():
    response = client.put(
        "/api/projects/does-not-exist",
        json={"name": "X", "audience": "x", "tone": "x", "author": "x"},
    )
    assert response.status_code == 404


def test_delete_project(existing_project):
    response = client.delete(f"/api/projects/{existing_project.slug}")
    assert response.status_code == 204
    assert client.get(f"/api/projects/{existing_project.slug}").status_code == 404


def test_delete_project_not_found():
    response = client.delete("/api/projects/does-not-exist")
    assert response.status_code == 404
