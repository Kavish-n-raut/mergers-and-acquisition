import React, { useState } from "react";
import { DEMO_CLOSING_CHECKLIST, formatCurrency, formatPercent, getActiveDealMeta, getActiveReport, saveActiveReport } from "../lib/dealUtils";
import { buildClosingChecklist, runCfiusScreening, runRegulatoryHorizon, saveModuleOutput } from "../lib/api";

const ALL_JURISDICTIONS = ["US_HSR", "EU_EC", "UK_CMA", "IN_CCI", "CN_SAMR", "DE_BKA", "AU_ACCC"];

// Merge an M7 result into the active deal report's `regulatory` object so the
// board pitchbook (Reports tab) picks it up.
function saveRegulatory(key, value) {
  const report = getActiveReport();
  saveActiveReport({ ...report, regulatory: { ...(report.regulatory || {}), [key]: value } });
  // Also persist to the backend deal record when a real deal is active.
  const dealId = getActiveDealMeta()?.id;
  if (dealId) saveModuleOutput(dealId, `m7_${key}`, value).catch(() => {});
}

export default function ClosingPage() {
  const meta = getActiveDealMeta();
  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Module 7 · Closing Readiness</p>
          <h2>Closing</h2>
          <p className="muted">Regulatory Horizon, CFIUS screening, and the conditions-precedent checklist. Results feed the board pitchbook (Reports tab).</p>
        </div>
        <span className="workspace-code compact">{meta.transactionCode}</span>
      </section>

      <RegulatoryPanel />
      <CfiusPanel />
      <ChecklistPanel />

      <section className="table-panel">
        <div className="section-title"><p className="eyebrow">Sample Checklist</p><h3>Execution Items (demo)</h3></div>
        <table className="data-table">
          <thead><tr><th>Checklist Item</th><th>Owner</th><th>Due Date</th><th>Status</th><th>Blocker Note</th></tr></thead>
          <tbody>{DEMO_CLOSING_CHECKLIST.map((item) => <tr key={item.item}><td>{item.item}</td><td>{item.owner}</td><td>{item.dueDate}</td><td>{item.status}</td><td>{item.blocker}</td></tr>)}</tbody>
        </table>
      </section>
    </div>
  );
}

