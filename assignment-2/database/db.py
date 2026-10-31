"""SQLite connection helpers for Assignment 2."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import settings
from database.models import SCHEMA


def get_conn() -> sqlite3.Connection:
    path = settings.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def connection():
    """Open a connection, commit on success, roll back on error, always close."""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Idempotently initialize all database tables."""
    with connection() as conn:
        conn.executescript(SCHEMA)
