# QuantumBlack M&A Deal OS - Architecture (v3.0 Build)

## Context
This implementation is based on `QuantumBlack_MADealOS_PRD_v3.pdf` (May 2026) and targets:
- 8 lifecycle modules (M1-M8)
- proprietary intelligence-assisted workflows
- FastAPI-first backend with strict Pydantic schemas
- fault-tolerant orchestration for partial-success execution

## Implemented Layers
- `backend/app/main.py`: FastAPI orchestrator and module endpoints
- `backend/app/schemas.py`: strict request/response contracts
- `backend/app/services/*`: financial, legal scan, synergy, structuring, negotiation, pitchbook
- `backend/app/db/*`: stateful deal thread persistence (PostgreSQL-ready, SQLite dev fallback)
- `backend/app/core/rbac.py`: API-layer role gating (no UI-only enforcement)
- `backend/app/tasks/*`: Celery + Redis async task skeleton

## Lifecycle Mapping
- M1 Hunt: target screening placeholder endpoint
- M2 Approach: target intake + NDA workflow placeholder endpoint
- M3 Handshake: valuation, LOI, initial terms via financial + structuring engines
- M4 Deep Dive: document scanner (RAG/FAISS) with strict schema output
- M5 War Room: negotiation strategy bounded by deterministic walk-away math
- M6 Check: financing/capital checks represented through structuring and negotiation constraints
- M7 Close: orchestrated synthesis + board-ready payload
- M8 Reality: pitchbook generation + status traceability for post-close workflows

## Design Principles
- Stateful deal thread persisted via DB model
- Ephemeral document vectors (session-scoped)
- Explainability-friendly JSON outputs
- Fault tolerance by stage-level exception boundaries
- Deterministic math for financial boundaries (no LLM math authority)
