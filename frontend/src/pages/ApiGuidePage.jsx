import React, { useState } from "react";
import { draftDocument, getPublicReferences } from "../lib/api";

const endpoints = [
  "GET /api/v1/health",
  "GET /api/v1/health/llm",
  "POST /api/v1/deals",
  "POST /api/v1/run-full-analysis/",
  "POST /api/v1/scan-document/",
  "POST /api/v1/document-qa/",
  "POST /api/v1/draft-document/",
  "GET /api/v1/public-data/fred/{series_id}",
  "GET /api/v1/public-data/treasury-yields",
  "GET /api/v1/public-data/stooq/{symbol}",
  "GET /api/v1/public-data/sec/companyfacts/{cik}",
  "GET /api/v1/public-data/references",
];

const defaultDraft = {
  document_type: "LOI",
  deal_name: "Northbridge Industrial Acquisition",
  buyer_name: "Apex Strategic Holdings",
  seller_name: "Meridian Industrial Group",
  jurisdiction: "Delaware",
  purchase_price: 45000000,
  exclusivity_days: 45,
};

export default function ApiGuidePage() {
  const [draftPayload, setDraftPayload] = useState(JSON.stringify(defaultDraft, null, 2));
  const [draftResult, setDraftResult] = useState("");
  const [refsResult, setRefsResult] = useState("");
  const [error, setError] = useState("");

  const runDraft = async () => {
    setError("");
    setDraftResult("");
    try {
      const payload = JSON.parse(draftPayload);
      const res = await draftDocument(payload);
      setDraftResult(JSON.stringify(res, null, 2));
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Term sheet draft generation failed.");
    }
  };

  const loadReferences = async () => {
    setError("");
    setRefsResult("");
    try {
      const res = await getPublicReferences();
      setRefsResult(JSON.stringify(res, null, 2));
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Reference data lookup failed.");
    }
  };

  return (
    <div className="page-grid">
      <section className="panel">
        <div className="panel-header">
          <h2>API Operations Console</h2>
          <span className="chip">Local and Institutional Modes</span>
        </div>
        <ul className="endpoint-list">
          {endpoints.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      </section>

      <section className="panel">
        <div className="panel-header">
          <h3>NDA and LOI Drafting Sandbox</h3>
          <span className="chip chip-live">No External Key Required</span>
        </div>
        <textarea rows={14} value={draftPayload} onChange={(e) => setDraftPayload(e.target.value)} />
        <div className="inline-form">
          <button onClick={runDraft}>Generate Draft</button>
          <button className="ghost-btn" onClick={loadReferences}>
            Fetch Public Data Sources
          </button>
        </div>
        {error && <p className="error-text">{error}</p>}
      </section>

      {(draftResult || refsResult) && (
        <section className="panel">
          <div className="panel-header">
            <h3>Console Output</h3>
            <span className="chip">JSON</span>
          </div>
          {draftResult && (
            <>
              <h4>Draft Output</h4>
              <pre className="json-view">{draftResult}</pre>
            </>
          )}
          {refsResult && (
            <>
              <h4>Public Data Reference Catalog</h4>
              <pre className="json-view">{refsResult}</pre>
            </>
          )}
        </section>
      )}
    </div>
  );
}
