"""Module 1 — The Hunt: composite target-screening engine (PRD v3.0 §4.1).

Deterministic, MVP mode (no Bloomberg/CapIQ feed). Scores each candidate on a
0-100 composite built from five weighted components:

    Financial Fit          30  — proximity to the screening criteria
    Growth Trajectory      25  — 3-yr revenue CAGR vs the sector median
    Sector Tailwind        15  — sector growth vs the economy baseline
    Deal Genome Match      20  — cosine similarity to the "ideal target" profile
    Competing-Bid Adj.     10  — Competitive Bid Oracle used as a tiebreaker

It also produces a Sentiment Radar (distress / momentum 0-10) and a Competitive
Bid Oracle probability for each candidate. When no candidates are supplied, a
deterministic synthetic universe is generated so the ranking is reproducible.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

from app.schemas import CompanyCandidate, TargetScreeningInput, TargetScreeningResult

WEIGHTS = {
    "financial_fit": 30.0,
    "growth_trajectory": 25.0,
    "sector_tailwind": 15.0,
    "deal_genome_match": 20.0,
    "competing_bid_adjustment": 10.0,
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _seeded_unit(*parts: Any) -> float:
    """Deterministic pseudo-random float in [0, 1) from the given seed parts."""
    digest = hashlib.md5("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


# --- Component scores (each returns 0..1) -------------------------------------

def _financial_fit(candidate: CompanyCandidate, inp: TargetScreeningInput) -> float:
    lo, hi = inp.min_revenue, inp.max_revenue
    mid = (lo + hi) / 2.0
    half_span = max((hi - lo) / 2.0, 1.0)
    # 1.0 at the midpoint, ~0.5 at the bounds, decaying beyond.
    revenue_fit = _clamp(1.0 - abs(candidate.revenue - mid) / (2.0 * half_span))

    margin_fit = _clamp(0.5 + (candidate.ebitda_margin - inp.ebitda_margin_min) * 2.0)

    if inp.ev_ebitda_max is not None and candidate.ev_ebitda is not None:
        multiple_fit = 1.0 if candidate.ev_ebitda <= inp.ev_ebitda_max else _clamp(inp.ev_ebitda_max / candidate.ev_ebitda)
    else:
        multiple_fit = 0.7  # neutral when not evaluated

    return _clamp(0.5 * revenue_fit + 0.3 * margin_fit + 0.2 * multiple_fit)


def _growth_trajectory(candidate: CompanyCandidate, inp: TargetScreeningInput) -> float:
    median = inp.target_revenue_cagr
    denom = max(abs(median) * 2.0, 0.10)
    return _clamp(0.5 + (candidate.revenue_cagr - median) / denom)


def _sector_tailwind(inp: TargetScreeningInput) -> float:
    baseline = inp.economy_baseline_growth
    denom = max(abs(baseline) * 3.0, 0.03)
    return _clamp(0.5 + (inp.sector_growth_rate - baseline) / denom)


def _deal_genome_match(candidate: CompanyCandidate, inp: TargetScreeningInput) -> float:
    """Cosine similarity between the candidate and the 'ideal acquisition' profile
    derived from the screening criteria."""
    mid_revenue = (inp.min_revenue + inp.max_revenue) / 2.0
    ideal_margin = max(inp.ebitda_margin_min, 0.20)
    scale = max(mid_revenue, 1.0)

    cand_vec = [candidate.revenue / scale, candidate.ebitda_margin, candidate.revenue_cagr]
    ideal_vec = [mid_revenue / scale, ideal_margin, inp.target_revenue_cagr]

    dot = sum(a * b for a, b in zip(cand_vec, ideal_vec))
    norm_a = math.sqrt(sum(a * a for a in cand_vec))
    norm_b = math.sqrt(sum(b * b for b in ideal_vec))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return _clamp(dot / (norm_a * norm_b))


def _sentiment_radar(candidate: CompanyCandidate) -> tuple[float, float]:
    """Return (distress_score, momentum_score), each 0-10."""
    momentum = _clamp(0.5 + candidate.revenue_cagr * 2.0 + (candidate.ebitda_margin - 0.15)) * 10.0
    distress = _clamp(0.5 - candidate.revenue_cagr * 2.0 + (0.10 - candidate.ebitda_margin) * 1.5) * 10.0
    return round(distress, 1), round(momentum, 1)


def _competing_bid_probability(candidate: CompanyCandidate, inp: TargetScreeningInput, momentum: float) -> float:
    """Competitive Bid Oracle — probability a competing bid emerges within 90 days."""
    mid = (inp.min_revenue + inp.max_revenue) / 2.0
    # Mid-size targets attract the most bidders; very large deals have fewer buyers.
    size_factor = 1.0 - _clamp(abs(candidate.revenue - mid) / max(mid, 1.0))
    ownership_factor = {"pe_backed": 0.9, "private": 0.6, "family_owned": 0.4, "public": 0.7}[candidate.ownership]
    return round(_clamp(0.15 + 0.4 * (momentum / 10.0) + 0.25 * size_factor + 0.2 * ownership_factor - 0.2), 4)


def _score_candidate(candidate: CompanyCandidate, inp: TargetScreeningInput) -> dict[str, Any]:
    fin = _financial_fit(candidate, inp)
    growth = _growth_trajectory(candidate, inp)
    tailwind = _sector_tailwind(inp)
    genome = _deal_genome_match(candidate, inp)
    distress, momentum = _sentiment_radar(candidate)
    competing_bid = _competing_bid_probability(candidate, inp, momentum)
    # Competing bids reduce attractiveness (auction risk) — tiebreaker per PRD.
    competing_adj = 1.0 - 0.5 * competing_bid

    components = {
        "financial_fit": round(fin * WEIGHTS["financial_fit"], 2),
        "growth_trajectory": round(growth * WEIGHTS["growth_trajectory"], 2),
        "sector_tailwind": round(tailwind * WEIGHTS["sector_tailwind"], 2),
        "deal_genome_match": round(genome * WEIGHTS["deal_genome_match"], 2),
        "competing_bid_adjustment": round(competing_adj * WEIGHTS["competing_bid_adjustment"], 2),
    }
    composite = round(sum(components.values()), 2)

    return {
        "name": candidate.name,
        "revenue": candidate.revenue,
        "ebitda_margin": candidate.ebitda_margin,
        "revenue_cagr": candidate.revenue_cagr,
        "ownership": candidate.ownership,
        "geography": inp.geography,
        "sector": inp.sector,
        "composite_score": composite,
        "score_components": components,
        "distress_score": distress,
        "momentum_score": momentum,
        "competing_bid_probability": competing_bid,
    }


def _synthetic_universe(inp: TargetScreeningInput) -> list[CompanyCandidate]:
    """Deterministic candidate universe seeded by sector + geography."""
    suffixes = ["Dynamics", "Holdings", "Systems", "Labs", "Partners", "Industries", "Technologies",
                "Group", "Solutions", "Networks", "Analytics", "Automation", "Global", "Ventures", "Works"]
    prefix = inp.sector.split()[0].title() if inp.sector.strip() else "Nova"
    lo, hi = inp.min_revenue, inp.max_revenue
    span = max(hi - lo, 1.0)
    ownerships = ["private", "pe_backed", "public", "family_owned"]

    universe: list[CompanyCandidate] = []
    for i in range(inp.longlist_size):
        seed = (inp.sector, inp.geography, i)
        # Revenue spread across (and slightly beyond) the target band.
        revenue = lo - 0.15 * span + _seeded_unit(*seed, "rev") * 1.3 * span
        revenue = max(revenue, 1_000_000.0)
        margin = _clamp(0.05 + _seeded_unit(*seed, "mgn") * 0.35)
        cagr = -0.05 + _seeded_unit(*seed, "cagr") * 0.45
        ev_ebitda = 6.0 + _seeded_unit(*seed, "ev") * 12.0
        ownership = ownerships[int(_seeded_unit(*seed, "own") * len(ownerships)) % len(ownerships)]
        name = f"{prefix} {suffixes[i % len(suffixes)]}" + ("" if i < len(suffixes) else f" {i // len(suffixes) + 1}")
        universe.append(
            CompanyCandidate(
                name=name,
                revenue=round(revenue, 2),
                ebitda_margin=round(margin, 4),
                revenue_cagr=round(cagr, 4),
                ev_ebitda=round(ev_ebitda, 2),
                ownership=ownership,
            )
        )
    return universe


def screen_targets(inp: TargetScreeningInput) -> TargetScreeningResult:
    if inp.candidates:
        candidates = inp.candidates
        source = "provided"
    else:
        candidates = _synthetic_universe(inp)
        source = "synthetic"

    scored = [_score_candidate(c, inp) for c in candidates]
    scored.sort(key=lambda row: row["composite_score"], reverse=True)
    for rank, row in enumerate(scored, start=1):
        row["rank"] = rank

    short_list = scored[: inp.shortlist_size]

    if short_list:
        avg_distress = sum(r["distress_score"] for r in short_list) / len(short_list)
        avg_momentum = sum(r["momentum_score"] for r in short_list) / len(short_list)
        avg_bid = sum(r["competing_bid_probability"] for r in short_list) / len(short_list)
        sentiment_summary = (
            f"Short list avg momentum {avg_momentum:.1f}/10, avg distress {avg_distress:.1f}/10. "
            f"Top target: {short_list[0]['name']} (score {short_list[0]['composite_score']})."
        )
    else:
        avg_bid = 0.0
        sentiment_summary = "No candidates matched the screening criteria."

    return TargetScreeningResult(
        long_list=scored,
        short_list=short_list,
        shortlist=short_list,
        sentiment_summary=sentiment_summary,
        competing_bid_risk_score=round(_clamp(avg_bid), 4),
        universe_source=source,
        methodology={
            "weights": WEIGHTS,
            "composite": "sum of weighted component scores (0-100)",
            "sentiment": "distress/momentum derived from revenue CAGR and EBITDA margin",
            "competing_bid": "Competitive Bid Oracle probability within 90 days",
        },
    )
