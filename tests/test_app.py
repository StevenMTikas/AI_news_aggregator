from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import app as app_module
from src.contentforge.db import documents as doc_store
from src.contentforge.db import runs as run_store
from src.contentforge.projects import ProjectProfile, create_project
from src.contentforge.schemas import BlogContent, Section

client = TestClient(app_module.app)


def make_content(**overrides) -> BlogContent:
    defaults = dict(
        title="Fake Blog Post",
        meta_description="A short summary.",
        hook="A hook sentence.",
        sections=[Section(heading="Section", body="Body.")],
        key_points=["Point one"],
        tags=["AI"],
        sources=[],
    )
    defaults.update(overrides)
    return BlogContent(**defaults)


class FakeService:
    """Stands in for RunService: writes a document row + completes the run, no API calls."""

    def __init__(self, output_dir):
        self.output_dir = Path(output_dir)

    def run_atomic(self, project, topic, *, run_id, topic_slug=None, current_date=None, **kw):
        content = make_content()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / "fake-blog-post.md"
        path.write_text("---\ntitle: Fake\n---\n", encoding="utf-8")
        doc_store.save_document(
            project_slug=project.slug, doc_type="blog_post", title=content.title,
            content_json=content.model_dump_json(), run_id=run_id,
            rendered_path=str(path), rendered_format="markdown",
        )
        run_store.update_run(run_id, status="completed", progress=100, message="Done.")
        return SimpleNamespace(run_id=run_id)

    def render_document(self, document_id, **kw):
        from src.contentforge.providers.fakes import FakeLLMProvider
        from src.contentforge.providers.serper import NullSearchProvider
        from src.contentforge.run_service import RunService

        real = RunService(
            llm=FakeLLMProvider(), search_provider=NullSearchProvider(), output_dir=self.output_dir
        )
        return real.render_document(document_id, **kw)


@pytest.fixture
def fake_service(monkeypatch):
    monkeypatch.setattr(app_module, "default_run_service", lambda output_dir: FakeService(output_dir))


@pytest.fixture()
def existing_project() -> ProjectProfile:
    profile = ProjectProfile(
        slug="acme-launch", name="Acme Launch", audience="solo developers",
        tone="conversational", category_tags=["Productivity"], author="Jane Doe",
        target_word_count=700,
    )
    create_project(profile)
    return profile


# --------------------------------------------------------------------- pages / health


def test_read_root_serves_index_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "ContentForge" in response.text or "<html" in response.text.lower()


def test_read_admin_serves_admin_html():
    assert client.get("/admin").status_code == 200


def test_health_check():
    body = client.get("/health").json()
    assert body["status"] == "healthy"
    assert isinstance(body["active_tasks"], int)


# --------------------------------------------------------------------- generate


def test_generate_blog_rejects_short_topic(existing_project):
    r = client.post("/api/generate", json={"topic": "ai", "project_slug": existing_project.slug})
    assert r.status_code == 400


def test_generate_blog_requires_project_slug():
    r = client.post("/api/generate", json={"topic": "AI tools for small business"})
    assert r.status_code == 422


def test_generate_blog_rejects_unknown_project():
    r = client.post("/api/generate", json={"topic": "AI tools", "project_slug": "nope"})
    assert r.status_code == 400


def test_generate_blog_success(fake_service, existing_project):
    r = client.post("/api/generate", json={"topic": "AI tools for small business", "project_slug": existing_project.slug})
    assert r.status_code == 200
    task_id = r.json()["task_id"]

    run = run_store.get_run(task_id)
    assert run.status == "completed" and run.progress == 100

    status = client.get(f"/api/status/{task_id}").json()
    assert status["result"]["title"] == "Fake Blog Post"
    assert status["download_url"] == "/download/fake-blog-post.md"


def test_generate_blog_failure_marks_run_failed(monkeypatch, existing_project):
    class Boom:
        def __init__(self, output_dir):
            pass

        def run_atomic(self, *a, **k):
            raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "default_run_service", lambda output_dir: Boom(output_dir))
    task_id = client.post(
        "/api/generate", json={"topic": "AI tools", "project_slug": existing_project.slug}
    ).json()["task_id"]

    run = run_store.get_run(task_id)
    assert run.status == "failed" and "boom" in run.message


def test_run_blog_generation_project_deleted_after_validation(monkeypatch):
    run = run_store.create_run(project_slug="acme-launch", topic="AI tools")

    from src.contentforge.projects import ProjectNotFoundError

    monkeypatch.setattr(app_module, "get_project", lambda slug: (_ for _ in ()).throw(ProjectNotFoundError(slug)))
    app_module.run_blog_generation(run_id=run.id, topic="AI tools", project_slug="acme-launch")

    reloaded = run_store.get_run(run.id)
    assert reloaded.status == "failed" and "acme-launch" in reloaded.message


