import os

import pytest

# FinBERT loads a ~440MB model; skipped by default. Enable with RUN_FINBERT_TESTS=1.
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_FINBERT_TESTS") != "1",
    reason="Set RUN_FINBERT_TESTS=1 to run FinBERT tests (loads the ProsusAI/finbert model).",
)

from app.services.finbert import analyze_texts, score_text


def test_finbert_directional_sentiment():
    positive = score_text("The company reported record revenue and raised full-year guidance.")
    negative = score_text("The firm warned of mounting losses, liquidity concerns, and layoffs.")
    assert positive["label"] == "positive"
    assert negative["label"] == "negative"
    assert positive["signed"] > 0 > negative["signed"]


def test_finbert_aggregate_momentum_vs_distress():
    bullish = analyze_texts([
        "Revenue beat expectations and margins expanded.",
        "The company raised guidance for the year.",
    ])
    bearish = analyze_texts([
        "The company missed estimates and cut its outlook.",
        "Rising debt and executive departures worry investors.",
    ])
    assert bullish["momentum_score"] > bearish["momentum_score"]
    assert bearish["distress_score"] > bullish["distress_score"]
