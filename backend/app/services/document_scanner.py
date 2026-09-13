from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import DocumentScanResult, RiskFlag
from app.services.ai_provider import (
    has_valid_anthropic_key,
    resolve_ai_provider,
    should_use_anthropic,
    should_use_groq,
)
from app.services.anthropic_client import (
    AnthropicAuthenticationError,
    AnthropicClientError,
    generate_structured_output,
)

TARGET_RISK_QUERIES = (
    "change of control anti-assignment consent termination acquisition merger",
    "debt covenant leverage ratio restricted payments additional indebtedness",
    "ongoing pending threatened litigation arbitration claims legal dispute",
    "material adverse change force majeure termination rights penalties",
    "data privacy cybersecurity breach notification liability indemnification",
)


class DocumentScannerError(ValueError):
    pass


class DocumentScannerDependencyError(DocumentScannerError):
    pass


class DocumentScannerConfigurationError(DocumentScannerError):
    pass


class DocumentScannerParsingError(DocumentScannerError):
    pass


class DocumentScannerLLMError(DocumentScannerError):
    pass


@dataclass(frozen=True)
class RiskRule:
    category: str
    severity: str
    explanation: str
    keywords: tuple[str, ...]


RISK_RULES: tuple[RiskRule, ...] = (
    RiskRule(
        category="Change of Control",
        severity="High",
        explanation="This clause can trigger termination, consent, or repricing when ownership changes.",
        keywords=(
            "change of control",
            "anti-assignment",
            "assignment",
            "consent of",
            "acquisition",
            "merger",
        ),
    ),
    RiskRule(
        category="Debt Covenant",
        severity="High",
        explanation="This clause can restrict refinancing, leverage, and post-close capital flexibility.",
        keywords=(
            "debt covenant",
            "leverage ratio",
            "minimum liquidity",
            "restricted payment",
            "additional indebtedness",
            "lender consent",
        ),
    ),
    RiskRule(
        category="Litigation",
        severity="Medium",
        explanation="Disclosed disputes can create closing uncertainty and contingent liabilities.",
        keywords=("litigation", "arbitration", "lawsuit", "claim", "threatened action"),
    ),
    RiskRule(
        category="Termination Rights",
        severity="Medium",
        explanation="Broad termination rights can destabilize key contracts post-signing or post-close.",
        keywords=(
            "termination for convenience",
            "material adverse change",
            "for cause",
            "force majeure",
            "right to terminate",
        ),
    ),
    RiskRule(
        category="Data Privacy & Security",
        severity="Medium",
        explanation="Privacy and cyber obligations can require expensive remediation and indemnities.",
        keywords=(
            "data breach",
            "privacy",
            "cybersecurity",
            "security incident",
            "gdpr",
            "ccpa",
        ),
    ),
)


class _RiskExtractionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    risks: list[RiskFlag] = Field(default_factory=list)


def _import_pdf_reader() -> Any:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentScannerDependencyError(
            "Missing dependency `pypdf`. Install with: pip install pypdf"
        ) from exc
    return PdfReader


def _extract_documents(file_stream: bytes, pdf_reader_cls: Any) -> list[dict[str, Any]]:
    try:
        reader = pdf_reader_cls(BytesIO(file_stream))
    except Exception as exc:
        raise DocumentScannerParsingError(f"Failed to parse PDF: {exc}") from exc

    docs: list[dict[str, Any]] = []
    for page_index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            docs.append({"page": page_index, "text": text})

    if not docs:
        raise DocumentScannerParsingError("No readable text extracted. PDF may be scanned/image-only.")
    return docs


def _chunk_documents(docs: list[dict[str, Any]], chunk_size: int = 1200, overlap: int = 150) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    step = max(1, chunk_size - overlap)
    for doc in docs:
        text = doc["text"]
        for start in range(0, len(text), step):
            piece = text[start : start + chunk_size].strip()
            if piece:
                chunks.append({"page": doc["page"], "text": piece})
    return chunks


def _score_chunk(text: str, query: str) -> int:
    lowered = text.lower()
    return sum(lowered.count(token) for token in query.lower().split())


def _semantic_context(chunks: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]] | None:
    """Semantic (embedding + FAISS) ranking of chunks against the risk queries.
    Returns None when semantic retrieval is unavailable, so the caller falls back
    to keyword scoring."""
    try:
        from app.services.embeddings import SemanticIndex, SemanticUnavailableError

        try:
            index = SemanticIndex(chunks)
        except SemanticUnavailableError:
            return None
        return index.rank_for_queries(TARGET_RISK_QUERIES, top_k=top_k)
    except Exception:
        return None


def _retrieve_relevant_context(chunks: list[dict[str, Any]], top_k: int = 12) -> str:
    semantic = _semantic_context(chunks, top_k)
    if semantic:
        return "\n\n".join(f"[Page {c['page']}]\n{c['text']}" for c in semantic)

    # Fallback: keyword frequency scoring.
    scored: list[tuple[int, dict[str, Any]]] = []
    for chunk in chunks:
        score = 0
        for query in TARGET_RISK_QUERIES:
            score += _score_chunk(chunk["text"], query)
        if score > 0:
            scored.append((score, chunk))

    if not scored:
        fallback = chunks[:top_k]
        return "\n\n".join(f"[Page {c['page']}]\n{c['text']}" for c in fallback)

    scored.sort(key=lambda item: item[0], reverse=True)
    top = [item[1] for item in scored[:top_k]]
    return "\n\n".join(f"[Page {c['page']}]\n{c['text']}" for c in top)


