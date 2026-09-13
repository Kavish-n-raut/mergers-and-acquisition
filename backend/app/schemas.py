from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, model_validator


OwnershipLiteral = Literal["private", "pe_backed", "public", "family_owned"]


class CompanyCandidate(BaseModel):
    """A single screening candidate. Only name + revenue are required; the rest
    default to neutral values so partial rows still score."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(..., min_length=1, max_length=200)
    revenue: StrictFloat = Field(..., ge=0.0, description="Annual revenue ($).")
    ebitda_margin: StrictFloat = Field(default=0.15, ge=-1.0, le=1.0)
    revenue_cagr: StrictFloat = Field(default=0.08, ge=-1.0, le=5.0, description="3-year revenue CAGR.")
    ev_ebitda: StrictFloat | None = Field(default=None, ge=0.0)
    employees: StrictInt | None = Field(default=None, ge=0)
    ownership: OwnershipLiteral = "private"


class TargetScreeningInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sector: str = Field(..., min_length=2, max_length=100)
    geography: str = Field(..., min_length=2, max_length=100)
    min_revenue: StrictFloat = Field(..., ge=0.0)
    max_revenue: StrictFloat = Field(..., gt=0.0)

    # Optional richer filters (all defaulted, so the legacy 4-field call still works).
    ebitda_margin_min: StrictFloat = Field(default=0.0, ge=-1.0, le=1.0)
    target_revenue_cagr: StrictFloat = Field(default=0.10, ge=-1.0, le=5.0, description="Sector median 3-yr CAGR to benchmark growth against.")
    sector_growth_rate: StrictFloat = Field(default=0.05, ge=-1.0, le=5.0, description="Sector-level growth rate (tailwind).")
    economy_baseline_growth: StrictFloat = Field(default=0.025, ge=-1.0, le=5.0)
    ev_ebitda_max: StrictFloat | None = Field(default=None, ge=0.0)
    shortlist_size: StrictInt = Field(default=10, ge=1, le=50)
    longlist_size: StrictInt = Field(default=25, ge=1, le=200, description="Size of the synthetic universe generated when no candidates are supplied.")
    candidates: list[CompanyCandidate] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def check_revenue_bounds(self) -> "TargetScreeningInput":
        if self.min_revenue > self.max_revenue:
            raise ValueError("min_revenue cannot exceed max_revenue.")
        return self


class TargetScreeningResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    long_list: list[dict[str, Any]] = Field(default_factory=list)
    short_list: list[dict[str, Any]] = Field(default_factory=list)
    shortlist: list[dict[str, Any]] = Field(default_factory=list)  # back-compat alias of short_list
    sentiment_summary: str = ""
    competing_bid_risk_score: StrictFloat = Field(default=0.0, ge=0.0, le=1.0)
    universe_source: Literal["provided", "synthetic"] = "synthetic"
    methodology: dict[str, Any] = Field(default_factory=dict)


class DCFAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    wacc: StrictFloat = Field(..., gt=0.0, lt=1.0)
    terminal_growth_rate: StrictFloat = Field(..., ge=0.0, lt=1.0)
    free_cash_flows: list[StrictFloat] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_terminal_growth(self) -> "DCFAssumptions":
        if self.terminal_growth_rate >= self.wacc:
            raise ValueError("terminal_growth_rate must be less than wacc.")
        return self


class LBOInput(BaseModel):
    """Inputs for the Module 6 (The Check) leveraged-acquisition finance model.

    Deterministic, MVP-mode: no live debt-market feed. All rates and leverage
    levels are explicit assumptions the analyst controls.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    enterprise_value: StrictFloat = Field(..., gt=0.0, description="Purchase enterprise value (uses of funds).")
    ebitda: StrictFloat = Field(..., gt=0.0, description="Target LTM EBITDA (entry).")

    senior_leverage_x: StrictFloat = Field(default=3.0, ge=0.0, le=8.0, description="Senior debt as a multiple of EBITDA.")
    mezzanine_leverage_x: StrictFloat = Field(default=1.0, ge=0.0, le=5.0, description="Mezzanine/unitranche debt as a multiple of EBITDA.")
    senior_rate: StrictFloat = Field(default=0.08, ge=0.0, lt=1.0, description="Senior debt annual cash interest rate.")
    mezzanine_rate: StrictFloat = Field(default=0.12, ge=0.0, lt=1.0, description="Mezzanine debt annual cash interest rate.")

    ebitda_growth_rate: StrictFloat = Field(default=0.05, gt=-1.0, lt=1.0, description="Annual EBITDA growth over the hold period.")
    projection_years: StrictInt = Field(default=5, ge=1, le=10, description="Hold period in years.")
    exit_multiple: StrictFloat | None = Field(default=None, gt=0.0, le=30.0, description="EV/EBITDA at exit. Defaults to the entry multiple.")

    tax_rate: StrictFloat = Field(default=0.21, ge=0.0, lt=1.0)
    mandatory_amortization_pct: StrictFloat = Field(default=0.05, ge=0.0, le=1.0, description="Scheduled annual senior amortisation as a fraction of the original senior principal (used for the DSCR covenant test).")
    capex_pct_ebitda: StrictFloat = Field(default=0.10, ge=0.0, le=1.0, description="Maintenance capex as a fraction of EBITDA.")
    da_pct_ebitda: StrictFloat = Field(default=0.10, ge=0.0, le=1.0, description="Depreciation & amortisation as a fraction of EBITDA.")
    transaction_fees_pct: StrictFloat = Field(default=0.02, ge=0.0, le=0.2, description="Transaction fees as a fraction of EV (added to uses).")
    seller_rollover: StrictFloat = Field(default=0.0, ge=0.0, description="Seller rollover equity ($), reduces sponsor equity.")

    board_hurdle_irr: StrictFloat = Field(default=0.15, ge=0.0, lt=1.0, description="Board-approved minimum levered equity IRR.")
    min_dscr_covenant: StrictFloat = Field(default=1.20, ge=0.0, le=10.0, description="Minimum DSCR covenant threshold.")


