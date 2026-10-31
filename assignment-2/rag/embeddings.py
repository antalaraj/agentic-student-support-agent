"""Embedding backends.

Primary : Sentence Transformers `all-MiniLM-L6-v2` (384-dim) - used when the model is available.
Fallback: a small deterministic hashing embedder (384-dim). It is purely lexical, needs no download and
          lets the app/tests run offline. Which backend is active is always reported (`backend_name`).
"""
import logging
import math
import os
import zlib
from functools import lru_cache

from config.text_utils import tokenize

logger = logging.getLogger(__name__)
DIM = 384


class HashingEmbedder:
    name = "hashing-fallback-384"

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    @staticmethod
    def _embed_one(text: str) -> list[float]:
        tokens = tokenize(text)
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        vec = [0.0] * DIM
        for f in features:
            h = zlib.crc32(f.encode())
            sign = 1.0 if (h >> 16) & 1 else -1.0
            vec[h % DIM] += sign * (1.0 if "_" not in f else 0.5)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


class MiniLMEmbedder:
    name = "all-MiniLM-L6-v2"

    def __init__(self):
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._model.encode(texts, normalize_embeddings=True).tolist()


@lru_cache(maxsize=1)
def get_embedder():
    """Cached so the model is loaded once per process."""
    if os.environ.get("EMBEDDINGS_BACKEND", "").lower() != "hashing":
        try:
            return MiniLMEmbedder()
        except Exception as exc:  # not installed, no network, etc.
            logger.warning("MiniLM unavailable (%s); using hashing fallback embedder.", type(exc).__name__)
    return HashingEmbedder()


def backend_name() -> str:
    return get_embedder().name
