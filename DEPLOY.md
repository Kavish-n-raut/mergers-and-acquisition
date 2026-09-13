# Deploying the M&A Deal OS (free tier)

The whole platform can run on free tiers: **Neon** (Postgres) + **Render** (backend API + static frontend).
None of this needs paid infrastructure. Accounts must be created by you (sign-up + password);
once created, everything below is copy-paste.

---

## 1. Database — Neon (free Postgres)
1. Sign up at https://neon.tech and create a project.
2. Copy the connection string (looks like `postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require`).
3. You'll paste it into the backend's `DATABASE_URL` (step 3). The app auto-routes it to the
   psycopg v3 driver — no code change needed. Tables auto-create on first startup.

## 2. Push the repo to GitHub
Render deploys from a Git repo. This project isn't a git repo yet:
```bash
git init && git add . && git commit -m "Deploy"
```
Create a GitHub repo and push. (Secrets are safe: `.env` and `*.db` are gitignored.)

## 3. Backend + Frontend — Render (Blueprint)
1. Sign up at https://render.com and connect your GitHub.
2. **New → Blueprint** → pick the repo. Render reads `render.yaml` and creates two services.
3. Fill the env vars it prompts for (marked `sync: false`):
   - **Backend** (`madealos-backend`):
     - `DATABASE_URL` = your Neon string
     - `DEMO_PASSWORD` = a login password of your choice
     - `CORS_ORIGINS` = your frontend URL, e.g. `https://madealos-frontend.onrender.com`
     - (optional) `FINNHUB_API_KEY`, `GROQ_API_KEY`, `PATENTSVIEW_API_KEY`
     - `JWT_SECRET` is generated automatically; `AUTH_ENFORCED` is preset to `true`.
   - **Frontend** (`madealos-frontend`):
     - `VITE_API_BASE_URL` = your backend URL, e.g. `https://madealos-backend.onrender.com`
4. Deploy. Log in at the frontend URL with any role name (`director`, etc.) + your `DEMO_PASSWORD`.

---

## Important notes
- **Set `VITE_API_BASE_URL` before the frontend build** — the SPA bakes it in at build time; without it, it calls `localhost:8000`.
- **`CORS_ORIGINS` must include the exact frontend origin**, or the browser blocks API calls.
- **`AUTH_ENFORCED=true`** means the app requires a real JWT (from `/auth/login`); the dev-only `x-user-role` header is rejected. Good for production.
- **Heavy image caveat**: `backend/requirements.txt` includes the FinBERT/embeddings ML stack (torch/transformers/faiss, ~2–3 GB). If the free-tier build fails on size/time:
  - Upgrade the Render instance, **or**
  - Deploy a slim image without `torch`, `transformers`, `faiss-cpu`, `sentence-transformers` (add `scikit-learn` + `joblib` explicitly, since they were transitive). FinBERT sentiment and semantic diligence retrieval then **fall back to keyword mode automatically** — everything else (including Groq AI, all engines, EDGAR/GDELT/Finnhub) works unchanged.
- **Neon free tier scales to zero** — the first request after idle may take a few seconds to wake; `pool_pre_ping` already handles reconnects.

## Alternative hosts
- **Fly.io** (backend Docker) + **Netlify/Vercel** (frontend static) work the same way — same env vars, same `VITE_API_BASE_URL` / `CORS_ORIGINS` rules.
