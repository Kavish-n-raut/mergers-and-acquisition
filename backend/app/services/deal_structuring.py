from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat

from app.schemas import DealStructureInput, DealStructureOutput, RiskFlag
from app.services.ai_provider import has_valid_anthropic_key, resolve_ai_provider, should_use_anthropic
from app.services.anthropic_client import (
    AnthropicAuthenticationError,
    AnthropicClientError,
    generate_structured_output,
)


class DealStructuringError(ValueError):
    pass


class DealStructuringConfigurationError(DealStructuringError):
    pass


class DealStructuringLLMError(DealStructuringError):
    pass


class _DealStructureLLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    recommended_structure: Literal[
        "All Cash",
        "Stock Swap",
        "LBO",
        "Cash + Earn-out",
        "Hybrid",
    ]
    tax_efficiency_score: StrictFloat = Field(..., ge=1.0, le=10.0)
    debt_capacity_warning: bool
    structuring_rationale: str = Field(..., min_length=20, max_length=2000)
    stock_consideration_pct: StrictFloat = Field(..., ge=0.0, le=1.0)


def calculate_dilution(acquirer_market_cap: float, target_ev: float, stock_pct: float) -> float:
    if acquirer_market_cap <= 0:
        raise ValueError("acquirer_market_cap must be positive.")
    if target_ev < 0:
        raise ValueError("target_ev cannot be negative.")
    if not 0 <= stock_pct <= 1:
        raise ValueError("stock_pct must be between 0 and 1.")

    equity_issued = target_ev * stock_pct
    if equity_issued <= 0:
        return 0.0
    dilution = (equity_issued / (acquirer_market_cap + equity_issued)) * 100.0
    return round(dilution, 2)


def _risk_summary(risks: list[RiskFlag]) -> str:
    if not risks:
        return "No major legal risks identified."
    return "\n".join(
        f"{i}. [{r.severity}] {r.risk_category}: {r.ai_explanation}"
        for i, r in enumerate(risks, start=1)
    )


