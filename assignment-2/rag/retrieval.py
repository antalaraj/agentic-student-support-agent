"""Retrieve only the most relevant handbook chunks for a query."""
from config import sqlite_compat  # noqa: F401
from config import settings
from rag.embeddings import get_embedder
from rag.ingestion import COLLECTION, get_client, ingest


def _collection():
    client = get_client()
    try:
        col = client.get_collection(COLLECTION)
        if col.count() > 0:
            return col
    except Exception:
        pass
    ingest()
    return client.get_collection(COLLECTION)


def retrieve(query: str, k: int | None = None, category: str | None = None) -> list[dict]:
    """Top-k chunks (optionally filtered by category) whose cosine distance is below the cut-off.
    Returns [] when nothing is relevant enough - the caller must then say the information is unavailable."""
    k = k or settings.RAG_TOP_K
    embedder = get_embedder()
    col = _collection()
    result = col.query(query_embeddings=embedder.embed([query]), n_results=k,
                       where={"category": category} if category else None,
                       include=["documents", "metadatas", "distances"])
    cutoff = settings.max_retrieval_distance(embedder.name)
    hits = []
    for cid, doc, meta, dist in zip(result["ids"][0], result["documents"][0], result["metadatas"][0],
                                    result["distances"][0]):
        if dist <= cutoff:
            hits.append({"chunk_id": cid, "section": meta["section"], "source": meta["source"],
                         "text": doc, "distance": round(float(dist), 4), "relevance": round(1 - float(dist), 4)})
    return hits