class DCFDriverAssumptions(BaseModel):
    """Driver-based 10-year DCF (PRD §4.3.2). Builds unlevered free cash flows
    from operating drivers, then discounts them. Produces Base/Bull/Bear cases."""

    model_config = ConfigDict(extra="forbid", strict=True)

    base_revenue: StrictFloat = Field(..., gt=0.0)
    revenue_growth_rate: StrictFloat = Field(..., gt=-1.0, lt=2.0, description="Annual revenue growth rate (base case).")
    projection_years: StrictInt = Field(default=5, ge=1, le=10)
    ebitda_margin: StrictFloat = Field(..., gt=0.0, le=1.0)
    da_pct_of_revenue: StrictFloat = Field(default=0.05, ge=0.0, le=1.0)
    capex_pct_of_revenue: StrictFloat = Field(default=0.05, ge=0.0, le=1.0)
    nwc_pct_of_revenue_change: StrictFloat = Field(default=0.10, ge=-1.0, le=1.0, description="Change in net working capital as a fraction of the change in revenue.")
    tax_rate: StrictFloat = Field(default=0.21, ge=0.0, lt=1.0)
    wacc: StrictFloat = Field(..., gt=0.0, lt=1.0)
    terminal_growth_rate: StrictFloat = Field(..., ge=0.0, lt=1.0)
    net_debt: StrictFloat = Field(default=0.0, description="Net debt, to bridge from enterprise value to equity value.")
    scenario_delta: StrictFloat = Field(default=0.15, ge=0.0, le=1.0, description="Relative up/down shock to the growth rate for Bull/Bear cases (e.g. 0.15 = +/-15%).")

    @model_validator(mode="after")
    def validate_terminal_growth(self) -> "DCFDriverAssumptions":
        if self.terminal_growth_rate >= self.wacc:
            raise ValueError("terminal_growth_rate must be less than wacc.")
        return self


class SynergyAssumptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    company_a_revenue: StrictFloat = Field(..., ge=0.0)
    company_b_revenue: StrictFloat = Field(..., ge=0.0)
    company_b_opex: StrictFloat = Field(..., ge=0.0)
    cost_reduction_pct: StrictFloat = Field(..., ge=0.0, le=1.0)
    cross_sell_pct: StrictFloat = Field(..., ge=0.0, le=1.0)
    market_compatibility_score: StrictInt = Field(..., ge=1, le=10)
    tech_stack_compatibility: StrictInt = Field(default=5, ge=1, le=10)


JurisdictionCode = Literal["US_HSR", "EU_EC", "UK_CMA", "IN_CCI", "CN_SAMR", "DE_BKA", "AU_ACCC"]


class JurisdictionTurnover(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    jurisdiction: JurisdictionCode
    combined_turnover_usd: StrictFloat = Field(..., ge=0.0, description="Combined parties' turnover in this jurisdiction (USD-equivalent).")


class RegulatoryHorizonInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    deal_ev: StrictFloat = Field(..., gt=0.0, description="Deal enterprise value (USD).")
    combined_market_share: StrictFloat = Field(..., ge=0.0, le=1.0, description="Combined share in the primary product market.")
    product_overlaps: StrictInt = Field(default=1, ge=0, le=100)
    sector: str = Field(default="general", min_length=2, max_length=100)
    is_private_equity: bool = False
    jurisdictions: list[JurisdictionTurnover] = Field(..., min_length=1, max_length=7)


class CFIUSInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    us_business: bool = True
    foreign_acquirer: bool = True
    acquirer_country_of_concern: bool = Field(default=False, description="Acquirer from a country subject to heightened CFIUS scrutiny.")
    critical_technology: bool = False
    critical_infrastructure: bool = False
    sensitive_personal_data: bool = False
    proximity_to_military: bool = False


class ClosingChecklistInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    required_jurisdictions: list[str] = Field(default_factory=list, max_length=20)
    acquirer_board_approval: bool = True
    target_board_approval: bool = True
    shareholder_approval_required: bool = False
    financing_required: bool = True
    change_of_control_consents: StrictInt = Field(default=0, ge=0, le=500)


class NormalizationAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    label: str = Field(..., min_length=1, max_length=160)
    amount: StrictFloat = Field(..., description="EBITDA add-back ($). Positive increases normalized EBITDA.")


class YearlyFinancials(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    year: StrictInt = Field(..., ge=1900, le=2200)
    revenue: StrictFloat = Field(..., ge=0.0)
    cogs: StrictFloat = Field(default=0.0, ge=0.0)
    sga: StrictFloat = Field(default=0.0, ge=0.0)
    rnd: StrictFloat = Field(default=0.0, ge=0.0)
    depreciation_amortization: StrictFloat = Field(default=0.0, ge=0.0)
    interest_expense: StrictFloat = Field(default=0.0)
    tax_rate: StrictFloat = Field(default=0.21, ge=0.0, lt=1.0)
    adjustments: list[NormalizationAdjustment] = Field(default_factory=list, max_length=50)


class FinancialNormalizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    years: list[YearlyFinancials] = Field(..., min_length=1, max_length=10)
    sector_ebitda_margin_95th: StrictFloat | None = Field(default=None, ge=0.0, le=1.0, description="Sector 95th-pct EBITDA margin for anomaly detection.")


class DealParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(..., min_length=1, max_length=200)
    role: Literal["management", "board", "advisor", "financing_bank", "counsel"]
    side: Literal["buyer", "target", "neutral"]
    affiliations: list[str] = Field(default_factory=list, max_length=50, description="Prior firms / shared entities.")


class AdvisorGraphInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    participants: list[DealParticipant] = Field(..., min_length=1, max_length=200)


class RiskFlag(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    risk_category: str = Field(..., min_length=3, max_length=120)
    severity: Literal["High", "Medium", "Low"]
    quoted_text: str = Field(..., min_length=10)
    ai_explanation: str = Field(..., min_length=10, max_length=1200)


class DocumentScanResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_name: str = Field(..., min_length=1, max_length=255)
    total_risks_found: StrictInt = Field(..., ge=0)
    risks: list[RiskFlag] = Field(default_factory=list)


class NewsSentimentInput(BaseModel):
    """FinBERT sentiment over provided texts, or over Finnhub company news for a
    ticker when `symbol` is given and FINNHUB_API_KEY is configured."""

    model_config = ConfigDict(extra="forbid", strict=True)

    texts: list[str] = Field(default_factory=list, max_length=100)
    symbol: str | None = Field(default=None, min_length=1, max_length=20)
    company: str | None = Field(default=None, min_length=1, max_length=200, description="Company name for GDELT news search.")
    source: Literal["finnhub", "gdelt"] = "finnhub"
    days: StrictInt = Field(default=30, ge=1, le=365)

    @model_validator(mode="after")
    def require_source(self) -> "NewsSentimentInput":
        if not self.texts and not self.symbol and not self.company:
            raise ValueError("Provide `texts`, a `symbol` (finnhub), or a `company` (gdelt).")
        return self


class TemporalRiskMapInput(BaseModel):
    """Input for the E4 Temporal Risk Mapper — a set of diligence findings to
    classify by when they crystallise relative to the deal timeline."""

    model_config = ConfigDict(extra="forbid", strict=True)

    risks: list[RiskFlag] = Field(default_factory=list, max_length=500)


class ValuationData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    enterprise_value: StrictFloat = Field(..., gt=0.0)
    ebitda: StrictFloat | None = None


class DealStructureInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    acquirer_market_cap: StrictFloat = Field(..., gt=0.0)
    valuation_data: ValuationData
    risk_flags: list[RiskFlag] = Field(default_factory=list)


class DealStructureOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    recommended_structure: Literal["All Cash", "Stock Swap", "LBO", "Cash + Earn-out", "Hybrid"]
    tax_efficiency_score: StrictFloat = Field(..., ge=1.0, le=10.0)
    debt_capacity_warning: bool
    structuring_rationale: str = Field(..., min_length=20, max_length=2000)
    stock_consideration_pct: StrictFloat = Field(..., ge=0.0, le=1.0)
    estimated_dilution_pct: StrictFloat = Field(default=0.0, ge=0.0, le=100.0)


class NegotiationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    target_enterprise_value: StrictFloat = Field(..., gt=0.0)
    total_annual_synergy: StrictFloat = Field(..., ge=0.0)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    recommended_structure: Literal["All Cash", "Stock Swap", "LBO", "Cash + Earn-out", "Hybrid"]


class NegotiationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    seller_leverage: Literal["High", "Medium", "Low"]
    recommended_opening_premium_pct: StrictFloat = Field(..., ge=0.0, le=100.0)
    opening_bid_price: StrictFloat = Field(..., ge=0.0)
    walk_away_price: StrictFloat = Field(..., ge=0.0)
    tactical_moves: list[str] = Field(default_factory=list, min_length=3, max_length=3)


class FullAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dcf_assumptions: DCFAssumptions
    acquirer_market_cap: StrictFloat = Field(..., gt=0.0)
    synergy_assumptions: SynergyAssumptions | None = None


class MasterDiligenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    deal_id: str
    company_a_financials: dict[str, Any] = Field(default_factory=dict)
    company_b_financials: dict[str, Any] = Field(default_factory=dict)
    valuation: dict[str, Any] | None = None
    synergies: dict[str, Any] = Field(default_factory=dict)
    legal_risks: dict[str, Any] | None = None
    deal_structure: dict[str, Any] | None = None
    negotiation_strategy: dict[str, Any] | None = None
    financing: dict[str, Any] | None = None  # M6 LBO / capital-stack output
    regulatory: dict[str, Any] | None = None  # M7 regulatory_horizon / cfius / closing_checklist
    status_log: list[str] = Field(default_factory=list)


SynergyCategoryLiteral = Literal[
    "Headcount",
    "Facilities",
    "Procurement",
    "Cross-Sell",
    "IT Rationalization",
    "Pricing Uplift",
]


class SynergyRealizationEntryInput(BaseModel):
    """A single monthly realised-vs-predicted synergy actual (Module 8)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    category: SynergyCategoryLiteral
    period_month: StrictInt = Field(..., ge=1, le=120, description="Month index post-close (1 = first month).")
    predicted_amount: StrictFloat = Field(..., ge=0.0, description="Synergy predicted for this category/month ($).")
    realized_amount: StrictFloat = Field(..., ge=0.0, description="Synergy actually realised this category/month ($).")
    note: str = Field(default="", max_length=1000)


class PMIDNAInput(BaseModel):
    """Inputs for the E6 PMI DNA Score (Module 8). MVP mode accepts analyst- or
    diligence-derived component scores (0-100) rather than live Glassdoor/LinkedIn."""

    model_config = ConfigDict(extra="forbid", strict=True)

    culture_compatibility: StrictFloat = Field(..., ge=0.0, le=100.0)
    org_structure_compatibility: StrictFloat = Field(..., ge=0.0, le=100.0)
    leadership_profile_match: StrictFloat = Field(..., ge=0.0, le=100.0)
    compensation_overlap: StrictFloat = Field(..., ge=0.0, le=100.0)
    technology_stack_compatibility: StrictFloat = Field(..., ge=0.0, le=100.0)


class LocalDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_type: Literal["NDA", "LOI"]
    deal_name: str = Field(..., min_length=3, max_length=200)
    buyer_name: str = Field(..., min_length=2, max_length=200)
    seller_name: str = Field(..., min_length=2, max_length=200)
    jurisdiction: str = Field(default="Delaware", min_length=2, max_length=120)
    purchase_price: StrictFloat | None = Field(default=None, ge=0.0)
    exclusivity_days: StrictInt = Field(default=45, ge=1, le=180)


class LocalDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_type: Literal["NDA", "LOI"]
    title: str
    key_terms: dict[str, Any] = Field(default_factory=dict)
    body: str


class LocalQAResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    document_name: str
    question: str
    answer: str
    supporting_quotes: list[str] = Field(default_factory=list, max_length=5)


class PublicDataSeriesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source: str
    identifier: str
    observations: list[dict[str, str]] = Field(default_factory=list)


class MarketAssumptionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    risk_free_rate: StrictFloat = Field(..., ge=0.0, lt=1.0)
    equity_risk_premium: StrictFloat = Field(..., ge=0.0, lt=1.0)
    beta: StrictFloat = Field(..., gt=0.0, lt=5.0)
    pre_tax_cost_of_debt: StrictFloat = Field(..., ge=0.0, lt=1.0)
    tax_rate: StrictFloat = Field(..., ge=0.0, lt=1.0)
    equity_weight: StrictFloat = Field(..., ge=0.0, le=1.0)
    debt_weight: StrictFloat = Field(..., ge=0.0, le=1.0)
    cost_of_equity: StrictFloat = Field(..., ge=0.0, lt=1.0)
    after_tax_cost_of_debt: StrictFloat = Field(..., ge=0.0, lt=1.0)
    wacc: StrictFloat = Field(..., gt=0.0, lt=1.0)
    terminal_growth_rate: StrictFloat = Field(..., ge=0.0, lt=1.0)
    source_mode: Literal["live", "sample", "mixed"]
    sources: list[dict[str, str]] = Field(default_factory=list)
    last_updated: str
    note: str


class HistoricalTransactionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    buyer_name: str = Field(..., min_length=2, max_length=255)
    target_name: str = Field(..., min_length=2, max_length=255)
    announcement_date: str = Field(default="", max_length=32)
    close_date: str | None = Field(default=None, max_length=32)
    deal_value: StrictFloat | None = Field(default=None, ge=0.0)
    enterprise_value: StrictFloat | None = Field(default=None, ge=0.0)
    revenue: StrictFloat | None = Field(default=None, ge=0.0)
    ebitda: StrictFloat | None = None
    sector: str = Field(default="Unknown", min_length=2, max_length=160)
    buyer_country: str = Field(default="Unknown", min_length=2, max_length=120)
    target_country: str = Field(default="Unknown", min_length=2, max_length=120)
    payment_type: str = Field(default="Unknown", min_length=2, max_length=80)
    premium_pct: StrictFloat | None = Field(default=None, ge=0.0)
    deal_status: str = Field(default="announced", min_length=2, max_length=80)
    source_url: str = Field(default="", max_length=1200)
    source_type: str = Field(default="manual", min_length=2, max_length=80)


class HistoricalTransactionResponse(HistoricalTransactionInput):
    id: str
    created_at: str
    updated_at: str


class DealGenomeSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    total_transactions: StrictInt = Field(..., ge=0)
    by_source_type: dict[str, StrictInt] = Field(default_factory=dict)
    by_status: dict[str, StrictInt] = Field(default_factory=dict)
    by_sector: dict[str, StrictInt] = Field(default_factory=dict)
    database_claim: str
    note: str


class CompanyMapMarker(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    name: str
    headquarters: str
    city: str
    country: str
    sector: str
    company_size: str = "Unknown"
    public_private: Literal["Public", "Private", "Unknown"]
    listed_exchange: str | None = None
    ticker: str | None = None
    lei: str | None = None
    registration_number: str | None = None
    marker_role: Literal["buyer", "target", "competitor", "customer", "regulatory", "operating_region", "company"]
    lat: StrictFloat
    lng: StrictFloat
    mna_signal: Literal["High", "Medium", "Low", "Insufficient public data"]
    confidence: Literal["High", "Medium", "Low", "Insufficient public data"]
    distress_signal: Literal["High", "Medium", "Low", "Insufficient public data"] = "Insufficient public data"
    signal_score: StrictFloat = Field(default=0.0, ge=0.0, le=100.0)
    signal_explanation: str
    data_source: str
    source_url: str | None = None
    last_updated: str
    source_mode: Literal["live", "sample", "cache"] = "sample"


class CompanyMapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    companies: list[CompanyMapMarker] = Field(default_factory=list)
    total: StrictInt = Field(default=0, ge=0)
    data_source: str
    source_mode: Literal["live", "sample", "cache", "mixed"]
    last_updated: str
    note: str


class CompanyProfileResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    company: CompanyMapMarker
    overview: str
    filings_registry_links: list[dict[str, str]] = Field(default_factory=list)
    competitors_nearby: list[CompanyMapMarker] = Field(default_factory=list)
    mna_signal_explanation: str
    legal_regulatory_notes: list[str] = Field(default_factory=list)
    ipo_public_company_details: dict[str, Any] = Field(default_factory=dict)


class MarketDataCard(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    label: str
    value: str
    change: str
    status: Literal["positive", "negative", "neutral"]
    last_updated: str
    data_source: str
    detail: str


class MarketDataSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    cards: list[MarketDataCard]
    source_mode: Literal["live", "sample", "mixed"] = "sample"
    note: str


DealStageLiteral = Literal[
    "m1_hunt",
    "m2_approach",
    "m3_handshake",
    "m4_deep_dive",
    "m5_war_room",
    "m6_check",
    "m7_close",
    "m8_reality",
]


class DealCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    deal_name: str = Field(..., min_length=3, max_length=255)


class DealStageUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    stage: DealStageLiteral
    status: Literal["in_progress", "completed", "blocked"] = "in_progress"


class DealSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    deal_name: str
    stage: DealStageLiteral
    status: Literal["in_progress", "completed", "blocked"]
    created_at: str
    updated_at: str


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=1, max_length=200)


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    username: str
    role: str
    expires_in: StrictInt


class ModuleOutputInput(BaseModel):
    """Persist a module/engine output onto a deal (M1/M2/M6/M7 results)."""

    model_config = ConfigDict(extra="forbid", strict=True)

    module_key: str = Field(..., min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)


class WarRoomMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sender_name: str = Field(default="anonymous", min_length=1, max_length=120)
    content: str = Field(..., min_length=1, max_length=4000)


class WarRoomMessageOut(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    deal_id: str
    sender_role: str
    sender_name: str
    content: str
    created_at: str
