import React, { useState } from "react";
import { saveModuleOutput, screenTargets } from "../lib/api";
import { formatCurrency, formatPercent, getActiveDealMeta } from "../lib/dealUtils";

const DEFAULTS = {
  sector: "Software",
  geography: "United States",
  min_revenue: 20000000,
  max_revenue: 100000000,
  target_revenue_cagr: 0.1,
  sector_growth_rate: 0.06,
  shortlist_size: 8,
  longlist_size: 20,
};

export default function ScreeningPage() {
  const [form, setForm] = useState(DEFAULTS);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const run = async () => {
    setStatus("loading");
    setError("");
    try {
      const res = await screenTargets(form);
      setResult(res.data);
      const dealId = getActiveDealMeta()?.id;
      if (dealId) saveModuleOutput(dealId, "m1_screening", res.data).catch(() => {});
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "Screening failed.");
    }
  };

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Module 1 · The Hunt</p>
          <h2>Target Screening</h2>
          <p className="muted">Composite 0–100 scoring (Financial Fit, Growth, Sector Tailwind, Deal Genome Match, Competing-Bid) with Sentiment Radar over a candidate universe.</p>
        </div>
        <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Screening..." : "Run Screen"}</button>
      </section>

      <section className="panel-flat">
        <div className="section-title"><p className="eyebrow">Filters</p><h3>Screening Criteria</h3></div>
        <div className="form-grid compact">
          <label>Sector<input type="text" value={form.sector} onChange={(e) => setField("sector", e.target.value)} /></label>
          <label>Geography<input type="text" value={form.geography} onChange={(e) => setField("geography", e.target.value)} /></label>
          <label>Min Revenue ($)<input type="number" value={form.min_revenue} onChange={(e) => setField("min_revenue", Number(e.target.value))} /></label>
          <label>Max Revenue ($)<input type="number" value={form.max_revenue} onChange={(e) => setField("max_revenue", Number(e.target.value))} /></label>
          <label>Sector Median CAGR<input type="number" step="0.01" value={form.target_revenue_cagr} onChange={(e) => setField("target_revenue_cagr", Number(e.target.value))} /></label>
          <label>Sector Growth<input type="number" step="0.01" value={form.sector_growth_rate} onChange={(e) => setField("sector_growth_rate", Number(e.target.value))} /></label>
          <label>Short List Size<input type="number" value={form.shortlist_size} onChange={(e) => setField("shortlist_size", Number(e.target.value))} /></label>
          <label>Universe Size<input type="number" value={form.longlist_size} onChange={(e) => setField("longlist_size", Number(e.target.value))} /></label>
        </div>
      </section>

      {status === "error" && <section className="panel-flat warning"><strong>Screening error</strong><p className="muted">{error}</p></section>}

      {status === "ready" && result && (
        <>
          <section className="metric-grid">
            <div className="metric-card"><span>Universe</span><strong>{result.long_list.length} ({result.universe_source})</strong></div>
            <div className="metric-card"><span>Short List</span><strong>{result.short_list.length}</strong></div>
            <div className="metric-card"><span>Top Score</span><strong>{result.short_list[0]?.composite_score ?? "—"}</strong></div>
            <div className="metric-card"><span>Avg Competing-Bid Risk</span><strong>{formatPercent(result.competing_bid_risk_score)}</strong></div>
          </section>
          <p className="muted">{result.sentiment_summary}</p>

          <section className="table-panel">
            <div className="section-title"><p className="eyebrow">Short List</p><h3>Ranked Targets</h3></div>
            <table className="data-table">
              <thead>
                <tr><th>#</th><th>Company</th><th>Revenue</th><th>CAGR</th><th>Score</th><th>Fin Fit</th><th>Growth</th><th>Genome</th><th>Momentum</th><th>Distress</th><th>Bid Risk</th></tr>
              </thead>
              <tbody>
                {result.short_list.map((c) => (
                  <tr key={c.name}>
                    <td>{c.rank}</td>
                    <td>{c.name}</td>
                    <td>{formatCurrency(c.revenue)}</td>
                    <td>{formatPercent(c.revenue_cagr)}</td>
                    <td><strong>{c.composite_score}</strong></td>
                    <td>{c.score_components.financial_fit}</td>
                    <td>{c.score_components.growth_trajectory}</td>
                    <td>{c.score_components.deal_genome_match}</td>
                    <td>{c.momentum_score}</td>
                    <td>{c.distress_score}</td>
                    <td>{formatPercent(c.competing_bid_probability)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}
