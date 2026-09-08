import asyncio

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app as app_module
from src.contentforge.projects import ProjectProfile, create_project
from src.contentforge.security import RateLimiter, cors_origins, require_api_key

client = TestClient(app_module.app)


def _key(value):
    return asyncio.run(require_api_key(x_api_key=value))


def test_require_api_key_noop_without_env(monkeypatch):
    monkeypatch.delenv("CONTENTFORGE_API_KEY", raising=False)
    _key(None)  # does not raise


def test_require_api_key_enforced_when_set(monkeypatch):
    monkeypatch.setenv("CONTENTFORGE_API_KEY", "secret")
    with pytest.raises(HTTPException) as exc:
        _key("wrong")
    assert exc.value.status_code == 401
    _key("secret")  # correct key: ok


def test_generate_route_locked_when_key_set(monkeypatch):
    create_project(ProjectProfile(slug="p", name="P", audience="a", tone="t", author="x"))
    monkeypatch.setenv("CONTENTFORGE_API_KEY", "secret")

    body = {"topic": "AI tools for teams", "project_slug": "p"}
    assert client.post("/api/generate", json=body).status_code == 401
    # a read route stays open
    assert client.get("/api/projects").status_code == 200
    # correct key gets in (project exists -> 200/queued)
    r = client.post("/api/generate", json=body, headers={"X-API-Key": "secret"})
    assert r.status_code == 200


def test_rate_limiter_blocks_after_max():
    rl = RateLimiter(max_per_minute=2)
    rl.check()
    rl.check()
    with pytest.raises(HTTPException) as exc:
        rl.check()
    assert exc.value.status_code == 429


def test_rate_limiter_disabled_when_zero():
    rl = RateLimiter(max_per_minute=0)
    for _ in range(100):
        rl.check()


def test_cors_origins_default_and_override(monkeypatch):
    monkeypatch.delenv("CONTENTFORGE_CORS_ORIGINS", raising=False)
    assert "http://localhost:8000" in cors_origins()
    monkeypatch.setenv("CONTENTFORGE_CORS_ORIGINS", "https://a.example, https://b.example")
    assert cors_origins() == ["https://a.example", "https://b.example"]
