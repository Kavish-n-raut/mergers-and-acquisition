# QuantumBlack M&A Deal OS (PRD v3.0 Implementation MVP)

This repository contains a functional implementation MVP derived from `QuantumBlack_MADealOS_PRD_v3.pdf`:
- 8-phase lifecycle model (M1-M8) with stage transitions
- strict Pydantic contracts
- fault-tolerant orchestration
- deterministic financial boundaries
- local/free AI-alternative legal and strategy layers (Anthropic optional)
- war-room messaging (REST + WebSocket)
- deal persistence + audit logs

## 🚀 Live Demo

**App:** https://mergers-and-acquisition-ashy.vercel.app

**Sign in** with any role — username is the role, password is `<username>@100`:

| Username | Password | Role |
|---|---|---|
| `director` | `director@100` | Director (recommended) |
| `analyst` · `associate` · `vp` · `md` · `admin` | `<username>@100` | escalating access |

> Demo credentials only — a real deployment must replace the demo user store and rotate `JWT_SECRET`.

**Deployed architecture (all free tier):**
- **Frontend:** React + Vite on **Vercel**
- **Backend:** FastAPI (Docker) on **Render**
- **Database:** **Neon** serverless Postgres
- **LLM:** **Groq** (`openai/gpt-oss-120b`, free) for document/strategy generation
- **Live data (free, no paid subscriptions):** Finnhub (market), GDELT (news), USPTO (patents), SEC EDGAR (real M&A filings)
- First request after ~15 min idle may take ~40s (Render free-tier cold start); a scheduled ping keeps it warm.

## Stack
- Backend: Python, FastAPI, Pydantic v2, SQLAlchemy
- AI/RAG: local deterministic pipeline by default, Anthropic Claude optional
- Async: Celery + Redis (skeleton)
- Output automation: python-pptx
- Frontend: React + Vite

## Quick Start

### 1) Backend
```bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --port 8000
```

Open docs at `http://127.0.0.1:8000/docs`

> **Windows note — do not use `--reload` with the Microsoft Store Python.**
> Under the sandboxed Store Python (`...\WindowsApps\PythonSoftwareFoundation.Python...`),
> uvicorn's reloader spawns a multiprocessing child that cannot create named pipes,
> producing an infinite `PermissionError: [WinError 5]` loop that writes gigabytes to the
> error log. Always launch through the project's own venv interpreter
> (`python -m uvicorn ...`, i.e. `backend\.venv\Scripts\python.exe`) and omit `--reload`,
> or install a standard python.org build if you need auto-reload. The bundled
> `.claude/launch.json` `backend` profile already uses the venv interpreter without `--reload`.

### Local/Free mode (default)
- `AI_PROVIDER=local` and `USE_ANTHROPIC=false` are the defaults.
- No Anthropic key is required for:
  - document scanning (rule-based),
  - deal structuring (deterministic),
  - negotiation playbook (rule-based + hard math),
  - document Q&A retrieval,
  - NDA/LOI drafting templates.
- Free/public source integration available in API:
  - SEC EDGAR (`/public-data/sec/companyfacts/{cik}`)
  - FRED (`/public-data/fred/{series_id}`)
  - U.S. Treasury FiscalData (`/public-data/treasury-yields`)
  - Stooq (`/public-data/stooq/{symbol}`)
  - Reference links for Damodaran, CUAD, SEC exhibits, FTC/EU/CMA/CFIUS (`/public-data/references`)

### Free upgrades (optional, no paid subscriptions)
- **Finnhub live market data** (free key, 60 calls/min — a Bloomberg/CapIQ stand-in):
  set `FINNHUB_API_KEY` from https://finnhub.io. Endpoints:
  `/market/finnhub/status`, `/market/finnhub/quote/{symbol}`,
  `/market/finnhub/financials/{symbol}`, `/market/finnhub/news/{symbol}`.
  Without a key these report `configured: false` instead of failing.
- **FinBERT financial sentiment** (free Hugging Face model, ~440MB on first use —
  powers Sentiment Radar/E2): `POST /modules/m1/news-sentiment` with
  `{"texts": [...]}`, or `{"symbol": "AAPL"}` to score live Finnhub company news.
  Falls back cleanly if the model can't load.
- **Neon / Supabase free Postgres** (cloud-ready database): paste the connection
  string into `DATABASE_URL` — a plain `postgres://`/`postgresql://` URL is
  auto-routed to the installed psycopg v3 driver, no code change needed.