def _contains_token(text: str, *tokens: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def _deterministic_structure(inputs: DealStructureInput) -> DealStructureOutput:
    target_ev = float(inputs.valuation_data.enterprise_value)
    acq_cap = float(inputs.acquirer_market_cap)
    size_ratio = target_ev / acq_cap
    high_risk_count = sum(1 for r in inputs.risk_flags if r.severity == "High")
    medium_risk_count = sum(1 for r in inputs.risk_flags if r.severity == "Medium")

    debt_covenant_risk = any(
        _contains_token(r.risk_category, "debt covenant", "leverage", "indebtedness")
        or _contains_token(r.ai_explanation, "debt", "covenant", "lender")
        for r in inputs.risk_flags
    )
    litigation_risk = any(
        _contains_token(r.risk_category, "litigation", "claim", "arbitration")
        for r in inputs.risk_flags
    )
    ebitda = float(inputs.valuation_data.ebitda or 0.0)

    if high_risk_count >= 2 or litigation_risk:
        structure = "Cash + Earn-out"
        stock_pct = 0.15
        tax_score = 7.2
        rationale = (
            "Risk profile is elevated, so deferring a portion of consideration as an earn-out "
            "helps protect downside while preserving transaction momentum."
        )
    elif debt_covenant_risk:
        structure = "Stock Swap" if size_ratio <= 0.40 else "Hybrid"
        stock_pct = 1.0 if structure == "Stock Swap" else 0.60
        tax_score = 8.1
        rationale = (
            "Debt covenants reduce safe leverage capacity; equity-heavy consideration lowers financing stress "
            "and keeps covenant headroom intact."
        )
    elif size_ratio >= 0.60:
        structure = "Hybrid"
        stock_pct = 0.50
        tax_score = 7.5
        rationale = (
            "Target size is material relative to acquirer value, so a hybrid mix balances dilution and cash "
            "while preserving flexibility."
        )
    elif ebitda > 0 and high_risk_count == 0 and medium_risk_count <= 1 and size_ratio <= 0.30:
        structure = "LBO"
        stock_pct = 0.0
        tax_score = 6.8
        rationale = (
            "Positive EBITDA with manageable risk supports prudent leverage usage and can improve return profile "
            "without meaningful equity dilution."
        )
    elif size_ratio <= 0.20:
        structure = "Stock Swap"
        stock_pct = 1.0
        tax_score = 8.4
        rationale = (
            "Acquirer is materially larger than target, making equity consideration efficient for liquidity "
            "preservation and integration funding."
        )
    else:
        structure = "All Cash"
        stock_pct = 0.0
        tax_score = 6.9
        rationale = (
            "Moderate risk and transaction size favor execution certainty via cash consideration with minimal "
            "complexity in post-close earn-out administration."
        )

    debt_capacity_warning = debt_covenant_risk or size_ratio > 0.50 or structure == "LBO"
    dilution = calculate_dilution(acq_cap, target_ev, stock_pct)
    return DealStructureOutput(
        recommended_structure=structure,
        tax_efficiency_score=round(tax_score, 2),
        debt_capacity_warning=debt_capacity_warning,
        structuring_rationale=rationale,
        stock_consideration_pct=round(stock_pct, 4),
        estimated_dilution_pct=dilution,
    )


def _anthropic_structure(inputs: DealStructureInput) -> DealStructureOutput:
    target_ev = inputs.valuation_data.enterprise_value
    ebitda = inputs.valuation_data.ebitda
    risk_summary = _risk_summary(inputs.risk_flags)
    system_prompt = (
        "You are an M&A structuring advisor. Recommend one structure among "
        "All Cash, Stock Swap, LBO, Cash + Earn-out, Hybrid. "
        "Set stock_consideration_pct coherently with structure."
    )
    human_prompt = (
        f"Target EV: {target_ev:,.2f}\n"
        f"Target EBITDA: {'Not provided' if ebitda is None else f'{ebitda:,.2f}'}\n"
        f"Acquirer Market Cap: {inputs.acquirer_market_cap:,.2f}\n"
        f"Risk Flags:\n{risk_summary}\n"
        "Constraints: avoid LBO if debt covenant risk is severe."
    )
    try:
        ai = generate_structured_output(
            output_model=_DealStructureLLMOutput,
            system_prompt=system_prompt,
            user_prompt=human_prompt,
            temperature=0.1,
            max_tokens=900,
        )
    except AnthropicAuthenticationError as exc:
        raise DealStructuringConfigurationError(
            f"Anthropic authentication failed: {exc.detail}"
        ) from exc
    except AnthropicClientError as exc:
        raise DealStructuringLLMError(f"Structuring LLM failed: {exc}") from exc
    except Exception as exc:
        raise DealStructuringLLMError(f"Structuring LLM failed: {exc}") from exc

    stock_pct = ai.stock_consideration_pct
    if ai.recommended_structure == "Stock Swap":
        stock_pct = 1.0
    elif ai.recommended_structure in {"All Cash", "LBO"}:
        stock_pct = 0.0

    dilution = calculate_dilution(inputs.acquirer_market_cap, target_ev, stock_pct)
    return DealStructureOutput(
        recommended_structure=ai.recommended_structure,
        tax_efficiency_score=ai.tax_efficiency_score,
        debt_capacity_warning=ai.debt_capacity_warning,
        structuring_rationale=ai.structuring_rationale,
        stock_consideration_pct=stock_pct,
        estimated_dilution_pct=dilution,
    )


def generate_deal_structure(inputs: DealStructureInput) -> DealStructureOutput:
    provider = resolve_ai_provider()
    if provider == "anthropic":
        if not has_valid_anthropic_key():
            raise DealStructuringConfigurationError(
                "Anthropic mode enabled but ANTHROPIC_API_KEY is missing/invalid."
            )
        if should_use_anthropic():
            try:
                return _anthropic_structure(inputs)
            except DealStructuringError:
                raise
            except Exception as exc:
                raise DealStructuringLLMError(f"Structuring LLM failed: {exc}") from exc

    return _deterministic_structure(inputs)

