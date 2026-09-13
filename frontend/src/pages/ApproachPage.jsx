import React, { useState } from "react";
import { buildAdvisorGraph, normalizeFinancials, saveModuleOutput } from "../lib/api";
import { formatCurrency, formatPercent, getActiveDealMeta } from "../lib/dealUtils";

function persistToDeal(key, payload) {
  const dealId = getActiveDealMeta()?.id;
  if (dealId) saveModuleOutput(dealId, key, payload).catch(() => {});
}

const ROLES = ["management", "board", "advisor", "financing_bank", "counsel"];
const SIDES = ["buyer", "target", "neutral"];

export default function ApproachPage() {
  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Module 2 · The Approach</p>
          <h2>Approach</h2>
          <p className="muted">Three-year financial normalization and the advisor conflict graph.</p>
        </div>
      </section>
      <NormalizationPanel />
      <AdvisorGraphPanel />
    </div>
  );
}

function NormalizationPanel() {
  const [years, setYears] = useState([
    { year: 2023, revenue: 100000000, cogs: 40000000, sga: 20000000, rnd: 5000000, addback: 3000000 },
    { year: 2024, revenue: 120000000, cogs: 48000000, sga: 22000000, rnd: 6000000, addback: 0 },
    { year: 2025, revenue: 140000000, cogs: 54000000, sga: 24000000, rnd: 7000000, addback: 0 },
  ]);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const setCell = (i, key, value) => setYears((rows) => rows.map((r, idx) => (idx === i ? { ...r, [key]: value } : r)));

  const run = async () => {
    setStatus("loading");
    setError("");
    try {
      const payload = {
        years: years.map((r) => ({
          year: r.year, revenue: r.revenue, cogs: r.cogs, sga: r.sga, rnd: r.rnd,
          adjustments: r.addback ? [{ label: "Owner comp / non-recurring add-back", amount: r.addback }] : [],
        })),
        sector_ebitda_margin_95th: 0.35,
      };
      const res = await normalizeFinancials(payload);
      setResult(res.normalized);
      persistToDeal("m2_normalization", res.normalized);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "Normalization failed.");
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title"><p className="eyebrow">Financial Normalization</p><h3>Three-Year Standardized Financials</h3></div>
      <div className="sensitivity-scroll">
        <table className="data-table">
          <thead><tr><th>Year</th><th>Revenue</th><th>COGS</th><th>SG&A</th><th>R&D</th><th>EBITDA Add-back</th></tr></thead>
          <tbody>
            {years.map((r, i) => (
              <tr key={i}>
                {["year", "revenue", "cogs", "sga", "rnd", "addback"].map((key) => (
                  <td key={key}><input type="number" value={r[key]} onChange={(e) => setCell(i, key, Number(e.target.value))} style={{ width: 110 }} /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Normalizing..." : "Normalize"}</button>
      {status === "error" && <p className="muted" style={{ color: "#f2a3a3" }}>{error}</p>}

      {status === "ready" && result && (
        <>
          <table className="data-table" style={{ marginTop: 14 }}>
            <thead><tr><th>Period</th><th>Year</th><th>Revenue</th><th>Reported EBITDA</th><th>Add-backs</th><th>Normalized EBITDA</th><th>Norm. Margin</th></tr></thead>
            <tbody>
              {result.periods.map((p) => (
                <tr key={p.year}>
                  <td><strong>{p.period}</strong></td>
                  <td>{p.year}</td>
                  <td>{formatCurrency(p.net_revenue)}</td>
                  <td>{formatCurrency(p.reported_ebitda)}</td>
                  <td>{formatCurrency(p.adjustments_total)}</td>
                  <td><strong>{formatCurrency(p.normalized_ebitda)}</strong></td>
                  <td>{formatPercent(p.normalized_ebitda_margin)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {result.anomalies.length > 0 && (
            <ul className="warning-list">
              {result.anomalies.map((a, i) => <li key={i}>[{a.period}] {a.detail}</li>)}
            </ul>
          )}
          {result.requires_analyst_signoff && <p className="muted" style={{ color: "#f2b96b" }}>⚠ Anomalies detected — analyst sign-off required before advancing.</p>}
        </>
      )}
    </section>
  );
}

function AdvisorGraphPanel() {
  const [participants, setParticipants] = useState([
    { name: "Buyer Corp Dev", role: "management", side: "buyer", affiliation: "Goldman Sachs" },
    { name: "Target CFO", role: "management", side: "target", affiliation: "Goldman Sachs" },
    { name: "Buyer Counsel", role: "counsel", side: "buyer", affiliation: "Kirkland & Ellis" },
    { name: "Target CEO", role: "board", side: "target", affiliation: "Stanford GSB" },
    { name: "Buyer VP", role: "management", side: "buyer", affiliation: "Stanford GSB" },
  ]);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const setCell = (i, key, value) => setParticipants((rows) => rows.map((r, idx) => (idx === i ? { ...r, [key]: value } : r)));

  const run = async () => {
    setStatus("loading");
    setError("");
    try {
      const payload = {
        participants: participants.map((p) => ({
          name: p.name, role: p.role, side: p.side,
          affiliations: p.affiliation ? [p.affiliation] : [],
        })),
      };
      const res = await buildAdvisorGraph(payload);
      setResult(res.advisor_graph);
      persistToDeal("m2_advisor_graph", res.advisor_graph);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "Advisor graph failed.");
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title"><p className="eyebrow">Advisor Conflict Graph</p><h3>Relationship &amp; Conflict Map</h3></div>
      <div className="sensitivity-scroll">
        <table className="data-table">
          <thead><tr><th>Name</th><th>Role</th><th>Side</th><th>Affiliation</th></tr></thead>
          <tbody>
            {participants.map((p, i) => (
              <tr key={i}>
                <td><input type="text" value={p.name} onChange={(e) => setCell(i, "name", e.target.value)} /></td>
                <td><select value={p.role} onChange={(e) => setCell(i, "role", e.target.value)}>{ROLES.map((r) => <option key={r} value={r}>{r}</option>)}</select></td>
                <td><select value={p.side} onChange={(e) => setCell(i, "side", e.target.value)}>{SIDES.map((s) => <option key={s} value={s}>{s}</option>)}</select></td>
                <td><input type="text" value={p.affiliation} onChange={(e) => setCell(i, "affiliation", e.target.value)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Building..." : "Build Graph"}</button>
      {status === "error" && <p className="muted" style={{ color: "#f2a3a3" }}>{error}</p>}

      {status === "ready" && result && (
        <>
          <section className="metric-grid" style={{ marginTop: 14 }}>
            <div className="metric-card severity-high"><span>Conflicts</span><strong>{result.summary.conflicts}</strong></div>
            <div className="metric-card severity-low"><span>Leverage Opportunities</span><strong>{result.summary.leverage_opportunities}</strong></div>
            <div className="metric-card"><span>Participants</span><strong>{result.summary.participants}</strong></div>
            <div className="metric-card"><span>Affiliations</span><strong>{result.summary.affiliations}</strong></div>
          </section>
          {result.conflict_flags.length > 0 && (
            <>
              <h4 style={{ margin: "12px 0 4px" }}>Conflict flags</h4>
              <ul className="warning-list">{result.conflict_flags.map((c, i) => <li key={i}>{c.description}</li>)}</ul>
            </>
          )}
          {result.leverage_opportunities.length > 0 && (
            <>
              <h4 style={{ margin: "12px 0 4px" }}>Leverage opportunities</h4>
              <ul className="warning-list" style={{ color: "#7ee6c6" }}>{result.leverage_opportunities.map((c, i) => <li key={i}>{c.description}</li>)}</ul>
            </>
          )}
        </>
      )}
    </section>
  );
}
