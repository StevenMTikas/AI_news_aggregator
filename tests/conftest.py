import pytest

from src.contentforge import db


@pytest.fixture(autouse=True)
def isolated_db(tmp_path):
    """Every test gets its own freshly-migrated SQLite database."""
    original = db.db_path()
    db.set_db_path(tmp_path / "test.db")
    db.reset_migration_cache()
    db.init_db()
    yield
    db.set_db_path(original)
    db.reset_migration_cache()


@pytest.fixture(autouse=True)
def fake_api_keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("SERPER_API_KEY", "test-serper-key")