def _normalize_snippet(text: str, max_chars: int = 320) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 3].rstrip() + "..."


def _candidate_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p and len(p.strip()) >= 20]


def _scan_locally(filename: str, docs: list[dict[str, Any]]) -> DocumentScanResult:
    risks: list[RiskFlag] = []
    seen: set[tuple[str, str]] = set()
    sentence_pool = []
    for doc in docs:
        for sentence in _candidate_sentences(doc["text"]):
            sentence_pool.append((doc["page"], sentence))

    for rule in RISK_RULES:
        for page, sentence in sentence_pool:
            lowered = sentence.lower()
            if not any(keyword in lowered for keyword in rule.keywords):
                continue
            quoted = _normalize_snippet(f"[Page {page}] {sentence}")
            key = (rule.category.lower(), quoted.lower())
            if key in seen:
                continue
            seen.add(key)
            risks.append(
                RiskFlag(
                    risk_category=rule.category,
                    severity=rule.severity,
                    quoted_text=quoted,
                    ai_explanation=rule.explanation,
                )
            )
            if len([r for r in risks if r.risk_category == rule.category]) >= 4:
                break

    risks = risks[:20]
    return DocumentScanResult(
        document_name=filename,
        total_risks_found=len(risks),
        risks=risks,
    )


def _scan_with_anthropic(filename: str, chunks: list[dict[str, Any]]) -> DocumentScanResult:
    context_text = _retrieve_relevant_context(chunks)
    system_prompt = (
        "You are an M&A legal due-diligence analyst. Use only provided context. "
        "No hallucinations. Return risk items with direct quotes."
    )
    user_prompt = (
        "Identify material risks: change-of-control, debt covenants, litigation, "
        "termination rights, compliance risk. If no risks, return empty list.\n\n"
        f"Context:\n{context_text}"
    )
    try:
        payload = generate_structured_output(
            output_model=_RiskExtractionPayload,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=1600,
        )
    except AnthropicAuthenticationError as exc:
        raise DocumentScannerConfigurationError(
            f"Anthropic authentication failed: {exc.detail}"
        ) from exc
    except AnthropicClientError as exc:
        raise DocumentScannerLLMError(f"Structured extraction failed: {exc}") from exc
    except Exception as exc:
        raise DocumentScannerLLMError(f"Structured extraction failed: {exc}") from exc

    deduped: list[RiskFlag] = []
    seen_flags: set[tuple[str, str]] = set()
    for risk in payload.risks:
        key = (risk.risk_category.strip().lower(), risk.quoted_text.strip().lower())
        if key in seen_flags:
            continue
        seen_flags.add(key)
        deduped.append(risk)
    return DocumentScanResult(
        document_name=filename,
        total_risks_found=len(deduped),
        risks=deduped,
    )


def _scan_with_groq(filename: str, chunks: list[dict[str, Any]]) -> DocumentScanResult:
    """Free-LLM diligence scan via Groq (JSON mode)."""
    from app.services.groq_client import GroqError, generate_json

    context_text = _retrieve_relevant_context(chunks)
    prompt = (
        "You are an M&A legal due-diligence analyst. Using ONLY the context below, "
        "identify material risks (change-of-control, debt covenants, litigation, termination "
        "rights, compliance/privacy). Return JSON: {\"risks\":[{\"risk_category\":str,"
        "\"severity\":\"High\"|\"Medium\"|\"Low\",\"quoted_text\":str,\"ai_explanation\":str}]}. "
        "quoted_text must be a direct quote from the context. If none, return {\"risks\":[]}.\n\n"
        f"Context:\n{context_text}"
    )
    try:
        payload = generate_json(prompt, system="You are a precise M&A diligence analyst returning only JSON.")
    except GroqError as exc:
        raise DocumentScannerLLMError(f"Groq extraction failed: {exc}") from exc

    deduped: list[RiskFlag] = []
    seen: set[tuple[str, str]] = set()
    for item in payload.get("risks", []) or []:
        try:
            risk = RiskFlag(
                risk_category=str(item.get("risk_category", ""))[:120] or "Risk",
                severity=item.get("severity", "Medium") if item.get("severity") in ("High", "Medium", "Low") else "Medium",
                quoted_text=str(item.get("quoted_text", ""))[:2000] or "(no quote provided)",
                ai_explanation=str(item.get("ai_explanation", ""))[:1200] or "No explanation provided.",
            )
        except Exception:
            continue
        key = (risk.risk_category.lower(), risk.quoted_text.lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(risk)
    return DocumentScanResult(document_name=filename, total_risks_found=len(deduped), risks=deduped)


def process_and_scan_pdf(file_stream: bytes, filename: str) -> DocumentScanResult:
    PdfReader = _import_pdf_reader()
    docs = _extract_documents(file_stream, PdfReader)
    chunks = _chunk_documents(docs)
    provider = resolve_ai_provider()

    if provider == "anthropic" and not has_valid_anthropic_key():
        raise DocumentScannerConfigurationError(
            "Anthropic mode enabled but ANTHROPIC_API_KEY is missing/invalid. "
            "Set AI_PROVIDER=local for free MVP mode or provide a valid key."
        )

    if should_use_groq():
        return _scan_with_groq(filename, chunks)
    if should_use_anthropic():
        return _scan_with_anthropic(filename, chunks)
    return _scan_locally(filename, docs)

