from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module

client = TestClient(app_module.app)


class FakeResult:
    def __init__(self, raw: str):
        self.raw = raw


def fake_run_pipeline(inputs, output_dir=None):
    output_dir = Path(output_dir or app_module.OUTPUT_DIR)
    output_path = output_dir / "fake-blog-post.md"
    return FakeResult("fake blog content"), output_path


@pytest.fixture(autouse=True)
def fake_api_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("SERPER_API_KEY", "test-serper-key")


def test_read_root_serves_index_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "AI News Aggregator" in response.text or "<html" in response.text.lower()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "timestamp" in body
    assert isinstance(body["active_tasks"], int)


def test_generate_blog_rejects_short_topic():
    response = client.post("/api/generate", json={"topic": "ai"})
    assert response.status_code == 400


def test_generate_blog_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_module, "run_pipeline", fake_run_pipeline)

    response = client.post("/api/generate", json={"topic": "AI tools for small business"})
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    task = app_module.tasks[task_id]
    assert task["status"] == "completed"
    assert task["progress"] == 100
    assert task["result"] == "fake blog content"
    assert task["download_url"] == "/download/fake-blog-post.md"


def test_generate_blog_failure_when_pipeline_raises(monkeypatch: pytest.MonkeyPatch):
    def failing_pipeline(inputs, output_dir=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(app_module, "run_pipeline", failing_pipeline)

    response = client.post("/api/generate", json={"topic": "AI tools for small business"})
    assert response.status_code == 200
    task_id = response.json()["task_id"]

    task = app_module.tasks[task_id]
    assert task["status"] == "failed"
    assert "boom" in task["message"]


def test_get_status_not_found():
    response = client.get("/api/status/does-not-exist")
    assert response.status_code == 404


def test_get_result_not_found():
    response = client.get("/api/result/does-not-exist")
    assert response.status_code == 404


def test_get_result_not_completed(monkeypatch: pytest.MonkeyPatch):
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
