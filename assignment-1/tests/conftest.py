import pytest

from database.seed import seed_students


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Every test gets its own SQLite DB and Chroma directory (nothing touches real app data)."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "hashing")
    from rag.embeddings import get_embedder

    get_embedder.cache_clear()
    seed_students()
    yield


class ScriptedLLM:
    """Fake chat model: returns pre-written AIMessages (or raises exceptions) in order."""
    model_name = "scripted-test-llm"

    def __init__(self, *script):
        self.script, self.calls = list(script), 0

    def bind_tools(self, tools):
        return self

    def invoke(self, messages):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
