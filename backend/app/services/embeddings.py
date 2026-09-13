"""Session-scoped semantic retrieval (embeddings + FAISS) for M4 diligence.

Implements the PRD's RAG retrieval layer in local/MVP mode:
- Embeds document chunks with a sentence-transformer (default all-MiniLM-L6-v2).
- Indexes them in an in-memory FAISS IndexFlatIP (cosine via normalised vectors).
- The index is ephemeral: created per request, held only in memory, and dropped
  when the caller releases it — matching the PRD §6.1 "session-scoped, never
  persisted" requirement.

All heavy dependencies (torch, sentence-transformers, faiss) are imported lazily
so importing this module is cheap and the rest of the app runs even if they are
unavailable. Callers should catch ``SemanticUnavailableError`` and fall back to
keyword retrieval.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

from app.core.config import get_settings


class SemanticUnavailableError(RuntimeError):
    """Raised when the embedding model or FAISS cannot be loaded/used."""


_model = None
_model_lock = Lock()


def _load_model():
    """Load and cache the sentence-transformer model (thread-safe, lazy)."""
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:  # pragma: no cover - import environment specific
            raise SemanticUnavailableError(f"sentence-transformers unavailable: {exc}") from exc
        try:
            _model = SentenceTransformer(get_settings().local_embedding_model)
        except Exception as exc:
            raise SemanticUnavailableError(f"Failed to load embedding model: {exc}") from exc
    return _model


def semantic_available() -> bool:
    """Best-effort check that semantic retrieval can run (model + faiss load)."""
    try:
        import faiss  # noqa: F401

        _load_model()
        return True
    except Exception:
        return False


class SemanticIndex:
    """Ephemeral in-memory FAISS index over a set of text chunks."""

    def __init__(self, chunks: list[dict[str, Any]]):
        if not chunks:
            raise SemanticUnavailableError("No chunks to index.")
        try:
            import faiss
            import numpy as np
        except Exception as exc:  # pragma: no cover - import environment specific
            raise SemanticUnavailableError(f"faiss/numpy unavailable: {exc}") from exc

        self._chunks = chunks
        model = _load_model()
        texts = [chunk["text"] for chunk in chunks]
        embeddings = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        embeddings = np.asarray(embeddings, dtype="float32")
        self._dim = embeddings.shape[1]
        self._index = faiss.IndexFlatIP(self._dim)
        self._index.add(embeddings)
        self._np = np
        self._model = model

    def search(self, query: str, top_k: int = 12) -> list[dict[str, Any]]:
        """Return the top-k chunks most semantically similar to the query."""
        vector = self._model.encode([query], normalize_embeddings=True, convert_to_numpy=True)
        vector = self._np.asarray(vector, dtype="float32")
        k = min(top_k, len(self._chunks))
        scores, indices = self._index.search(vector, k)
        results: list[dict[str, Any]] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = dict(self._chunks[idx])
            chunk["similarity"] = float(score)
            results.append(chunk)
        return results

    def rank_for_queries(self, queries: tuple[str, ...] | list[str], top_k: int = 12) -> list[dict[str, Any]]:
        """Aggregate the best similarity across several queries and return top-k chunks."""
        best: dict[int, dict[str, Any]] = {}
        for query in queries:
            for chunk in self.search(query, top_k=top_k):
                key = chunk["page"], chunk["text"][:64]
                idx = hash(key)
                if idx not in best or chunk["similarity"] > best[idx]["similarity"]:
                    best[idx] = chunk
        ranked = sorted(best.values(), key=lambda c: c["similarity"], reverse=True)
        return ranked[:top_k]
