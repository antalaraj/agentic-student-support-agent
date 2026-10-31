"""Central configuration. Values are read at call time (not import time) so tests and the
evaluator can point the app at temporary databases by changing environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

try:  # .env is only a local-development convenience
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

APP_NAME = "Intelligent Student Support Agent"
INSTITUTION = "Meridian Institute of Management (FICTIONAL demo institution)"
CONTACT_OFFICE = "Student Services Office (student.services@meridian-demo.example)"

# ---- context-selection budgets (see README: "Context selection") ----
MAX_HISTORY_MESSAGES = 6      # only the most recent turns are sent to the model
MAX_HISTORY_CHARS = 600       # each history message is truncated
MAX_MEMORIES = 3              # at most this many relevant memories are injected
RAG_TOP_K = 3                 # policy chunks retrieved per search
MAX_AGENT_STEPS = 4           # safety limit on agent<->tool loops
MAX_QUERY_CHARS = 1500

PREFERRED_GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
]


def secret(name: str, default=None):
    """Environment variable first, then Streamlit secrets. Never raises if secrets are missing."""
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
    return Path(os.environ.get("DB_PATH") or ROOT / "data" / "student_support.db")


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
    """Cosine-distance cut-off above which a chunk is considered 'not relevant enough'.
    The fallback hashing embedder is lexical, so it needs a different cut-off from MiniLM."""
    override = os.environ.get("RAG_MAX_DISTANCE")
    if override:
        return float(override)
    return 0.62 if "MiniLM" in embedder_name else 0.80
