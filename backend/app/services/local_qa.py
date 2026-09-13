from __future__ import annotations

import re
from io import BytesIO
from typing import Any

from app.schemas import LocalQAResponse


class LocalQAError(ValueError):
    pass


def _import_pdf_reader() -> Any:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise LocalQAError("Missing dependency `pypdf`. Install with: pip install pypdf") from exc
    return PdfReader


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(token) > 2]


def _extract_pdf_text(file_bytes: bytes) -> list[dict[str, Any]]:
    PdfReader = _import_pdf_reader()
    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception as exc:
        raise LocalQAError(f"Failed to parse PDF: {exc}") from exc
    pages: list[dict[str, Any]] = []
    for idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append({"page": idx, "text": text})
    if not pages:
        raise LocalQAError("No readable text found in document.")
    return pages


def _extract_text(file_bytes: bytes, filename: str) -> list[dict[str, Any]]:
    if filename.lower().endswith(".pdf"):
        return _extract_pdf_text(file_bytes)
    if filename.lower().endswith(".txt"):
        raw = file_bytes.decode("utf-8", errors="ignore").strip()
        if not raw:
            raise LocalQAError("Text file is empty.")
        return [{"page": 1, "text": raw}]
    raise LocalQAError("Only .pdf and .txt files are supported for local Q&A.")


def _chunk_pages(pages: list[dict[str, Any]], chunk_size: int = 900, overlap: int = 120) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    step = max(1, chunk_size - overlap)
    for page in pages:
        text = page["text"]
        for start in range(0, len(text), step):
            piece = text[start : start + chunk_size].strip()
            if piece:
                chunks.append({"page": page["page"], "text": piece})
    return chunks


def _score_chunk(question_tokens: list[str], chunk_text: str) -> int:
    lowered = chunk_text.lower()
    return sum(lowered.count(token) for token in question_tokens)


def _semantic_top_chunks(chunks: list[dict[str, Any]], question: str, top_k: int) -> list[dict[str, Any]] | None:
    """Semantic retrieval via embeddings + FAISS. Returns None if unavailable so
    the caller can fall back to keyword scoring."""
    try:
        from app.services.embeddings import SemanticIndex, SemanticUnavailableError

        try:
            index = SemanticIndex(chunks)
        except SemanticUnavailableError:
            return None
        return index.search(question, top_k=max(1, top_k))
    except Exception:
        return None


def answer_question_from_document(
    file_bytes: bytes,
    filename: str,
    question: str,
    top_k: int = 4,
) -> LocalQAResponse:
    pages = _extract_text(file_bytes, filename)
    chunks = _chunk_pages(pages)
    q_tokens = _tokenize(question)
    if not q_tokens:
        raise LocalQAError("Question must contain searchable keywords.")

    top_chunks = _semantic_top_chunks(chunks, question, top_k)
    if top_chunks is None:
        # Fallback: keyword frequency scoring.
        scored = [(max(_score_chunk(q_tokens, chunk["text"]), 0), chunk) for chunk in chunks]
        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [chunk for score, chunk in scored[: max(1, top_k)] if score > 0]
        if not top_chunks:
            top_chunks = [chunk for _, chunk in scored[: max(1, top_k)]]

    supporting_quotes: list[str] = []
    for chunk in top_chunks[:5]:
        snippet = re.sub(r"\s+", " ", chunk["text"]).strip()
        if len(snippet) > 220:
            snippet = snippet[:217].rstrip() + "..."
        supporting_quotes.append(f"[Page {chunk['page']}] {snippet}")

    answer = (
        "Based on the uploaded document, the most relevant sections are highlighted in supporting quotes. "
        "Review those clauses directly for final legal interpretation."
    )
    return LocalQAResponse(
        document_name=filename,
        question=question,
        answer=answer,
        supporting_quotes=supporting_quotes,
    )

