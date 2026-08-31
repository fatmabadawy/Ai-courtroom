"""
backend/app/rag/embeddings.py
────────────────────────────────
Local, self-contained embedding backend for the real RAG implementation.
No paid/hosted API — everything runs on-machine.

Two backends, auto-selected:

  1. SentenceTransformerBackend (preferred) — semantic embeddings via a
     small local model (`all-MiniLM-L6-v2`, ~80MB). Produces stable,
     storable vectors: embed once at ingestion time, compare against a
     freshly embedded query at retrieval time. Requires the model weights
     to be downloaded once (needs internet on first run; cached after).

  2. TfidfBackend (automatic fallback) — pure scikit-learn TF-IDF, fully
     offline, no model download. TRADEOFF: TF-IDF vectors are only
     comparable within the SAME fitted vocabulary, so unlike the
     sentence-transformer backend, this one cannot precompute-and-store a
     stable embedding per chunk at ingest time — retrieve_real.py refits it
     over (case's chunks + query) at query time instead. This is simpler
     and slower per query, but keeps the system fully working even with no
     internet access — appropriate for a demo environment that might not
     have connectivity.

Both backends are exposed through the same `EmbeddingBackend` interface so
callers don't need to know which one is active.
"""

from __future__ import annotations

import logging
from typing import List, Protocol

logger = logging.getLogger(__name__)


class EmbeddingBackend(Protocol):
    name: str
    is_stable: bool  # True if embeddings can be precomputed/stored independently

    def embed(self, texts: List[str]) -> List[List[float]]: ...


class SentenceTransformerBackend:
    name = "sentence-transformers/all-MiniLM-L6-v2"
    is_stable = True

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer("all-MiniLM-L6-v2")

    def embed(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return [v.tolist() for v in vectors]


class TfidfBackend:
    """
    Offline fallback. NOT stable across separate fit() calls — see module
    docstring. `embed()` here fits fresh on whatever `texts` it's given, so
    callers needing cross-call comparability must pass ALL texts (corpus +
    query) together in one call.
    """

    name = "tfidf-offline-fallback"
    is_stable = False

    def embed(self, texts: List[str]) -> List[List[float]]:
        from sklearn.feature_extraction.text import TfidfVectorizer

        if not texts:
            return []
        vectorizer = TfidfVectorizer(stop_words="english", max_features=4096)
        matrix = vectorizer.fit_transform(texts)
        return matrix.toarray().tolist()


_backend: EmbeddingBackend | None = None


def get_backend() -> EmbeddingBackend:
    """
    Lazily construct and cache the embedding backend for this process.
    Tries the semantic model first; falls back to TF-IDF if the model
    can't be loaded (e.g. no internet on first run, no cached weights).
    """
    global _backend
    if _backend is not None:
        return _backend

    try:
        _backend = SentenceTransformerBackend()
        logger.info("RAG embeddings: using %s", _backend.name)
    except Exception as exc:
        logger.warning(
            "SentenceTransformer backend unavailable (%s) — falling back to "
            "offline TF-IDF embeddings. Retrieval quality will be lower "
            "(keyword-overlap based, not semantic) until this is resolved "
            "(usually a one-time model download / network access issue).",
            exc,
        )
        _backend = TfidfBackend()
    return _backend


def cosine_similarity(a: List[float], b: List[float]) -> float:
    import numpy as np

    va, vb = np.array(a), np.array(b)
    denom = (np.linalg.norm(va) * np.linalg.norm(vb)) or 1e-9
    return float(np.dot(va, vb) / denom)