# --------------------------------------------------------------------- status / result


def test_get_status_not_found():
    assert client.get("/api/status/nope").status_code == 404


def test_get_result_not_found():
    assert client.get("/api/result/nope").status_code == 404


def test_get_result_shape_is_stable(fake_service, existing_project):
    """Characterization: the /api/result contract stays put across the rewrite."""
    task_id = client.post(
        "/api/generate", json={"topic": "AI tools for small business", "project_slug": existing_project.slug}
    ).json()["task_id"]

    body = client.get(f"/api/result/{task_id}").json()
    assert set(body) == {"task_id", "content", "download_url"}
    assert set(body["content"]) == {
        "title", "meta_description", "hook", "sections", "key_points",
        "call_to_action", "tags", "sources",
    }
    assert set(body["content"]["sections"][0]) == {"heading", "body", "pull_quote"}


def test_get_result_not_completed():
    run = run_store.create_run(project_slug="acme-launch", topic="AI tools")
    run_store.update_run(run.id, status="running")
    assert client.get(f"/api/result/{run.id}").status_code == 400


# --------------------------------------------------------------------- run history


def test_list_runs_and_run_documents(fake_service, existing_project):
    task_id = client.post(
        "/api/generate", json={"topic": "AI tools for small business", "project_slug": existing_project.slug}
    ).json()["task_id"]

    runs = client.get("/api/runs").json()
    assert any(r["id"] == task_id and r["status"] == "completed" for r in runs)

    docs = client.get(f"/api/runs/{task_id}/documents").json()
    assert docs[0]["type"] == "blog_post"
    assert docs[0]["download_url"] == "/download/fake-blog-post.md"


def test_render_document_endpoint(fake_service, existing_project, monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "OUTPUT_DIR", tmp_path)
    task_id = client.post(
        "/api/generate", json={"topic": "AI tools for small business", "project_slug": existing_project.slug}
    ).json()["task_id"]
    doc_id = client.get(f"/api/runs/{task_id}/documents").json()[0]["id"]

    r = client.post(f"/api/documents/{doc_id}/render")
    assert r.status_code == 200 and r.json()["download_url"].startswith("/download/")


# --------------------------------------------------------------------- download


def test_download_file_not_found():
    assert client.get("/download/nope.md").status_code == 404


def test_download_file_success(monkeypatch, tmp_path):
    monkeypatch.setattr(app_module, "OUTPUT_DIR", tmp_path)
    (tmp_path / "post.md").write_text("Hello world", encoding="utf-8")
    r = client.get("/download/post.md")
    assert r.status_code == 200 and "Hello world" in r.text


# --------------------------------------------------------------------- project CRUD


def test_list_projects_empty():
    assert client.get("/api/projects").json() == []


def test_create_project():
    r = client.post("/api/projects", json={
        "slug": "acme-launch", "name": "Acme Launch", "audience": "solo developers",
        "tone": "conversational", "category_tags": ["Productivity"], "author": "Jane Doe",
        "target_word_count": 700,
    })
    assert r.status_code == 201 and r.json()["slug"] == "acme-launch"


def test_create_project_duplicate_slug_conflicts(existing_project):
    r = client.post("/api/projects", json={
        "slug": existing_project.slug, "name": "Dup", "audience": "x", "tone": "x", "author": "x",
    })
    assert r.status_code == 409


def test_get_project(existing_project):
    assert client.get(f"/api/projects/{existing_project.slug}").json()["name"] == "Acme Launch"


def test_get_project_not_found():
    assert client.get("/api/projects/nope").status_code == 404


def test_update_project(existing_project):
    r = client.put(f"/api/projects/{existing_project.slug}", json={
        "name": "Acme Relaunch", "audience": "solo developers", "tone": "playful",
        "category_tags": ["Productivity"], "author": "Jane Doe", "target_word_count": 700,
    })
    assert r.status_code == 200 and r.json()["tone"] == "playful"


def test_update_project_not_found():
    r = client.put("/api/projects/nope", json={"name": "X", "audience": "x", "tone": "x", "author": "x"})
    assert r.status_code == 404


def test_delete_project(existing_project):
    assert client.delete(f"/api/projects/{existing_project.slug}").status_code == 204
    assert client.get(f"/api/projects/{existing_project.slug}").status_code == 404


def test_delete_project_not_found():
    assert client.delete("/api/projects/nope").status_code == 404
