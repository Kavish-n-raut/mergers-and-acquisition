import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000",
  timeout: 60000,
  headers: {
    "x-user-role": "director",
  },
});

// --- Authentication (JWT) ---------------------------------------------------
const SESSION_KEY = "authSession";

export function getSession() {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY)) || null;
  } catch {
    return null;
  }
}

function applyToken(token) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common["Authorization"];
  }
}

export async function login(username, password) {
  const res = await api.post("/api/v1/auth/login", { username, password });
  const session = { token: res.data.access_token, username: res.data.username, role: res.data.role };
  applyToken(session.token);
  try {
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    /* storage unavailable — session lives for this tab only */
  }
  return session;
}

export function logout() {
  applyToken(null);
  try {
    localStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}

// Restore a persisted session on module load so a reload keeps the user signed in.
const _restored = getSession();
if (_restored?.token) applyToken(_restored.token);

// A stored JWT expires (8h) while its presence still gates the UI, so a returning
// user would otherwise sit on a stale dashboard while every call 401s. On any 401
// (except the login call itself), clear the session and signal the app to show the
// login screen — a clean "your session expired, sign in again" instead of broken data.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status;
    const url = error?.config?.url || "";
    if (status === 401 && !url.includes("/auth/login")) {
      logout();
      try {
        window.dispatchEvent(new Event("auth:expired"));
      } catch {
        /* non-browser context */
      }
    }
    return Promise.reject(error);
  },
);

export async function getHealth() {
  const res = await api.get("/api/v1/health");
  return res.data;
}

export async function getLlmHealth() {
  const res = await api.get("/api/v1/health/llm");
  return res.data;
}

export async function listDeals(limit = 50) {
  const res = await api.get(`/api/v1/deals?limit=${limit}`);
  return res.data;
}

export async function createDeal(dealName) {
  const res = await api.post("/api/v1/deals", { deal_name: dealName });
  return res.data;
}

export async function getDeal(dealId) {
  const res = await api.get(`/api/v1/deals/${dealId}`);
  return res.data;
}

