from __future__ import annotations

import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat

from app.schemas import NegotiationInput, NegotiationOutput, RiskFlag
from app.services.ai_provider import has_valid_anthropic_key, resolve_ai_provider, should_use_anthropic
from app.services.anthropic_client import (
    AnthropicAuthenticationError,
    AnthropicClientError,
    generate_structured_output,
)


class NegotiationEngineError(ValueError):
    pass


class NegotiationConfigurationError(NegotiationEngineError):
    pass


class NegotiationLLMError(NegotiationEngineError):
    pass


class _AINegotiationAdvice(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    seller_leverage: Literal["High", "Medium", "Low"]
    recommended_opening_premium_pct: StrictFloat = Field(..., ge=0.0, le=100.0)
    tactical_moves: list[str] = Field(default_factory=list, min_length=3, max_length=3)


def calculate_walk_away_price(target_ev: float, annual_synergy: float, npv_multiple: float = 5.0) -> float:
    if target_ev <= 0:
        raise ValueError("target_ev must be positive.")
    if annual_synergy < 0:
        raise ValueError("annual_synergy cannot be negative.")
    if npv_multiple <= 0:
        raise ValueError("npv_multiple must be positive.")
    return round(target_ev + annual_synergy * npv_multiple, 2)


def _risk_summary(risks: list[RiskFlag]) -> str:
    if not risks:
        return "No major legal risks identified."
    return "\n".join(
        f"{i}. [{r.severity}] {r.risk_category}: {r.ai_explanation}"
        for i, r in enumerate(risks, start=1)
    )


def _determine_leverage(inputs: NegotiationInput, synergy_ratio: float) -> Literal["High", "Medium", "Low"]:
    high = sum(1 for r in inputs.risk_flags if r.severity == "High")
    medium = sum(1 for r in inputs.risk_flags if r.severity == "Medium")

    if high >= 2:
        return "Low"
    if synergy_ratio >= 0.30 and high == 0:
        return "High"
    if high == 0 and medium <= 1:
        return "High"
    if high == 1 or medium >= 3:
        return "Medium"
    return "Medium"


def _rule_based_tactics(inputs: NegotiationInput, leverage: str) -> list[str]:
    moves: list[str] = []
    if any("debt" in r.risk_category.lower() for r in inputs.risk_flags):
        moves.append("Use covenant pressure to negotiate escrow and tighter reps-and-warranties coverage.")
    if any("litigation" in r.risk_category.lower() for r in inputs.risk_flags):
        moves.append("Tie unresolved litigation to milestone-based consideration and indemnity caps.")
    if inputs.recommended_structure in {"Stock Swap", "Hybrid"}:
        moves.append("Anchor on valuation collar mechanics to protect against market volatility pre-close.")
    if inputs.recommended_structure == "Cash + Earn-out":
        moves.append("Push performance-based earn-out tranches to align payment with post-close execution.")

    if leverage == "Low":
        moves.append("Open with slower concession cadence and require downside protection before price movement.")
    elif leverage == "High":
        moves.append("Lead with speed-to-close certainty while limiting upward movement beyond value-creation math.")
    else:
        moves.append("Exchange movement on price only for hard concessions on diligence disclosures and covenants.")

    fallback_pool = [
        "Sequence concessions: economics last, protections first, and document each trade-off in writing.",
        "Use a dated bid validity window to maintain momentum and prevent process drift.",
        "Bundle asks: link valuation movement to specific diligence disclosures and covenant relief.",
    ]
    for fallback in fallback_pool:
        if len(moves) >= 3:
            break
        if fallback not in moves:
            moves.append(fallback)
    return moves[:3]


def _deterministic_negotiation(inputs: NegotiationInput) -> NegotiationOutput:
    npv_multiple = float(os.getenv("SYNERGY_NPV_MULTIPLE", "5.0"))
    walk_away = calculate_walk_away_price(
        inputs.target_enterprise_value,
        inputs.total_annual_synergy,
        npv_multiple=npv_multiple,
    )
    max_premium_pct = max(0.0, ((walk_away / inputs.target_enterprise_value) - 1.0) * 100.0)
    synergy_ratio = (
        float(inputs.total_annual_synergy) / float(inputs.target_enterprise_value)
        if inputs.target_enterprise_value > 0
        else 0.0
    )
    leverage = _determine_leverage(inputs, synergy_ratio)

    if leverage == "Low":
        premium = 6.0
    elif leverage == "High":
        premium = 18.0 if synergy_ratio >= 0.20 else 14.0
    else:
        premium = 11.0

    if inputs.recommended_structure == "LBO":
        premium = min(premium, 9.0)
    premium = round(min(premium, max_premium_pct), 2)
    opening_bid = round(inputs.target_enterprise_value * (1.0 + premium / 100.0), 2)
    opening_bid = min(opening_bid, walk_away)

    return NegotiationOutput(
        seller_leverage=leverage,
        recommended_opening_premium_pct=premium,
        opening_bid_price=opening_bid,
        walk_away_price=walk_away,
        tactical_moves=_rule_based_tactics(inputs, leverage),
    )


def _anthropic_negotiation(inputs: NegotiationInput) -> NegotiationOutput:
    npv_multiple = float(os.getenv("SYNERGY_NPV_MULTIPLE", "5.0"))
    walk_away = calculate_walk_away_price(
        inputs.target_enterprise_value,
        inputs.total_annual_synergy,
        npv_multiple=npv_multiple,
    )
    max_premium_pct = ((walk_away / inputs.target_enterprise_value) - 1.0) * 100.0

    system_prompt = (
        "You are a buy-side M&A negotiation advisor. Only decide seller leverage, "
        "opening premium intent, and exactly three tactical moves."
    )
    human_prompt = (
        f"Target EV: {inputs.target_enterprise_value:,.2f}\n"
        f"Annual synergy: {inputs.total_annual_synergy:,.2f}\n"
        f"Recommended structure: {inputs.recommended_structure}\n"
        f"Hard max premium bound: {max_premium_pct:.2f}%\n"
        f"Risk flags:\n{_risk_summary(inputs.risk_flags)}"
    )

    try:
        ai = generate_structured_output(
            output_model=_AINegotiationAdvice,
            system_prompt=system_prompt,
            user_prompt=human_prompt,
            temperature=0.2,
            max_tokens=900,
        )
    except AnthropicAuthenticationError as exc:
        raise NegotiationConfigurationError(
            f"Anthropic authentication failed: {exc.detail}"
        ) from exc
    except AnthropicClientError as exc:
        raise NegotiationLLMError(f"Negotiation LLM failed: {exc}") from exc
    except Exception as exc:
        raise NegotiationLLMError(f"Negotiation LLM failed: {exc}") from exc

    premium = max(0.0, min(float(ai.recommended_opening_premium_pct), max_premium_pct))
    if inputs.recommended_structure == "LBO":
        premium = min(premium, 10.0)
    premium = round(premium, 2)
    opening_bid = round(inputs.target_enterprise_value * (1.0 + premium / 100.0), 2)
    opening_bid = min(opening_bid, walk_away)

    return NegotiationOutput(
        seller_leverage=ai.seller_leverage,
        recommended_opening_premium_pct=premium,
        opening_bid_price=opening_bid,
        walk_away_price=walk_away,
        tactical_moves=ai.tactical_moves,
    )


def generate_negotiation_strategy(inputs: NegotiationInput) -> NegotiationOutput:
    provider = resolve_ai_provider()
    if provider == "anthropic":
        if not has_valid_anthropic_key():
            raise NegotiationConfigurationError(
                "Anthropic mode enabled but ANTHROPIC_API_KEY is missing/invalid."
            )
        if should_use_anthropic():
            try:
                return _anthropic_negotiation(inputs)
            except NegotiationEngineError:
                raise
            except Exception as exc:
                raise NegotiationLLMError(f"Negotiation LLM failed: {exc}") from exc

    return _deterministic_negotiation(inputs)
