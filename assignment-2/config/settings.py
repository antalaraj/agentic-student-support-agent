"""Central configuration for Assignment 2 (Safe and Production-Aware Student Support Agent)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

APP_NAME = "Intelligent Student Support Agent (Production & Security Edition)"
INSTITUTION = "Meridian Institute of Management (FICTIONAL demo institution)"
CONTACT_OFFICE = "Student Services & Financial Aid Office (student.services@meridian-demo.example)"

# ---- Context-selection budgets ----
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_CHARS = 600
MAX_MEMORIES = 3
RAG_TOP_K = 3
MAX_AGENT_STEPS = 4
MAX_QUERY_CHARS = 1500

# ---- Security & Authentication settings ----
AUTH_PASSWORD_MIN_LENGTH = 8
SESSION_COOKIE_NAME = "secure_student_session"
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_ROLE = "admin"
DEFAULT_STUDENT_ROLE = "student"

PREFERRED_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]


def secret(name: str, default=None):
    """Environment variable first, then Streamlit secrets. Never raises if missing."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        import streamlit as st

        if name in st.secrets:
            return st.secrets[name]
    except Exception:
        pass
    return default


def db_path() -> Path:
    return Path(os.environ.get("DB_PATH") or ROOT / "data" / "student_support_secure.db")


def chroma_dir() -> Path:
    return Path(os.environ.get("CHROMA_DIR") or ROOT / "data" / "chroma")


def handbook_path() -> Path:
    return Path(os.environ.get("HANDBOOK_PATH") or ROOT / "data" / "student_handbook.txt")


def students_json_path() -> Path:
    return ROOT / "data" / "sample_students.json"


def groq_api_key():
    return secret("GROQ_API_KEY")


def groq_model() -> str:
    return secret("GROQ_MODEL") or PREFERRED_GROQ_MODELS[0]


def max_retrieval_distance(embedder_name: str) -> float:
    override = os.environ.get("RAG_MAX_DISTANCE")
    if override:
        return float(override)
    return 0.62 if "MiniLM" in embedder_name else 0.80
