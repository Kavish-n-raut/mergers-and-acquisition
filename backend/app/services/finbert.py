"""FinBERT financial-sentiment scoring (ProsusAI/finbert).

The PRD's Sentiment Radar (E2) calls for FinBERT sentiment over news / earnings
text. FinBERT is a free, finance-tuned model on Hugging Face; this wraps it and
turns a batch of texts (e.g. company headlines from Finnhub) into the platform's
distress / momentum signals.

The model (~440MB) downloads on first use and is cached thereafter. All heavy
imports are lazy so the app runs without it; callers catch FinBertUnavailableError
and fall back to the deterministic financial-ratio sentiment.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

from app.core.config import get_settings


class FinBertUnavailableError(RuntimeError):
    pass


_classifier = None
_lock = Lock()


def _load_classifier():
    global _classifier
    if _classifier is not None:
        return _classifier
    with _lock:
        if _classifier is not None:
            return _classifier
        try:
            from transformers import pipeline
        except Exception as exc:  # pragma: no cover - import environment specific
            raise FinBertUnavailableError(f"transformers unavailable: {exc}") from exc
        try:
            _classifier = pipeline("text-classification", model=get_settings().finbert_model)
        except Exception as exc:
            raise FinBertUnavailableError(f"Failed to load FinBERT model: {exc}") from exc
    return _classifier


def finbert_available() -> bool:
    try:
        _load_classifier()
        return True
    except Exception:
        return False


def _signed(label: str, score: float) -> float:
    label = label.lower()
    if label == "positive":
        return score
    if label == "negative":
        return -score
    return 0.0


def score_text(text: str) -> dict[str, Any]:
    clf = _load_classifier()
    result = clf(text[:512])[0]
    label = str(result["label"]).lower()
    score = float(result["score"])
    return {"label": label, "confidence": round(score, 4), "signed": round(_signed(label, score), 4)}


def analyze_texts(texts: list[str]) -> dict[str, Any]:
    """Aggregate FinBERT sentiment across texts into distress / momentum (0-10)."""
    clean = [t for t in (t.strip() for t in texts) if t]
    if not clean:
        raise FinBertUnavailableError("No non-empty texts to analyze.")

    scored = [score_text(t) for t in clean]
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for s in scored:
        counts[s["label"]] = counts.get(s["label"], 0) + 1

    avg_signed = sum(s["signed"] for s in scored) / len(scored)  # in [-1, 1]
    momentum_score = round(max(0.0, min(10.0, 5.0 * (1.0 + avg_signed))), 2)
    distress_score = round(max(0.0, min(10.0, 5.0 * (1.0 - avg_signed))), 2)

    return {
        "analyzed": len(scored),
        "average_signed_sentiment": round(avg_signed, 4),
        "distress_score": distress_score,
        "momentum_score": momentum_score,
        "label_counts": counts,
        "model": get_settings().finbert_model,
        "per_text": [
            {"text": t[:160], **s} for t, s in zip(clean, scored)
        ][:50],
    }
