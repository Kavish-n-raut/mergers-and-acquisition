from __future__ import annotations

import json
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.auth import authenticate, create_access_token
from app.core.config import get_settings
from app.core.rbac import attach_role_to_request, get_current_role, require_role
from app.db.base import Base
from app.db.models import AuditLog, DealModuleOutput, DealRecord
from app.db.session import engine, get_db
from app.schemas import (
    AdvisorGraphInput,
    CFIUSInput,
    ClosingChecklistInput,
    DCFAssumptions,
    DCFDriverAssumptions,
    DealCreateRequest,
    FinancialNormalizationInput,
    LBOInput,
    RegulatoryHorizonInput,
    DealGenomeSummaryResponse,
    DealStageUpdateRequest,
    DealStructureInput,
    DealSummary,
    FullAnalysisRequest,
    HistoricalTransactionInput,
    LocalDraftRequest,
    MasterDiligenceReport,
    MarketAssumptionsResponse,
    LoginRequest,
    ModuleOutputInput,
    NegotiationInput,
    NewsSentimentInput,
    PMIDNAInput,
    RiskFlag,
    TokenResponse,
    SynergyAssumptions,
    SynergyRealizationEntryInput,
    TargetScreeningInput,
    TemporalRiskMapInput,
    WarRoomMessageIn,
)
from app.services.deal_manager import DealLifecycleError, create_deal, update_deal_stage
from app.services.deal_genome import (
    DealGenomeError,
    create_or_update_transaction,
    import_transactions_csv,
    list_transactions,
    seed_sample_transactions,
    summarize_deal_genome,
)
from app.services.deal_structuring import (
    DealStructuringConfigurationError,
    DealStructuringError,
    generate_deal_structure,
)
from app.services.drafting import generate_local_draft
from app.services.document_scanner import (
    DocumentScannerConfigurationError,
    DocumentScannerDependencyError,
    DocumentScannerError,
    process_and_scan_pdf,
)
from app.services.deal_financing import LBOFinancingError, calculate_lbo
from app.services.advisor_graph import build_advisor_conflict_graph
from app.services.finnhub_client import (
    FinnhubConfigurationError,
    FinnhubError,
    get_basic_financials,
    get_company_news,
    get_quote,
    is_configured as finnhub_is_configured,
)
from app.services.finbert import FinBertUnavailableError, analyze_texts as finbert_analyze
from app.services.groq_client import (
    GroqConfigurationError,
    GroqError,
    check_connectivity as groq_check_connectivity,
    generate_text as groq_generate_text,
    is_configured as groq_is_configured,
)
from app.services.gdelt import GdeltError, get_news as gdelt_get_news
from app.services.patents import (
    PatentsConfigurationError,
    PatentsError,
    get_patent_velocity,
    is_configured as patents_is_configured,
)
from app.services.edgar_deals import EdgarError, import_ma_filings_to_genome, search_ma_filings
from app.services.financial_normalization import normalize_financials
from app.services.regulatory import cfius_screening, closing_checklist, regulatory_horizon
from app.services.external_data import load_external_datasets
from app.services.ml_layer import MLError, predict_deal_intelligence
from app.services.financial_engine import (
    FinancialDataError,
    ValuationError,
    calculate_dcf,
    calculate_dcf_from_drivers,
    calculate_financial_ratios,
    dataframe_to_records,
    load_financial_csv,
)
from app.services.market_assumptions import calculate_market_assumptions
from app.services.lifecycle_modules import run_module1_target_screening, run_module2_approach_summary
from app.services.local_qa import LocalQAError, answer_question_from_document
from app.services.negotiator import (
    NegotiationConfigurationError,
    NegotiationEngineError,
    generate_negotiation_strategy,
)
from app.services.orchestrator import run_full_analysis
from app.services.pmi import (
    add_realization_entry,
    calculate_pmi_dna_score,
    synergy_realization_dashboard,
)
from app.services.temporal_risk import map_temporal_risks
from app.services.pitchbook import create_pitchbook
from app.services.public_data import (
    PublicDataError,
    get_fred_series,
    get_reference_datasets,
    get_sec_companyfacts,
    get_stooq_prices,
    get_treasury_yields,
)
from app.services.synthetic_data import (
    SyntheticDataError,
    list_synthetic_datasets,
    load_synthetic_dataset,
)
from app.services.synergy import SynergyCalculationError, calculate_synergies
from app.services.war_room import get_war_room_messages, save_war_room_message
from app.services.ai_provider import has_valid_anthropic_key, resolve_ai_provider
from app.services.anthropic_client import (
    AnthropicAuthenticationError,
    AnthropicClientError,
    AnthropicConfigurationError,
    AnthropicRequestError,
    check_anthropic_connectivity,
)
from app.services.company_intelligence import (
    get_company_profile,
    market_data_summary,
    search_companies,
    viewport_companies,
)
from app.services.overpass import query_companies, OverpassError

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version="3.0.0",
    description="QuantumBlack M&A Deal Operating System API",
    lifespan=lifespan,
)

