import React, { useState } from "react";
import { DEMO_INTEGRATION_TASKS, getActiveDealMeta, getActiveReport } from "../lib/dealUtils";
import { addSynergyRealization, getPmiDnaScore, getSynergyRealization } from "../lib/api";

const workstreams = ["IT", "Finance", "HR", "Sales", "Operations", "Culture"];

const PMI_FIELDS = [
  { key: "culture_compatibility", label: "Culture Compatibility" },
  { key: "org_structure_compatibility", label: "Org Structure" },
  { key: "leadership_profile_match", label: "Leadership Match" },
  { key: "compensation_overlap", label: "Compensation Overlap" },
  { key: "technology_stack_compatibility", label: "Technology Stack" },
];

const SYNERGY_CATEGORIES = ["Headcount", "Facilities", "Procurement", "Cross-Sell", "IT Rationalization", "Pricing Uplift"];

export default function IntegrationPage() {
  const report = getActiveReport();
  const synergy = report.synergies?.financial_synergies?.total_annual_synergy || 0;

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">100-Day Plan · Module 8</p>
          <h2>Integration</h2>
          <p className="muted">PMI DNA Score, synergy realization tracking, and the 100-Day PMI plan.</p>
        </div>
        <button>Export PMI Plan</button>
      </section>

      <section className="metric-grid">
        <div className="metric-card"><span>Annual Synergy Target</span><strong>${Number(synergy).toLocaleString()}</strong></div>
        <div className="metric-card"><span>Workstreams</span><strong>{workstreams.length}</strong></div>
        <div className="metric-card"><span>Day 1 Readiness</span><strong>82%</strong></div>
        <div className="metric-card"><span>Synergy Realization</span><strong>34%</strong></div>
      </section>

      <PmiDnaPanel />
      <SynergyTrackerPanel />

      <section className="table-panel">
        <div className="section-title"><p className="eyebrow">PMI Tracker</p><h3>100-Day PMI Plan: Day 1 to Day 100 Milestones</h3></div>
        <table className="data-table">
          <thead><tr><th>Milestone</th><th>Workstream</th><th>Task</th><th>Owner</th><th>Status</th></tr></thead>
          <tbody>{DEMO_INTEGRATION_TASKS.map((task) => <tr key={`${task.milestone}-${task.task}`}><td>{task.milestone}</td><td>{task.workstream}</td><td>{task.task}</td><td>{task.owner}</td><td>{task.status}</td></tr>)}</tbody>
        </table>
      </section>
    </div>
  );
}

