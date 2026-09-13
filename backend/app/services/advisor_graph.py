"""Module 2 — The Approach: Advisor Conflict Graph (PRD v3.0 §4.2.2).

Deterministic. Builds a node/edge relationship graph from deal participants and
their affiliations, then surfaces:
  - Conflict flags: advisor / counsel / financing roles on OPPOSITE sides that
    share an affiliation (potential channel conflict).
  - Leverage opportunities: management / board people on opposite sides that
    share an affiliation (an existing personal relationship to exploit).
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from app.schemas import AdvisorGraphInput

_ADVISORY_ROLES = {"advisor", "counsel", "financing_bank"}


def build_advisor_conflict_graph(inp: AdvisorGraphInput) -> dict[str, Any]:
    participants = inp.participants

    # Nodes: every participant, plus every distinct affiliation entity.
    nodes: list[dict[str, Any]] = []
    for p in participants:
        nodes.append({"id": f"person:{p.name}", "label": p.name, "type": "person", "role": p.role, "side": p.side})

    affiliation_members: dict[str, list[Any]] = {}
    for p in participants:
        for aff in p.affiliations:
            affiliation_members.setdefault(aff, []).append(p)

    for aff in affiliation_members:
        nodes.append({"id": f"firm:{aff}", "label": aff, "type": "firm"})

    # Edges: person -> affiliation.
    edges: list[dict[str, str]] = []
    for p in participants:
        for aff in p.affiliations:
            edges.append({"source": f"person:{p.name}", "target": f"firm:{aff}"})

    conflict_flags: list[dict[str, Any]] = []
    leverage_opportunities: list[dict[str, Any]] = []

    for aff, members in affiliation_members.items():
        # Only relationships that cross the buyer/target divide are interesting.
        for a, b in combinations(members, 2):
            sides = {a.side, b.side}
            if not ({"buyer", "target"} <= sides):
                continue
            if a.role in _ADVISORY_ROLES or b.role in _ADVISORY_ROLES:
                conflict_flags.append({
                    "affiliation": aff,
                    "parties": [a.name, b.name],
                    "roles": [a.role, b.role],
                    "sides": [a.side, b.side],
                    "description": (
                        f"{a.name} ({a.role}, {a.side}) and {b.name} ({b.role}, {b.side}) both connect through {aff} "
                        f"— potential channel conflict."
                    ),
                })
            else:
                leverage_opportunities.append({
                    "affiliation": aff,
                    "parties": [a.name, b.name],
                    "roles": [a.role, b.role],
                    "sides": [a.side, b.side],
                    "description": (
                        f"{a.name} ({a.side}) and {b.name} ({b.side}) share a connection through {aff} "
                        f"— existing relationship that can be leveraged."
                    ),
                })

    return {
        "nodes": nodes,
        "edges": edges,
        "conflict_flags": conflict_flags,
        "leverage_opportunities": leverage_opportunities,
        "summary": {
            "participants": len(participants),
            "affiliations": len(affiliation_members),
            "conflicts": len(conflict_flags),
            "leverage_opportunities": len(leverage_opportunities),
        },
    }
