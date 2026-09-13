import pytest

from app.schemas import CompanyCandidate, TargetScreeningInput
from app.services.target_screening import screen_targets


def _input(**overrides):
    base = dict(sector="Software", geography="United States", min_revenue=20_000_000.0, max_revenue=100_000_000.0)
    base.update(overrides)
    return TargetScreeningInput(**base)


def test_synthetic_universe_is_deterministic_and_ranked():
    a = screen_targets(_input(longlist_size=15))
    b = screen_targets(_input(longlist_size=15))
    assert a.universe_source == "synthetic"
    assert len(a.long_list) == 15
    # Deterministic: same names in the same order across runs.
    assert [r["name"] for r in a.long_list] == [r["name"] for r in b.long_list]
    # Sorted by composite score descending.
    scores = [r["composite_score"] for r in a.long_list]
    assert scores == sorted(scores, reverse=True)
    # Composite scores are within 0..100.
    assert all(0.0 <= s <= 100.0 for s in scores)


def test_shortlist_size_and_ranks():
    result = screen_targets(_input(shortlist_size=5, longlist_size=20))
    assert len(result.short_list) == 5
    assert result.short_list == result.shortlist  # back-compat alias
    assert [r["rank"] for r in result.long_list[:5]] == [1, 2, 3, 4, 5]


def test_provided_candidates_score_by_fit():
    strong = CompanyCandidate(name="Strong Co", revenue=60_000_000.0, ebitda_margin=0.30, revenue_cagr=0.30, ownership="pe_backed")
    weak = CompanyCandidate(name="Weak Co", revenue=2_000_000.0, ebitda_margin=0.02, revenue_cagr=-0.10, ownership="family_owned")
    result = screen_targets(_input(candidates=[weak, strong], target_revenue_cagr=0.10))
    assert result.universe_source == "provided"
    # The stronger fundamentals should rank first.
    assert result.long_list[0]["name"] == "Strong Co"
    assert result.long_list[0]["composite_score"] > result.long_list[1]["composite_score"]


def test_component_weights_sum_into_composite():
    result = screen_targets(_input(candidates=[CompanyCandidate(name="X", revenue=60_000_000.0, ebitda_margin=0.25, revenue_cagr=0.15)]))
    row = result.long_list[0]
    assert row["composite_score"] == pytest.approx(sum(row["score_components"].values()), abs=0.05)


def test_sentiment_distress_vs_momentum_direction():
    result = screen_targets(_input(candidates=[
        CompanyCandidate(name="Grower", revenue=50_000_000.0, ebitda_margin=0.30, revenue_cagr=0.35),
        CompanyCandidate(name="Shrinker", revenue=50_000_000.0, ebitda_margin=0.03, revenue_cagr=-0.20),
    ]))
    rows = {r["name"]: r for r in result.long_list}
    assert rows["Grower"]["momentum_score"] > rows["Shrinker"]["momentum_score"]
    assert rows["Shrinker"]["distress_score"] > rows["Grower"]["distress_score"]