function PmiDnaPanel() {
  const [values, setValues] = useState({
    culture_compatibility: 60,
    org_structure_compatibility: 70,
    leadership_profile_match: 65,
    compensation_overlap: 50,
    technology_stack_compatibility: 45,
  });
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const run = async () => {
    setStatus("loading");
    setError("");
    try {
      const res = await getPmiDnaScore(values);
      setResult(res.pmi_dna_score);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "PMI DNA scoring failed.");
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title"><p className="eyebrow">E6 · PMI DNA Score</p><h3>Pre-close integration friction</h3></div>
      <div className="form-grid compact">
        {PMI_FIELDS.map((field) => (
          <label key={field.key} className="slider-field">
            {field.label} <span className="slider-value">{values[field.key]}</span>
            <input
              type="range" min="0" max="100" step="1" value={values[field.key]}
              onChange={(e) => setValues((v) => ({ ...v, [field.key]: Number(e.target.value) }))}
            />
          </label>
        ))}
      </div>
      <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Scoring..." : "Compute PMI DNA Score"}</button>

      {status === "error" && <p className="muted" style={{ color: "#f2a3a3" }}>{error}</p>}

      {status === "ready" && result && (
        <>
          <section className="metric-grid" style={{ marginTop: 16 }}>
            <div className="metric-card"><span>Composite Score</span><strong>{result.composite_score}</strong></div>
            <div className="metric-card" style={{ gridColumn: "span 2" }}><span>Assessment</span><strong style={{ fontSize: 14 }}>{result.risk_narrative}</strong></div>
          </section>
          <div className="friction-heatmap">
            {result.friction_heatmap.map((cell) => (
              <div key={cell.workstream} className={`friction-cell friction-${cell.friction_level}`}>
                <span className="friction-workstream">{cell.workstream}</span>
                <span className="friction-value">{cell.friction_score}</span>
                <span className="friction-workstream">{cell.friction_level} friction</span>
              </div>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function SynergyTrackerPanel() {
  const meta = getActiveDealMeta();
  const [dealId, setDealId] = useState(meta?.id || "");
  const [entry, setEntry] = useState({ category: "Headcount", period_month: 1, predicted_amount: 100, realized_amount: 80 });
  const [dashboard, setDashboard] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const refresh = async (id) => {
    const res = await getSynergyRealization(id);
    setDashboard(res.dashboard);
  };

  const addEntry = async () => {
    if (!dealId) { setError("Enter a deal id (create a deal in Deal Pipeline first)."); setStatus("error"); return; }
    setStatus("loading");
    setError("");
    try {
      await addSynergyRealization(dealId, entry);
      await refresh(dealId);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "Could not record synergy actuals.");
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title"><p className="eyebrow">M8 · Synergy Realization Tracker</p><h3>Predicted vs. realised, by category</h3></div>
      <div className="form-grid compact">
        <label>Deal ID<input type="text" value={dealId} onChange={(e) => setDealId(e.target.value)} placeholder="deal uuid" /></label>
        <label>Category
          <select value={entry.category} onChange={(e) => setEntry((s) => ({ ...s, category: e.target.value }))}>
            {SYNERGY_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
        <label>Month<input type="number" min="1" value={entry.period_month} onChange={(e) => setEntry((s) => ({ ...s, period_month: Number(e.target.value) }))} /></label>
        <label>Predicted ($)<input type="number" value={entry.predicted_amount} onChange={(e) => setEntry((s) => ({ ...s, predicted_amount: Number(e.target.value) }))} /></label>
        <label>Realised ($)<input type="number" value={entry.realized_amount} onChange={(e) => setEntry((s) => ({ ...s, realized_amount: Number(e.target.value) }))} /></label>
      </div>
      <button onClick={addEntry} disabled={status === "loading"}>{status === "loading" ? "Saving..." : "Record Actuals"}</button>

      {status === "error" && <p className="muted" style={{ color: "#f2a3a3" }}>{error}</p>}

      {dashboard && dashboard.categories.length > 0 && (
        <>
          <section className="metric-grid" style={{ marginTop: 16 }}>
            <div className="metric-card"><span>Cumulative Predicted</span><strong>${dashboard.totals.cumulative_predicted.toLocaleString()}</strong></div>
            <div className="metric-card"><span>Cumulative Realised</span><strong>${dashboard.totals.cumulative_realized.toLocaleString()}</strong></div>
            <div className="metric-card"><span>Realization Rate</span><strong>{dashboard.totals.realization_rate != null ? `${(dashboard.totals.realization_rate * 100).toFixed(0)}%` : "n/a"}</strong></div>
          </section>
          <table className="data-table">
            <thead><tr><th>Category</th><th>Months</th><th>Predicted</th><th>Realised</th><th>Variance</th><th>Run-rate</th><th>Root Cause?</th></tr></thead>
            <tbody>
              {dashboard.categories.map((c) => (
                <tr key={c.category}>
                  <td>{c.category}</td>
                  <td>{c.months_tracked}</td>
                  <td>${c.cumulative_predicted.toLocaleString()}</td>
                  <td>${c.cumulative_realized.toLocaleString()}</td>
                  <td className={c.variance_abs < 0 ? "irr-fail" : "irr-pass"}>{c.variance_pct != null ? `${(c.variance_pct * 100).toFixed(0)}%` : "—"}</td>
                  <td>${c.run_rate_annualized.toLocaleString()}</td>
                  <td>{c.root_cause_review_required ? <span className="temporal-tier at-signing">Review</span> : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