# NOTE: the CORS spec forbids combining a wildcard origin ("*") with
# allow_credentials=True — browsers reject credentialed requests in that case.
# Use an explicit allow-list (configurable via settings.cors_origins) instead.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class WarRoomConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, list[WebSocket]] = {}

    async def connect(self, deal_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(deal_id, []).append(websocket)

    def disconnect(self, deal_id: str, websocket: WebSocket) -> None:
        if deal_id not in self._connections:
            return
        self._connections[deal_id] = [w for w in self._connections[deal_id] if w is not websocket]
        if not self._connections[deal_id]:
            del self._connections[deal_id]

    async def broadcast(self, deal_id: str, payload: dict) -> None:
        for ws in list(self._connections.get(deal_id, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(deal_id, ws)


war_room_manager = WarRoomConnectionManager()


@app.middleware("http")
async def role_context_middleware(request: Request, call_next):
    header_role = request.headers.get("x-user-role")
    role = header_role.lower() if header_role else settings.default_role.lower()
    attach_role_to_request(request, role)
    return await call_next(request)


def _safe_remove_file(path: str) -> None:
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        return


def _write_audit_log(db: Session, deal_id: str, role: str, action: str, details: str = "") -> None:
    db.add(
        AuditLog(
            deal_id=deal_id,
            actor_role=role,
            action=action,
            details=details,
        )
    )
    db.commit()


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _save_master_report(db: Session, report: MasterDiligenceReport) -> DealRecord:
    existing = db.get(DealRecord, report.deal_id)
    if existing is None:
        record = DealRecord(id=report.deal_id)
        db.add(record)
    else:
        record = existing

    record.stage = "m8_reality"
    record.status = "completed"
    record.company_a_financials = report.company_a_financials
    record.company_b_financials = report.company_b_financials
    record.valuation = report.valuation
    record.synergies = report.synergies
    record.legal_risks = report.legal_risks
    record.deal_structure = report.deal_structure
    record.negotiation_strategy = report.negotiation_strategy
    record.status_log = report.status_log

    db.commit()
    db.refresh(record)
    return record


@app.get("/")
def root():
    return {"message": f"{settings.app_name} API is running.", "version": app.version}


@app.get(f"{settings.api_v1_prefix}/health")
def health():
    return {"status": "ok", "service": settings.app_name}


@app.post(f"{settings.api_v1_prefix}/auth/login", response_model=TokenResponse)
def auth_login(payload: LoginRequest):
    role = authenticate(payload.username, payload.password)
    if role is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(payload.username.lower(), role)
    return TokenResponse(
        access_token=token,
        username=payload.username.lower(),
        role=role,
        expires_in=settings.jwt_expire_minutes * 60,
    )


@app.get(f"{settings.api_v1_prefix}/auth/me")
def auth_me(user_role: str = Depends(get_current_role)):
    return {"status": "success", "role": user_role, "auth_enforced": settings.auth_enforced}


@app.post(
    f"{settings.api_v1_prefix}/ai/generate",
    dependencies=[Depends(require_role("analyst"))],
)
def ai_generate(payload: dict):
    """Free-LLM text generation via Groq (e.g. explanations, ad-hoc analysis)."""
    prompt = (payload or {}).get("prompt", "").strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="`prompt` is required.")
    system = (payload or {}).get("system") or "You are a precise M&A analyst. Be concise and factual."
    max_tokens = int((payload or {}).get("max_tokens", 800))
    try:
        text = groq_generate_text(prompt, system=system, max_tokens=max_tokens)
        return {"status": "success", "provider": "groq", "model": settings.groq_model, "text": text}
    except GroqConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GroqError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(f"{settings.api_v1_prefix}/external-data")
def external_data_index():
    try:
        return {"status": "success", "data": load_external_datasets()}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"External dataset loading failed: {exc}") from exc


@app.post(f"{settings.api_v1_prefix}/ml/deal-intelligence")
async def ml_deal_intelligence(payload: dict):
    try:
        financials_a = pd.DataFrame(payload.get("company_a_financials", []))
        financials_b = pd.DataFrame(payload.get("company_b_financials", []))
        market_context = payload.get("market_context")
        return {"status": "success", "result": predict_deal_intelligence(financials_a, financials_b, market_context)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"ML pipeline failed: {exc}") from exc


@app.get(f"{settings.api_v1_prefix}/health/llm")
def llm_health(live_check: bool = Query(default=True)):
    provider = resolve_ai_provider()
    if provider == "local":
        return {
            "status": "ok",
            "provider": "local",
            "mode": "free_mvp",
            "detail": "Local deterministic mode enabled. No paid API key required.",
        }

    if provider == "groq":
        if not groq_is_configured():
            return {
                "status": "degraded",
                "provider": "groq",
                "model": settings.groq_model,
                "detail": "Groq mode requested but GROQ_API_KEY is missing. Get a free key at https://console.groq.com.",
            }
        if not live_check:
            return {"status": "configured", "provider": "groq", "model": settings.groq_model}
        try:
            ping = groq_check_connectivity()
            return {"status": "ok", "provider": "groq", "model": ping["model"], "reply": ping["reply"]}
        except GroqConfigurationError as exc:
            return {"status": "degraded", "provider": "groq", "detail": str(exc)}
        except GroqError as exc:
            raise HTTPException(status_code=503, detail=f"Groq health check failed: {exc}") from exc

    if not has_valid_anthropic_key():
        return {
            "status": "degraded",
            "provider": "anthropic",
            "model": settings.anthropic_model,
            "detail": "Anthropic mode requested but ANTHROPIC_API_KEY is missing or invalid.",
        }

    if not live_check:
        return {
            "status": "configured",
            "provider": "anthropic",
            "model": settings.anthropic_model,
            "detail": "Set live_check=true to validate upstream Anthropic authentication.",
        }

    try:
        ping = check_anthropic_connectivity(model=settings.anthropic_model)
        return {
            "status": "ok",
            "provider": ping["provider"],
            "model": ping["model"],
            "request_id": ping["request_id"],
        }
    except AnthropicConfigurationError as exc:
        return {
            "status": "degraded",
            "provider": "anthropic",
            "detail": str(exc),
        }
    except AnthropicAuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Anthropic authentication failed: {exc.detail}",
        ) from exc
    except AnthropicRequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Anthropic upstream request failed ({exc.status_code}): {exc.detail}",
        ) from exc
    except AnthropicClientError as exc:
        raise HTTPException(status_code=503, detail=f"Anthropic health check failed: {exc}") from exc