function RegulatoryPanel() {
  const [form, setForm] = useState({ deal_ev: 2000000000, combined_market_share: 0.35, product_overlaps: 4, sector: "telecom" });
  const [turnover, setTurnover] = useState({ US_HSR: 500000000, EU_EC: 1000000000 });
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const toggleJur = (code) => setTurnover((t) => {
    const next = { ...t };
    if (code in next) delete next[code]; else next[code] = 300000000;
    return next;
  });

  const run = async () => {
    setStatus("loading");
    setError("");
    try {
      const payload = {
        ...form,
        jurisdictions: Object.entries(turnover).map(([jurisdiction, combined_turnover_usd]) => ({ jurisdiction, combined_turnover_usd })),
      };
      const res = await runRegulatoryHorizon(payload);
      setResult(res.regulatory_horizon);
      saveRegulatory("regulatory_horizon", res.regulatory_horizon);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "Regulatory analysis failed.");
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title"><p className="eyebrow">E5 · Regulatory Horizon</p><h3>Multi-jurisdiction antitrust</h3></div>
      <div className="form-grid compact">
        <label>Deal EV ($)<input type="number" value={form.deal_ev} onChange={(e) => setForm((f) => ({ ...f, deal_ev: Number(e.target.value) }))} /></label>
        <label>Combined Market Share<input type="number" step="0.01" value={form.combined_market_share} onChange={(e) => setForm((f) => ({ ...f, combined_market_share: Number(e.target.value) }))} /></label>
        <label>Product Overlaps<input type="number" value={form.product_overlaps} onChange={(e) => setForm((f) => ({ ...f, product_overlaps: Number(e.target.value) }))} /></label>
        <label>Sector<input type="text" value={form.sector} onChange={(e) => setForm((f) => ({ ...f, sector: e.target.value }))} /></label>
      </div>
      <div className="segmented-control" style={{ marginTop: 8 }}>
        {ALL_JURISDICTIONS.map((code) => (
          <button key={code} className={code in turnover ? "active" : ""} onClick={() => toggleJur(code)}>{code}</button>
        ))}
      </div>
      <button onClick={run} disabled={status === "loading"} style={{ marginTop: 10 }}>{status === "loading" ? "Analyzing..." : "Run Regulatory Horizon"}</button>
      {status === "error" && <p className="muted" style={{ color: "#f2a3a3" }}>{error}</p>}

      {status === "ready" && result && (
        <>
          <section className="metric-grid" style={{ marginTop: 14 }}>
            <div className="metric-card"><span>Filings Required</span><strong>{result.filings_required}</strong></div>
            <div className="metric-card"><span>Phase II Probability</span><strong>{formatPercent(result.phase2_probability_model)}</strong></div>
            <div className="metric-card"><span>Critical Path</span><strong>{result.critical_path ? `${result.critical_path.jurisdiction} · ${result.critical_path.expected_review_weeks}w` : "—"}</strong></div>
            <div className="metric-card"><span>Est. Divestiture Cost</span><strong>{formatCurrency(result.total_estimated_divestiture_cost_usd)}</strong></div>
          </section>
          <table className="data-table">
            <thead><tr><th>Jurisdiction</th><th>Regulator</th><th>Filing?</th><th>Phase II</th><th>Review (wks)</th><th>Divestiture Cost</th></tr></thead>
            <tbody>
              {result.jurisdictions.map((j) => (
                <tr key={j.jurisdiction}>
                  <td>{j.jurisdiction}</td>
                  <td>{j.regulator}</td>
                  <td className={j.filing_required ? "irr-fail" : "irr-pass"}>{j.filing_required ? "Required" : "No"}</td>
                  <td>{formatPercent(j.phase2_probability)}</td>
                  <td>{j.expected_review_weeks}</td>
                  <td>{formatCurrency(j.divestiture_cost_estimate_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}

function CfiusPanel() {
  const [flags, setFlags] = useState({
    us_business: true, foreign_acquirer: true, acquirer_country_of_concern: false,
    critical_technology: false, critical_infrastructure: false, sensitive_personal_data: false, proximity_to_military: false,
  });
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");

  const run = async () => {
    setStatus("loading");
    try {
      const res = await runCfiusScreening(flags);
      setResult(res.cfius);
      saveRegulatory("cfius", res.cfius);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
    }
  };

  const tierClass = result?.blocking ? "severity-high" : result?.risk_tier === "Low" ? "severity-low" : "severity-medium";

  return (
    <section className="panel-flat">
      <div className="section-title"><p className="eyebrow">CFIUS Screening</p><h3>Foreign-investment national-security review</h3></div>
      <div className="form-grid compact">
        {Object.keys(flags).map((key) => (
          <label key={key} style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            <input type="checkbox" checked={flags[key]} onChange={(e) => setFlags((f) => ({ ...f, [key]: e.target.checked }))} />
            {key.replace(/_/g, " ")}
          </label>
        ))}
      </div>
      <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Screening..." : "Screen CFIUS"}</button>

      {status === "ready" && result && (
        <section className="metric-grid" style={{ marginTop: 14 }}>
          <div className={`metric-card ${tierClass}`} style={{ gridColumn: "span 2" }}><span>Risk Tier</span><strong style={{ fontSize: 15 }}>{result.risk_tier}</strong></div>
          <div className="metric-card"><span>Blocking</span><strong>{result.blocking ? "Yes" : "No"}</strong></div>
          <div className="metric-card"><span>Timeline</span><strong>{result.estimated_timeline_days} days</strong></div>
          {result.rationale?.length > 0 && (
            <div className="metric-card" style={{ gridColumn: "1 / -1" }}>
              <span>Rationale</span>
              <ul className="warning-list" style={{ color: "#a7b2b8" }}>{result.rationale.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}
        </section>
      )}
    </section>
  );
}

function ChecklistPanel() {
  const [form, setForm] = useState({ jurisdictions: "US_HSR, EU_EC", shareholder_approval_required: true, financing_required: true, change_of_control_consents: 2 });
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");

  const run = async () => {
    setStatus("loading");
    try {
      const payload = {
        required_jurisdictions: form.jurisdictions.split(",").map((s) => s.trim()).filter(Boolean),
        shareholder_approval_required: form.shareholder_approval_required,
        financing_required: form.financing_required,
        change_of_control_consents: form.change_of_control_consents,
      };
      const res = await buildClosingChecklist(payload);
      setResult(res.closing_checklist);
      saveRegulatory("closing_checklist", res.closing_checklist);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title"><p className="eyebrow">Conditions Precedent</p><h3>Auto-Generated Closing Checklist</h3></div>
      <div className="form-grid compact">
        <label>Required Jurisdictions<input type="text" value={form.jurisdictions} onChange={(e) => setForm((f) => ({ ...f, jurisdictions: e.target.value }))} /></label>
        <label>CoC Consents<input type="number" value={form.change_of_control_consents} onChange={(e) => setForm((f) => ({ ...f, change_of_control_consents: Number(e.target.value) }))} /></label>
        <label style={{ flexDirection: "row", alignItems: "center", gap: 8 }}><input type="checkbox" checked={form.shareholder_approval_required} onChange={(e) => setForm((f) => ({ ...f, shareholder_approval_required: e.target.checked }))} />Shareholder approval</label>
        <label style={{ flexDirection: "row", alignItems: "center", gap: 8 }}><input type="checkbox" checked={form.financing_required} onChange={(e) => setForm((f) => ({ ...f, financing_required: e.target.checked }))} />Financing required</label>
      </div>
      <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Building..." : "Generate Checklist"}</button>

      {status === "ready" && result && (
        <table className="data-table" style={{ marginTop: 14 }}>
          <thead><tr><th>Item</th><th>Category</th><th>Status</th></tr></thead>
          <tbody>{result.items.map((it, i) => <tr key={i}><td>{it.item}</td><td>{it.category}</td><td>{it.status}</td></tr>)}</tbody>
        </table>
      )}
    </section>
  );
}
