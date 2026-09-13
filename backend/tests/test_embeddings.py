import os

import pytest

from app.services.embeddings import SemanticIndex

# These tests load torch + a sentence-transformer model, which is slow. They are
# skipped by default so the main suite stays fast; enable with RUN_SEMANTIC_TESTS=1.
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SEMANTIC_TESTS") != "1",
    reason="Set RUN_SEMANTIC_TESTS=1 to run embedding/FAISS tests (loads torch + model).",
)


CHUNKS = [
    {"page": 1, "text": "The lease may be terminated by the landlord if the tenant undergoes a change in ownership or corporate restructuring."},
    {"page": 2, "text": "The staff cafeteria serves a hot lunch between noon and two o'clock on weekdays."},
    {"page": 3, "text": "Full-time employees accrue twenty days of paid vacation each calendar year."},
]


def test_semantic_search_finds_conceptually_related_chunk():
    index = SemanticIndex(CHUNKS)
    # Query uses "change of control" phrasing absent verbatim from the text.
    results = index.search("a change of control clause letting a party cancel the agreement", top_k=3)
    assert results[0]["page"] == 1
    assert results[0]["similarity"] > results[-1]["similarity"]


def test_rank_for_queries_returns_ranked_chunks():
    index = SemanticIndex(CHUNKS)
    ranked = index.rank_for_queries(
        ("termination and change of control", "employee vacation benefits"),
        top_k=3,
    )
    assert len(ranked) >= 2
    pages = {c["page"] for c in ranked}
    assert 1 in pages  # change-of-control chunk surfaced
