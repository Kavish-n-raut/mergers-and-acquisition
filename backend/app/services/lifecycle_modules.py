from __future__ import annotations

from app.schemas import TargetScreeningInput, TargetScreeningResult
from app.services.target_screening import screen_targets


def run_module1_target_screening(payload: TargetScreeningInput) -> TargetScreeningResult:
    """M1 Hunt — delegates to the composite target-screening engine."""
    return screen_targets(payload)


def run_module2_approach_summary(target_name: str) -> dict:
    return {
        "target_name": target_name,
        "nda_status": "draft_generated",
        "advisor_conflict_graph_status": "pending_external_feed",
        "normalized_financials_status": "ready_for_module_3",
    }