@app.post(
    f"{settings.api_v1_prefix}/deals",
    response_model=DealSummary,
    dependencies=[Depends(require_role("associate"))],
)
def create_deal_record(
    payload: DealCreateRequest,
    db: Session = Depends(get_db),
    user_role: str = Depends(get_current_role),
):
    deal = create_deal(db, payload)
    _write_audit_log(
        db=db,
        deal_id=deal.id,
        role=user_role,
        action="create_deal",
        details=json.dumps({"deal_name": payload.deal_name}),
    )
    return DealSummary(
        id=deal.id,
        deal_name=deal.deal_name,
        stage=deal.stage,
        status=deal.status,
        created_at=_iso_utc(deal.created_at),
        updated_at=_iso_utc(deal.updated_at),
    )


@app.patch(
    f"{settings.api_v1_prefix}/deals/{{deal_id}}/stage",
    response_model=DealSummary,
    dependencies=[Depends(require_role("vp"))],
)
def update_deal_stage_endpoint(
    deal_id: str,
    payload: DealStageUpdateRequest,
    db: Session = Depends(get_db),
    user_role: str = Depends(get_current_role),
):
    deal = db.get(DealRecord, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal record not found.")
    try:
        updated = update_deal_stage(db, deal, payload)
    except DealLifecycleError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    _write_audit_log(
        db=db,
        deal_id=updated.id,
        role=user_role,
        action="update_stage",
        details=json.dumps({"stage": payload.stage, "status": payload.status}),
    )
    return DealSummary(
        id=updated.id,
        deal_name=updated.deal_name,
        stage=updated.stage,
        status=updated.status,
        created_at=_iso_utc(updated.created_at),
        updated_at=_iso_utc(updated.updated_at),
    )


# Module 1 (Hunt)
@app.post(
    f"{settings.api_v1_prefix}/modules/m1/screen-targets",
    dependencies=[Depends(require_role("analyst"))],
)
def module1_screen_targets(payload: TargetScreeningInput):
    result = run_module1_target_screening(payload)
    return {"status": "success", "module": "m1_hunt", "data": result.model_dump()}


# Module 2 (Approach)
@app.get(
    f"{settings.api_v1_prefix}/modules/m2/approach-summary",
    dependencies=[Depends(require_role("associate"))],
)
def module2_approach_summary(target_name: str = Query(..., min_length=2, max_length=120)):
    return {
        "status": "success",
        "module": "m2_approach",
        "data": run_module2_approach_summary(target_name),
    }

# Module 2 (Approach) — three-year financial normalization
@app.post(
    f"{settings.api_v1_prefix}/modules/m2/normalize-financials",
    dependencies=[Depends(require_role("associate"))],
)
def module2_normalize_financials(payload: FinancialNormalizationInput):
    try:
        return {"status": "success", "module": "m2_approach", "normalized": normalize_financials(payload)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Normalization engine failed: {exc}") from exc


# Module 2 (Approach) — advisor conflict graph
@app.post(
    f"{settings.api_v1_prefix}/modules/m2/advisor-graph",
    dependencies=[Depends(require_role("associate"))],
)
def module2_advisor_graph(payload: AdvisorGraphInput):
    try:
        return {"status": "success", "module": "m2_approach", "advisor_graph": build_advisor_conflict_graph(payload)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Advisor graph engine failed: {exc}") from exc


@app.post(
    f"{settings.api_v1_prefix}/draft-document/",
    dependencies=[Depends(require_role("associate"))],
)
def draft_local_document(payload: LocalDraftRequest):
    draft = generate_local_draft(payload)
    return {"status": "success", "draft": draft.model_dump()}


@app.get(
    f"{settings.api_v1_prefix}/deals/{{deal_id}}/war-room/messages",
    dependencies=[Depends(require_role("analyst"))],
)
def list_war_room_messages(
    deal_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if db.get(DealRecord, deal_id) is None:
        raise HTTPException(status_code=404, detail="Deal record not found.")
    return {
        "status": "success",
        "deal_id": deal_id,
        "messages": [m.model_dump() for m in get_war_room_messages(db, deal_id, limit)],
    }


@app.post(
    f"{settings.api_v1_prefix}/deals/{{deal_id}}/war-room/messages",
    dependencies=[Depends(require_role("associate"))],
)
async def post_war_room_message(
    deal_id: str,
    payload: WarRoomMessageIn,
    db: Session = Depends(get_db),
    user_role: str = Depends(get_current_role),
):
    if db.get(DealRecord, deal_id) is None:
        raise HTTPException(status_code=404, detail="Deal record not found.")
    msg = save_war_room_message(db, deal_id, user_role, payload)
    await war_room_manager.broadcast(deal_id, msg.model_dump())
    return {"status": "success", "message": msg.model_dump()}


@app.websocket(f"{settings.api_v1_prefix}/ws/war-room/{{deal_id}}")
async def war_room_websocket(deal_id: str, websocket: WebSocket):
    role = websocket.headers.get("x-user-role", settings.default_role)
    await war_room_manager.connect(deal_id, websocket)
    try:
        await war_room_manager.broadcast(
            deal_id,
            {
                "system_event": "join",
                "deal_id": deal_id,
                "sender_role": role,
            },
        )
        while True:
            payload = await websocket.receive_json()
            payload.setdefault("deal_id", deal_id)
            payload.setdefault("sender_role", role)
            await war_room_manager.broadcast(deal_id, payload)
    except WebSocketDisconnect:
        war_room_manager.disconnect(deal_id, websocket)
        await war_room_manager.broadcast(
            deal_id,
            {
                "system_event": "leave",
                "deal_id": deal_id,
                "sender_role": role,
            },
        )


# Phase 1 financial ratios
@app.post(f"{settings.api_v1_prefix}/financial/ratios")
async def analyze_financial_ratios(
    company_a_file: UploadFile = File(...),
    company_b_file: UploadFile = File(...),
):
    try:
        company_a_bytes = await company_a_file.read()
        company_b_bytes = await company_b_file.read()
        if not company_a_bytes or not company_b_bytes:
            raise HTTPException(status_code=400, detail="Both uploaded CSV files must be non-empty.")

        cleaned_a, warnings_a = load_financial_csv(company_a_bytes, "Company A")
        cleaned_b, warnings_b = load_financial_csv(company_b_bytes, "Company B")
        ratios_a = calculate_financial_ratios(cleaned_a)
        ratios_b = calculate_financial_ratios(cleaned_b)
        return {
            "status": "success",
            "companies": {
                "company_a": {
                    "warnings": warnings_a,
                    "ratios": dataframe_to_records(ratios_a),
                },
                "company_b": {
                    "warnings": warnings_b,
                    "ratios": dataframe_to_records(ratios_b),
                },
            },
        }
    except FinancialDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Financial ratio engine failed: {exc}") from exc


# Phase 1 DCF
@app.post(f"{settings.api_v1_prefix}/valuation/dcf")
def run_dcf_valuation(assumptions: DCFAssumptions):
    try:
        return {"status": "success", "valuation": calculate_dcf(assumptions)}
    except ValuationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"DCF engine failed: {exc}") from exc


# Module 3 (Handshake) — driver-based DCF with Base/Bull/Bear scenarios
@app.post(f"{settings.api_v1_prefix}/valuation/dcf-drivers")
def run_dcf_from_drivers(drivers: DCFDriverAssumptions):
    try:
        return {"status": "success", "valuation": calculate_dcf_from_drivers(drivers)}
    except ValuationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Driver-based DCF engine failed: {exc}") from exc


@app.get(f"{settings.api_v1_prefix}/valuation/market-assumptions", response_model=MarketAssumptionsResponse)
def valuation_market_assumptions(
    beta: float = Query(default=1.10, gt=0.0, lt=5.0),
    equity_risk_premium: float = Query(default=0.0433, ge=0.0, lt=1.0),
    debt_spread: float = Query(default=0.0200, ge=0.0, lt=1.0),
    tax_rate: float = Query(default=0.21, ge=0.0, lt=1.0),
    equity_weight: float = Query(default=0.75, ge=0.0, le=1.0),
    terminal_growth_rate: float = Query(default=0.025, ge=0.0, lt=1.0),
):
    try:
        return calculate_market_assumptions(
            beta=beta,
            equity_risk_premium=equity_risk_premium,
            debt_spread=debt_spread,
            tax_rate=tax_rate,
            equity_weight=equity_weight,
            terminal_growth_rate=terminal_growth_rate,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Market assumptions failed: {exc}") from exc


# Phase 2 synergy
@app.post(f"{settings.api_v1_prefix}/calculate-synergies/")
def run_synergy_engine(assumptions: SynergyAssumptions):
    try:
        return {"status": "success", "synergy_analysis": calculate_synergies(assumptions)}
    except SynergyCalculationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Synergy engine failed: {exc}") from exc


# Phase 3 legal scan
@app.post(f"{settings.api_v1_prefix}/scan-document/")
async def scan_legal_document(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

    try:
        scan_results = process_and_scan_pdf(file_bytes, file.filename)
        return {"status": "success", "diligence_report": scan_results.model_dump()}
    except DocumentScannerConfigurationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except DocumentScannerDependencyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except DocumentScannerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Document scan failed: {exc}") from exc


@app.post(f"{settings.api_v1_prefix}/document-qa/")
async def document_qa(
    file: UploadFile = File(...),
    question: str = Form(..., min_length=3, max_length=500),
    top_k: int = Form(default=4, ge=1, le=8),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing file name.")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded document is empty.")
    try:
        answer = answer_question_from_document(file_bytes, file.filename, question, top_k=top_k)
        return {"status": "success", "qa": answer.model_dump()}
    except LocalQAError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Document Q&A failed: {exc}") from exc


# Phase 4/5 structuring
@app.post(f"{settings.api_v1_prefix}/structure-deal/")
def structure_ma_deal(payload: DealStructureInput):
    try:
        result = generate_deal_structure(payload)
        return {"status": "success", "deal_structure": result.model_dump()}
    except DealStructuringConfigurationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except DealStructuringError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Structuring engine failed: {exc}") from exc


# Phase 6 negotiation
@app.post(
    f"{settings.api_v1_prefix}/negotiation-strategy/",
    dependencies=[Depends(require_role("associate"))],
)
def calculate_negotiation_strategy(payload: NegotiationInput):
    try:
        result = generate_negotiation_strategy(payload)
        return {"status": "success", "negotiation_playbook": result.model_dump()}
    except NegotiationConfigurationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except NegotiationEngineError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Negotiation engine failed: {exc}") from exc


# Module 4 (Deep Dive) — E4 Temporal Risk Mapper
@app.post(
    f"{settings.api_v1_prefix}/modules/m4/temporal-risk-map",
    dependencies=[Depends(require_role("analyst"))],
)
def module4_temporal_risk_map(payload: TemporalRiskMapInput):
    return {
        "status": "success",
        "module": "m4_deep_dive",
        "temporal_risk_map": map_temporal_risks(payload.risks),
    }


# Module 6 (The Check) — LBO / acquisition-finance engine
@app.post(
    f"{settings.api_v1_prefix}/modules/m6/lbo",
    dependencies=[Depends(require_role("vp"))],
)
def module6_lbo(payload: LBOInput):
    try:
        return {"status": "success", "module": "m6_check", "lbo_analysis": calculate_lbo(payload)}
    except LBOFinancingError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LBO engine failed: {exc}") from exc


# Module 8 (The Reality) — PMI DNA Score (E6)
@app.post(
    f"{settings.api_v1_prefix}/modules/m8/pmi-dna-score",
    dependencies=[Depends(require_role("vp"))],
)
def module8_pmi_dna_score(payload: PMIDNAInput):
    return {"status": "success", "module": "m8_reality", "pmi_dna_score": calculate_pmi_dna_score(payload)}


# Module 8 (The Reality) — Synergy Realization Tracker
@app.post(
    f"{settings.api_v1_prefix}/deals/{{deal_id}}/synergy-realization",
    dependencies=[Depends(require_role("associate"))],
)
def add_synergy_realization(
    deal_id: str,
    payload: SynergyRealizationEntryInput,
    db: Session = Depends(get_db),
    user_role: str = Depends(get_current_role),
):
    if db.get(DealRecord, deal_id) is None:
        raise HTTPException(status_code=404, detail="Deal record not found.")
    entry = add_realization_entry(db, deal_id, payload)
    _write_audit_log(
        db=db,
        deal_id=deal_id,
        role=user_role,
        action="synergy_realization_entry",
        details=json.dumps({"category": payload.category, "month": payload.period_month}),
    )
    return {"status": "success", "entry": entry}


@app.get(
    f"{settings.api_v1_prefix}/deals/{{deal_id}}/synergy-realization",
    dependencies=[Depends(require_role("analyst"))],
)
def get_synergy_realization(deal_id: str, db: Session = Depends(get_db)):
    if db.get(DealRecord, deal_id) is None:
        raise HTTPException(status_code=404, detail="Deal record not found.")
    return {"status": "success", "dashboard": synergy_realization_dashboard(db, deal_id)}


# Module 7 (The Close) — Regulatory Horizon Engine (E5)
@app.post(
    f"{settings.api_v1_prefix}/modules/m7/regulatory-horizon",
    dependencies=[Depends(require_role("associate"))],
)
def module7_regulatory_horizon(payload: RegulatoryHorizonInput):
    return {"status": "success", "module": "m7_close", "regulatory_horizon": regulatory_horizon(payload)}


# Module 7 (The Close) — CFIUS screening
@app.post(
    f"{settings.api_v1_prefix}/modules/m7/cfius-screening",
    dependencies=[Depends(require_role("associate"))],
)
def module7_cfius_screening(payload: CFIUSInput):
    return {"status": "success", "module": "m7_close", "cfius": cfius_screening(payload)}


# Module 7 (The Close) — conditions-precedent / closing checklist
@app.post(
    f"{settings.api_v1_prefix}/modules/m7/closing-checklist",
    dependencies=[Depends(require_role("analyst"))],
)
def module7_closing_checklist(payload: ClosingChecklistInput):
    return {"status": "success", "module": "m7_close", "closing_checklist": closing_checklist(payload)}


# Per-deal module-output persistence (M1/M2/M6/M7 results stick to a deal)
@app.put(
    f"{settings.api_v1_prefix}/deals/{{deal_id}}/module-output",
    dependencies=[Depends(require_role("analyst"))],
)
def save_module_output(deal_id: str, payload: ModuleOutputInput, db: Session = Depends(get_db)):
    if db.get(DealRecord, deal_id) is None:
        raise HTTPException(status_code=404, detail="Deal record not found.")
    existing = (
        db.query(DealModuleOutput)
        .filter(DealModuleOutput.deal_id == deal_id, DealModuleOutput.module_key == payload.module_key)
        .one_or_none()
    )
    if existing is None:
        row = DealModuleOutput(deal_id=deal_id, module_key=payload.module_key, payload=payload.payload)
        db.add(row)
    else:
        existing.payload = payload.payload
        row = existing
    db.commit()
    db.refresh(row)
    return {"status": "success", "module_key": row.module_key, "updated_at": _iso_utc(row.updated_at)}


@app.get(
    f"{settings.api_v1_prefix}/deals/{{deal_id}}/module-outputs",
    dependencies=[Depends(require_role("analyst"))],
)
def get_module_outputs(deal_id: str, db: Session = Depends(get_db)):
    if db.get(DealRecord, deal_id) is None:
        raise HTTPException(status_code=404, detail="Deal record not found.")
    rows = db.query(DealModuleOutput).filter(DealModuleOutput.deal_id == deal_id).all()
    return {
        "status": "success",
        "deal_id": deal_id,
        "outputs": {r.module_key: {"payload": r.payload, "updated_at": _iso_utc(r.updated_at)} for r in rows},
    }


# Phase 7 orchestrator
@app.post(
    f"{settings.api_v1_prefix}/run-full-analysis/",
    response_model=MasterDiligenceReport,
    dependencies=[Depends(require_role("director"))],
)
async def run_full_orchestration(
    request: Request,
    company_a_file: UploadFile = File(...),
    company_b_file: UploadFile = File(...),
    orchestration_payload: str = Form(..., description="JSON string for FullAnalysisRequest"),
    legal_pdf: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    user_role: str = Depends(get_current_role),
):
    try:
        payload = FullAnalysisRequest.model_validate_json(orchestration_payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

    company_a_bytes = await company_a_file.read()
    company_b_bytes = await company_b_file.read()
    if not company_a_bytes or not company_b_bytes:
        raise HTTPException(status_code=400, detail="Both financial CSV uploads are required.")

    legal_pdf_bytes = None
    legal_pdf_name = None
    if legal_pdf is not None:
        legal_pdf_name = legal_pdf.filename
        legal_pdf_bytes = await legal_pdf.read()

    report = run_full_analysis(
        deal_id=str(uuid.uuid4()),
        company_a_bytes=company_a_bytes,
        company_b_bytes=company_b_bytes,
        payload=payload,
        legal_pdf_bytes=legal_pdf_bytes,
        legal_pdf_name=legal_pdf_name,
    )

    _save_master_report(db, report)
    _write_audit_log(
        db=db,
        deal_id=report.deal_id,
        role=user_role,
        action="run_full_analysis",
        details=json.dumps({"status_log_count": len(report.status_log)}),
    )

    return report


# Phase 8 pitchbook
@app.post(
    f"{settings.api_v1_prefix}/download-pitchbook/",
    dependencies=[Depends(require_role("associate"))],
)
def download_presentation(
    report: MasterDiligenceReport,
    background_tasks: BackgroundTasks,
):
    try:
        filepath = create_pitchbook(report)
        background_tasks.add_task(_safe_remove_file, filepath)
        return FileResponse(
            path=filepath,
            filename=f"MA_Pitchbook_{report.deal_id}.pptx",
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pitchbook generation failed: {exc}") from exc


@app.get(
    f"{settings.api_v1_prefix}/deals/{{deal_id}}/pitchbook",
    dependencies=[Depends(require_role("associate"))],
)
def download_presentation_from_deal(
    deal_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    record = db.get(DealRecord, deal_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Deal record not found.")
    report = MasterDiligenceReport(
        deal_id=record.id,
        company_a_financials=record.company_a_financials or {},
        company_b_financials=record.company_b_financials or {},
        valuation=record.valuation,
        synergies=record.synergies or {},
        legal_risks=record.legal_risks,
        deal_structure=record.deal_structure,
        negotiation_strategy=record.negotiation_strategy,
        status_log=record.status_log or [],
    )
    try:
        filepath = create_pitchbook(report)
        background_tasks.add_task(_safe_remove_file, filepath)
        return FileResponse(
            path=filepath,
            filename=f"MA_Pitchbook_{deal_id}.pptx",
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Pitchbook generation failed: {exc}") from exc


# Finnhub free market data (live quotes / financials / news)
@app.get(f"{settings.api_v1_prefix}/market/finnhub/status")
def finnhub_status():
    return {"status": "success", "configured": finnhub_is_configured(), "provider": "Finnhub", "free_tier": "60 calls/minute"}


@app.get(f"{settings.api_v1_prefix}/market/finnhub/quote/{{symbol}}")
def finnhub_quote(symbol: str):
    try:
        return {"status": "success", "quote": get_quote(symbol)}
    except FinnhubConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FinnhubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(f"{settings.api_v1_prefix}/market/finnhub/financials/{{symbol}}")
def finnhub_financials(symbol: str):
    try:
        return {"status": "success", "financials": get_basic_financials(symbol)}
    except FinnhubConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FinnhubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(f"{settings.api_v1_prefix}/market/finnhub/news/{{symbol}}")
def finnhub_news(symbol: str, days: int = Query(default=30, ge=1, le=365), limit: int = Query(default=20, ge=1, le=100)):
    try:
        return {"status": "success", "news": get_company_news(symbol, days=days, limit=limit)}
    except FinnhubConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FinnhubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# GDELT free global news (no key) — pairs with FinBERT for Sentiment Radar
@app.get(f"{settings.api_v1_prefix}/market/gdelt/news")
def gdelt_news(q: str = Query(..., min_length=2, max_length=200), max_records: int = Query(default=25, ge=1, le=250)):
    try:
        return {"status": "success", "news": gdelt_get_news(q, max_records=max_records)}
    except GdeltError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# USPTO PatentsView patent-velocity signal (free key)
@app.get(f"{settings.api_v1_prefix}/market/patents/status")
def patents_status():
    from app.services.patents import patentsview_configured, uspto_configured
    active = "USPTO Open Data Portal" if uspto_configured() else "Google Patents (keyless)"
    return {
        "status": "success",
        "configured": patents_is_configured(),  # always True — Google Patents is the keyless fallback
        "provider": active,
        "uspto_odp": uspto_configured(),
        "patentsview_fallback": patentsview_configured(),
    }


@app.get(f"{settings.api_v1_prefix}/market/patents/{{company}}")
def patents_velocity(company: str):
    try:
        return {"status": "success", "patents": get_patent_velocity(company)}
    except PatentsConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except PatentsError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# SEC EDGAR real M&A deal history (free, no key) — search + import into Deal Genome
@app.get(f"{settings.api_v1_prefix}/deal-genome/edgar/search")
def deal_genome_edgar_search(
    q: str = Query(default='"merger agreement"', min_length=2, max_length=200),
    forms: str = Query(default="8-K", max_length=60),
    start: str | None = Query(default=None, max_length=10),
    end: str | None = Query(default=None, max_length=10),
    limit: int = Query(default=20, ge=1, le=100),
):
    try:
        return {"status": "success", "filings": search_ma_filings(q, forms=forms, start=start, end=end, limit=limit)}
    except EdgarError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post(
    f"{settings.api_v1_prefix}/deal-genome/edgar/import",
    dependencies=[Depends(require_role("associate"))],
)
def deal_genome_edgar_import(
    q: str = Query(default='"merger agreement"', min_length=2, max_length=200),
    forms: str = Query(default="8-K", max_length=60),
    start: str | None = Query(default=None, max_length=10),
    end: str | None = Query(default=None, max_length=10),
    limit: int = Query(default=20, ge=1, le=100),
    enrich: bool = Query(default=False, description="Also parse each filing for a best-effort deal value (slower)."),
    db: Session = Depends(get_db),
):
    try:
        return {"status": "success", "result": import_ma_filings_to_genome(db, q, forms=forms, start=start, end=end, limit=limit, enrich=enrich)}
    except EdgarError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# FinBERT financial-sentiment (E2 Sentiment Radar) — over provided texts or Finnhub news
@app.post(
    f"{settings.api_v1_prefix}/modules/m1/news-sentiment",
    dependencies=[Depends(require_role("analyst"))],
)
def module1_news_sentiment(payload: NewsSentimentInput):
    texts = list(payload.texts)
    news_source = "provided_texts"
    if payload.source == "gdelt" and payload.company:
        try:
            news = gdelt_get_news(payload.company, max_records=50)
            texts = [a["title"] for a in news["articles"] if a.get("title")] or texts
            news_source = "gdelt_news"
        except GdeltError as exc:
            if not texts:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
    elif payload.symbol:
        try:
            news = get_company_news(payload.symbol, days=payload.days, limit=50)
            texts = [f"{a['headline']}. {a['summary']}".strip() for a in news["articles"] if a.get("headline")]
            news_source = "finnhub_company_news"
        except FinnhubConfigurationError as exc:
            if not texts:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
        except FinnhubError as exc:
            if not texts:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
    if not texts:
        raise HTTPException(status_code=422, detail="No texts available to analyze.")
    try:
        result = finbert_analyze(texts)
    except FinBertUnavailableError as exc:
        raise HTTPException(status_code=503, detail=f"FinBERT unavailable: {exc}") from exc
    return {"status": "success", "module": "m1_hunt", "news_source": news_source, "sentiment": result}


@app.get(f"{settings.api_v1_prefix}/public-data/references")
def public_data_references():
    return {"status": "success", "references": get_reference_datasets()}


@app.get(f"{settings.api_v1_prefix}/public-data/fred/{{series_id}}")
def public_data_fred(series_id: str, limit: int = Query(default=20, ge=1, le=200)):
    try:
        return {"status": "success", "data": get_fred_series(series_id=series_id, limit=limit).model_dump()}
    except PublicDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(f"{settings.api_v1_prefix}/public-data/treasury-yields")
def public_data_treasury(limit: int = Query(default=20, ge=1, le=200)):
    try:
        return {"status": "success", "data": get_treasury_yields(limit=limit).model_dump()}
    except PublicDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(f"{settings.api_v1_prefix}/public-data/stooq/{{symbol}}")
def public_data_stooq(symbol: str, limit: int = Query(default=20, ge=1, le=200)):
    try:
        return {"status": "success", "data": get_stooq_prices(symbol=symbol, limit=limit).model_dump()}
    except PublicDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(f"{settings.api_v1_prefix}/public-data/sec/companyfacts/{{cik}}")
def public_data_sec_companyfacts(cik: str):
    try:
        return {"status": "success", "data": get_sec_companyfacts(cik)}
    except PublicDataError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get(f"{settings.api_v1_prefix}/synthetic-data")
def synthetic_data_index():
    return {"status": "success", "datasets": list_synthetic_datasets()}


@app.get(f"{settings.api_v1_prefix}/synthetic-data/{{dataset_name}}")
def synthetic_data_payload(dataset_name: str):
    try:
        return {"status": "success", "dataset": load_synthetic_dataset(dataset_name)}
    except SyntheticDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get(f"{settings.api_v1_prefix}/deal-genome/summary", response_model=DealGenomeSummaryResponse)
def deal_genome_summary(db: Session = Depends(get_db)):
    return summarize_deal_genome(db)


@app.get(f"{settings.api_v1_prefix}/deal-genome/transactions")
def deal_genome_transactions(
    q: str | None = None,
    sector: str | None = None,
    country: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return {
        "status": "success",
        "transactions": [item.model_dump() for item in list_transactions(db, q=q, sector=sector, country=country, limit=limit)],
    }


@app.post(
    f"{settings.api_v1_prefix}/deal-genome/transactions",
    dependencies=[Depends(require_role("associate"))],
)
def deal_genome_create_transaction(payload: HistoricalTransactionInput, db: Session = Depends(get_db)):
    return {"status": "success", "transaction": create_or_update_transaction(db, payload).model_dump()}


@app.post(
    f"{settings.api_v1_prefix}/deal-genome/import-csv",
    dependencies=[Depends(require_role("associate"))],
)
async def deal_genome_import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded CSV is empty.")
    try:
        return {"status": "success", "result": import_transactions_csv(db, file_bytes)}
    except DealGenomeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    f"{settings.api_v1_prefix}/deal-genome/seed-sample",
    dependencies=[Depends(require_role("associate"))],
    response_model=DealGenomeSummaryResponse,
)
def deal_genome_seed_sample(db: Session = Depends(get_db)):
    return seed_sample_transactions(db)


@app.get(f"{settings.api_v1_prefix}/company-map/search")
def company_map_search(
    q: str | None = Query(default=None, description="Company name, ticker, sector, city, country, LEI, or registration number"),
    country: str | None = None,
    sector: str | None = None,
    company_size: str | None = None,
    public_private: str | None = None,
    listed_exchange: str | None = None,
    mna_signal: str | None = None,
    distress_signal: str | None = None,
    ipo_public_company: bool | None = None,
    marker_role: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
):
    return search_companies(
        q=q,
        country=country,
        sector=sector,
        company_size=company_size,
        public_private=public_private,
        listed_exchange=listed_exchange,
        mna_signal=mna_signal,
        distress_signal=distress_signal,
        ipo_public_company=ipo_public_company,
        marker_role=marker_role,
        limit=limit,
    )


@app.get(f"{settings.api_v1_prefix}/company-map/viewport")
def company_map_viewport(
    north: float = Query(..., ge=-90.0, le=90.0),
    south: float = Query(..., ge=-90.0, le=90.0),
    east: float = Query(..., ge=-180.0, le=180.0),
    west: float = Query(..., ge=-180.0, le=180.0),
    q: str | None = None,
    country: str | None = None,
    sector: str | None = None,
    company_size: str | None = None,
    public_private: str | None = None,
    listed_exchange: str | None = None,
    mna_signal: str | None = None,
    distress_signal: str | None = None,
    ipo_public_company: bool | None = None,
    marker_role: str | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
):
    if south > north:
        raise HTTPException(status_code=422, detail="south cannot exceed north.")
    return viewport_companies(
        north=north,
        south=south,
        east=east,
        west=west,
        q=q,
        country=country,
        sector=sector,
        company_size=company_size,
        public_private=public_private,
        listed_exchange=listed_exchange,
        mna_signal=mna_signal,
        distress_signal=distress_signal,
        ipo_public_company=ipo_public_company,
        marker_role=marker_role,
        limit=limit,
    )


@app.get(f"{settings.api_v1_prefix}/company-map/company/{{company_id}}")
def company_map_company(company_id: str):
    profile = get_company_profile(company_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Company profile not found.")
    return profile


@app.get(f"{settings.api_v1_prefix}/companies")
def companies_viewport(
    south: float = Query(..., ge=-90.0, le=90.0),
    west: float = Query(..., ge=-180.0, le=180.0),
    north: float = Query(..., ge=-90.0, le=90.0),
    east: float = Query(..., ge=-180.0, le=180.0),
):
    # Prevent very large bboxes which commonly cause Overpass to reject the query
    lat_span = abs(north - south)
    lon_span = abs(east - west)
    MAX_SPAN_DEGREES = 4.0
    MAX_AREA_DEGREES = 25.0
    if lat_span > MAX_SPAN_DEGREES or lon_span > MAX_SPAN_DEGREES or (lat_span * lon_span) > MAX_AREA_DEGREES:
        raise HTTPException(
            status_code=422,
            detail=(
                "Bounding box too large for live Overpass queries. "
                "Please zoom in or reduce the viewport size (max ~4° span or ~25° area)."
            ),
        )
    try:
        results = query_companies(south=south, west=west, north=north, east=east)
        return {"status": "success", "companies": results, "count": len(results)}
    except OverpassError as exc:
        # Try a local sample fallback to keep the UI functional when Overpass is unavailable
        try:
            sample_path = Path(__file__).resolve().parents[1] / "runtime_artifacts" / "companies.json"
            if sample_path.exists():
                with open(sample_path, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                companies = []
                for c in payload.get("companies", []):
                    lat = c.get("lat") or c.get("latitude") or c.get("lat")
                    lng = c.get("lng") or c.get("longitude") or c.get("lng")
                    if lat is None or lng is None:
                        continue
                    if south <= float(lat) <= north and west <= float(lng) <= east:
                        companies.append(
                            {
                                "id": c.get("id"),
                                "name": c.get("name"),
                                "latitude": float(lat),
                                "longitude": float(lng),
                                "category": c.get("sector") or c.get("marker_role") or "company",
                                "address": c.get("city") or c.get("headquarters") or None,
                                "raw_tags": {},
                            }
                        )
                return {"status": "fallback", "companies": companies, "count": len(companies)}
        except Exception:
            pass
        raise HTTPException(status_code=503, detail=f"Overpass service unavailable: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch companies: {exc}") from exc


@app.get(f"{settings.api_v1_prefix}/market-data/summary")
def get_market_data_summary():
    return market_data_summary()


@app.get(
    f"{settings.api_v1_prefix}/deals/{{deal_id}}",
    dependencies=[Depends(require_role("analyst"))],
)
def get_deal(deal_id: str, db: Session = Depends(get_db)):
    record = db.get(DealRecord, deal_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Deal record not found.")
    return {
        "id": record.id,
        "deal_name": record.deal_name,
        "stage": record.stage,
        "status": record.status,
        "company_a_financials": record.company_a_financials,
        "company_b_financials": record.company_b_financials,
        "valuation": record.valuation,
        "synergies": record.synergies,
        "legal_risks": record.legal_risks,
        "deal_structure": record.deal_structure,
        "negotiation_strategy": record.negotiation_strategy,
        "status_log": record.status_log,
        "created_at": _iso_utc(record.created_at),
        "updated_at": _iso_utc(record.updated_at),
    }


@app.get(
    f"{settings.api_v1_prefix}/deals",
    dependencies=[Depends(require_role("analyst"))],
)
def list_deals(limit: int = Query(default=20, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.query(DealRecord).order_by(DealRecord.created_at.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "deal_name": r.deal_name,
            "stage": r.stage,
            "status": r.status,
            "created_at": _iso_utc(r.created_at),
            "updated_at": _iso_utc(r.updated_at),
        }
        for r in rows
    ]