export async function runFullAnalysis(formData) {
  const res = await api.post("/api/v1/run-full-analysis/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function draftDocument(payload) {
  const res = await api.post("/api/v1/draft-document/", payload, {
    headers: {
      "x-user-role": "associate",
    },
  });
  return res.data;
}

export async function getPublicReferences() {
  const res = await api.get("/api/v1/public-data/references");
  return res.data;
}

export async function getMarketDataSummary() {
  const res = await api.get("/api/v1/market-data/summary");
  return res.data;
}

export async function getMarketAssumptions(params = {}) {
  const res = await api.get("/api/v1/valuation/market-assumptions", { params });
  return res.data;
}

export async function getDealGenomeSummary() {
  const res = await api.get("/api/v1/deal-genome/summary");
  return res.data;
}

export async function getDealIntelligence(payload) {
  const res = await api.post("/api/v1/ml/deal-intelligence", payload);
  return res.data;
}

// --- Free data sources (Finnhub, FinBERT/GDELT sentiment, USPTO, SEC EDGAR) ---
export async function getFinnhubStatus() {
  const res = await api.get("/api/v1/market/finnhub/status");
  return res.data;
}

export async function getFinnhubQuote(symbol) {
  const res = await api.get(`/api/v1/market/finnhub/quote/${encodeURIComponent(symbol)}`);
  return res.data;
}

export async function getFinnhubFinancials(symbol) {
  const res = await api.get(`/api/v1/market/finnhub/financials/${encodeURIComponent(symbol)}`);
  return res.data;
}

export async function getNewsSentiment(payload) {
  const res = await api.post("/api/v1/modules/m1/news-sentiment", payload);
  return res.data;
}

export async function getGdeltNews(q, maxRecords = 25) {
  const res = await api.get("/api/v1/market/gdelt/news", { params: { q, max_records: maxRecords } });
  return res.data;
}

export async function getPatentsStatus() {
  const res = await api.get("/api/v1/market/patents/status");
  return res.data;
}

export async function getPatentVelocity(company) {
  const res = await api.get(`/api/v1/market/patents/${encodeURIComponent(company)}`);
  return res.data;
}

export async function searchEdgarDeals(params = {}) {
  const res = await api.get("/api/v1/deal-genome/edgar/search", { params });
  return res.data;
}

export async function importEdgarDeals(params = {}) {
  const res = await api.post("/api/v1/deal-genome/edgar/import", null, { params });
  return res.data;
}

export async function saveModuleOutput(dealId, moduleKey, payload) {
  const res = await api.put(`/api/v1/deals/${dealId}/module-output`, { module_key: moduleKey, payload });
  return res.data;
}

export async function getModuleOutputs(dealId) {
  const res = await api.get(`/api/v1/deals/${dealId}/module-outputs`);
  return res.data;
}

export async function listDealGenomeTransactions(params = {}) {
  const res = await api.get("/api/v1/deal-genome/transactions", { params });
  return res.data;
}

export async function seedDealGenomeSample() {
  const res = await api.post("/api/v1/deal-genome/seed-sample");
  return res.data;
}

export async function searchCompanyMap(params = {}) {
  const res = await api.get("/api/v1/company-map/search", { params });
  return res.data;
}

export async function getCompanyMapViewport(params = {}) {
  const res = await api.get("/api/v1/company-map/viewport", { params });
  return res.data;
}

export async function getCompaniesBBox(params = {}) {
  const res = await api.get("/api/v1/companies", { params });
  return res.data;
}

export async function getCompanyProfile(companyId) {
  const res = await api.get(`/api/v1/company-map/company/${companyId}`);
  return res.data;
}

export async function downloadPitchbook(report) {
  const res = await api.post("/api/v1/download-pitchbook/", report, {
    responseType: "blob",
    headers: {
      "x-user-role": "associate",
    },
  });
  return res.data;
}

export async function listWarRoomMessages(dealId) {
  const res = await api.get(`/api/v1/deals/${dealId}/war-room/messages`);
  return res.data;
}

export async function postWarRoomMessage(dealId, senderName, content) {
  const res = await api.post(`/api/v1/deals/${dealId}/war-room/messages`, {
    sender_name: senderName,
    content,
  });
  return res.data;
}

export async function runLboAnalysis(payload) {
  const res = await api.post("/api/v1/modules/m6/lbo", payload, {
    headers: { "x-user-role": "vp" },
  });
  return res.data;
}

export async function runDriverDcf(payload) {
  const res = await api.post("/api/v1/valuation/dcf-drivers", payload);
  return res.data;
}

export async function mapTemporalRisks(risks) {
  const res = await api.post("/api/v1/modules/m4/temporal-risk-map", { risks });
  return res.data;
}

export async function getPmiDnaScore(payload) {
  const res = await api.post("/api/v1/modules/m8/pmi-dna-score", payload, {
    headers: { "x-user-role": "vp" },
  });
  return res.data;
}

export async function addSynergyRealization(dealId, payload) {
  const res = await api.post(`/api/v1/deals/${dealId}/synergy-realization`, payload, {
    headers: { "x-user-role": "associate" },
  });
  return res.data;
}

export async function getSynergyRealization(dealId) {
  const res = await api.get(`/api/v1/deals/${dealId}/synergy-realization`);
  return res.data;
}

export async function screenTargets(payload) {
  const res = await api.post("/api/v1/modules/m1/screen-targets", payload);
  return res.data;
}

export async function normalizeFinancials(payload) {
  const res = await api.post("/api/v1/modules/m2/normalize-financials", payload);
  return res.data;
}

export async function buildAdvisorGraph(payload) {
  const res = await api.post("/api/v1/modules/m2/advisor-graph", payload);
  return res.data;
}

export async function runRegulatoryHorizon(payload) {
  const res = await api.post("/api/v1/modules/m7/regulatory-horizon", payload);
  return res.data;
}

export async function runCfiusScreening(payload) {
  const res = await api.post("/api/v1/modules/m7/cfius-screening", payload);
  return res.data;
}

export async function buildClosingChecklist(payload) {
  const res = await api.post("/api/v1/modules/m7/closing-checklist", payload);
  return res.data;
}

export function warRoomWebSocketUrl(dealId) {
  const base = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000")
    .replace("http://", "ws://")
    .replace("https://", "wss://");
  return `${base}/api/v1/ws/war-room/${dealId}`;
}