- **GDELT global news** (free, **no key** — NewsAPI stand-in): `/market/gdelt/news?q=...`;
  or `POST /modules/m1/news-sentiment` with `{"source":"gdelt","company":"Acme"}`
  to score GDELT headlines through FinBERT. (GDELT throttles ~1 request/5s per IP.)
- **SEC EDGAR real M&A deal history** (free, **no key** — feeds the Deal Genome/E1
  with real deals instead of synthetic): `/deal-genome/edgar/search?q=...` to preview,
  `POST /deal-genome/edgar/import?q=...` to write real filings into the
  `historical_transactions` table.
- **USPTO PatentsView patent velocity** (free key — R&D-momentum signal):
  set `PATENTSVIEW_API_KEY`; `/market/patents/{company}`.

### Optional Anthropic premium mode
Set all three:
```bash
AI_PROVIDER=anthropic
USE_ANTHROPIC=true
ANTHROPIC_API_KEY=sk-ant-...
```

### 2) Frontend
```bash
cd frontend
npm install
copy .env.example .env
npm run dev
```

Open app at `http://127.0.0.1:5173`

## Key Endpoints
- `POST /api/v1/auth/login` (JWT login — returns a Bearer token)
- `GET /api/v1/auth/me` (current role from token/header)
- `POST /api/v1/deals`
- `GET /api/v1/health/llm`
- `PATCH /api/v1/deals/{deal_id}/stage`
- `GET /api/v1/deals/{deal_id}/war-room/messages`
- `POST /api/v1/deals/{deal_id}/war-room/messages`
- `WS  /api/v1/ws/war-room/{deal_id}`
- `POST /api/v1/modules/m1/screen-targets`
- `POST /api/v1/draft-document/`
- `POST /api/v1/financial/ratios`
- `POST /api/v1/valuation/dcf`
- `POST /api/v1/valuation/dcf-drivers` (driver-based DCF, Base/Bull/Bear — M3)
- `POST /api/v1/calculate-synergies/`
- `POST /api/v1/modules/m4/temporal-risk-map` (E4 Temporal Risk Mapper)
- `POST /api/v1/modules/m6/lbo` (M6 LBO / IRR / capital-stack engine)
- `POST /api/v1/modules/m8/pmi-dna-score` (E6 PMI DNA Score)
- `POST /api/v1/deals/{deal_id}/synergy-realization` (M8 tracker — add monthly actuals)
- `GET  /api/v1/deals/{deal_id}/synergy-realization` (M8 tracker — variance dashboard)
- `POST /api/v1/scan-document/`
- `POST /api/v1/document-qa/`
- `POST /api/v1/structure-deal/`
- `POST /api/v1/negotiation-strategy/`
- `POST /api/v1/run-full-analysis/`
- `POST /api/v1/download-pitchbook/`
- `GET /api/v1/deals/{deal_id}/pitchbook`
- `GET /api/v1/public-data/references`
- `GET /api/v1/public-data/fred/{series_id}`
- `GET /api/v1/public-data/treasury-yields`
- `GET /api/v1/public-data/stooq/{symbol}`
- `GET /api/v1/public-data/sec/companyfacts/{cik}`
- `GET /api/v1/synthetic-data`
- `GET /api/v1/synthetic-data/{dataset_name}`

## Tests
```bash
cd backend
pytest -q
```

The default suite is fast (SQLite in-memory, deterministic engines). The
embedding/FAISS semantic-retrieval tests are skipped by default because they load
`torch` + a sentence-transformer model (~2 min). Run them explicitly with:
```bash
RUN_SEMANTIC_TESTS=1 pytest -q tests/test_embeddings.py
```

## Notes
- Anthropic is optional; free/local mode is default and fully functional.
- If Anthropic mode is enabled without a valid key, only Anthropic-specific calls degrade.
- Orchestrator is stage-fault-tolerant: if legal scan fails, downstream finance/strategy still return.
- DB defaults to SQLite for local dev. Set `DATABASE_URL` for PostgreSQL.
- Role-based access is enforced at the API layer. Two modes:
  - **Dev (default, `AUTH_ENFORCED=false`)**: send role via the `x-user-role` header (`analyst|associate|vp|director|md|admin`).
  - **Auth (`AUTH_ENFORCED=true`, used in the live deployment)**: obtain a signed JWT from `POST /api/v1/auth/login` (demo users are the role names above, password `<username>@100`, e.g. `director@100`), then send `Authorization: Bearer <token>`. A valid Bearer token always takes precedence over the header. Tokens expire after `JWT_EXPIRE_MINUTES` (default 8h); an expired/invalid token returns 401 and the UI drops back to the login screen. Change `JWT_SECRET` and the demo passwords before any real deployment.
