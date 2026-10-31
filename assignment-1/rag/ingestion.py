"""Load -> extract -> chunk -> embed -> store in ChromaDB. Ingestion is idempotent: the collection is
rebuilt only when the handbook content or the embedding backend changed."""
import hashlib
import re

from config import sqlite_compat  # noqa: F401  (must precede chromadb import)
import chromadb

from config import settings
from rag.embeddings import get_embedder

COLLECTION = "student_handbook"
MAX_CHUNK_CHARS = 700


def load_text(path) -> str:
    """Read a .txt or .pdf handbook. PDFs are parsed with PyMuPDF."""
    path = str(path)
    if path.lower().endswith(".pdf"):
        try:
            import pymupdf  # PyMuPDF
        except ImportError:  # older PyMuPDF versions
            import fitz as pymupdf

        with pymupdf.open(path) as doc:
            return "\n".join(page.get_text() for page in doc)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def split_into_chunks(text: str) -> list[dict]:
    """Split by '## N. Title [category]' sections, then group clauses up to ~700 characters.
    Each chunk keeps its section title so retrieved evidence can be cited."""
    chunks: list[dict] = []
    sections = re.split(r"^## ", text, flags=re.M)[1:]
    for block in sections:
        header, _, body = block.partition("\n")
        m = re.match(r"(\d+)\.\s*(.*?)\s*\[(\w+)\]\s*$", header.strip())
        number, title, category = (m.group(1), m.group(2), m.group(3)) if m else ("0", header.strip(), "policy")
        current, idx = "", 0
        for line in [l.strip() for l in body.splitlines() if l.strip()]:
            if current and len(current) + len(line) > MAX_CHUNK_CHARS:
                chunks.append(_make_chunk(number, title, category, idx, current))
                current, idx = "", idx + 1
            current = f"{current}\n{line}".strip()
        if current:
            chunks.append(_make_chunk(number, title, category, idx, current))
    return chunks


def _make_chunk(number, title, category, idx, body) -> dict:
    return {"id": f"hb-{number}-{idx}", "section": f"Section {number}: {title}", "category": category,
            "text": f"{title}\n{body}"}


def get_client():
    path = settings.chroma_dir()
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path))


def ingest(force: bool = False) -> dict:
    """Build the vector store if missing/outdated. Returns a small status dict."""
    path = settings.handbook_path()
    text = load_text(path)
    fingerprint = hashlib.sha256(text.encode()).hexdigest()[:16]
    embedder = get_embedder()
    client = get_client()

    if not force:
        try:
            col = client.get_collection(COLLECTION)
            meta = col.metadata or {}
            if meta.get("fingerprint") == fingerprint and meta.get("embedder") == embedder.name and col.count() > 0:
                return {"status": "up_to_date", "chunks": col.count(), "embedder": embedder.name}
        except Exception:
            pass
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    chunks = split_into_chunks(text)
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine", "fingerprint": fingerprint,
                                                         "embedder": embedder.name})
    col.add(ids=[c["id"] for c in chunks], documents=[c["text"] for c in chunks],
            embeddings=embedder.embed([c["text"] for c in chunks]),
            metadatas=[{"section": c["section"], "category": c["category"], "source": path.name} for c in chunks])
    return {"status": "ingested", "chunks": len(chunks), "embedder": embedder.name}
