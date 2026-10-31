"""ChromaDB needs SQLite >= 3.35. Some hosts (e.g. Streamlit Community Cloud) ship an older one.
If the optional `pysqlite3-binary` package is installed, use it instead of the stdlib module.
Import this module BEFORE importing chromadb."""
import sys

try:
    import pysqlite3  # type: ignore

    sys.modules["sqlite3"] = pysqlite3
except ImportError:  # normal on Windows/macOS/most Linux machines
    pass
