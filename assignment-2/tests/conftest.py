"""Pytest configuration and isolated fixtures for Assignment 2."""
import json
from pathlib import Path

import pytest

from auth.models import AuthUser
from auth.service import authenticate_user, create_user
from database.db import connection, init_db
from database.seed import seed_database


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate database, vector store, and environment variables for every test."""
    db_file = tmp_path / "test_secure.db"
    chroma_dir = tmp_path / "test_chroma"
    monkeypatch.setenv("DB_PATH", str(db_file))
    monkeypatch.setenv("CHROMA_DIR", str(chroma_dir))
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "hashing")

    # Clear graph cache
    from agent.graph import _GRAPH_CACHE
    _GRAPH_CACHE.clear()

    # Seed isolated database
    seed_database()

    yield {"db_file": db_file, "chroma_dir": chroma_dir}


@pytest.fixture
def student_user_a() -> AuthUser:
    """Authenticated Student A (Diya Nair - MIM25002)."""
    user = authenticate_user("diya", "Student@123")
    assert user is not None, "Failed to authenticate student Diya"
    return user


@pytest.fixture
def student_user_b() -> AuthUser:
    """Authenticated Student B (Aarav Mehta - MIM25001)."""
    user = authenticate_user("aarav", "Student@123")
    assert user is not None, "Failed to authenticate student Aarav"
    return user


@pytest.fixture
def admin_user() -> AuthUser:
    """Authenticated Administrator."""
    user = authenticate_user("admin", "Admin@12345")
    assert user is not None, "Failed to authenticate admin"
    return user
