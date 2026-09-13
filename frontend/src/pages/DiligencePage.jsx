import React, { useMemo, useState } from "react";
import { getActiveReport, riskItems } from "../lib/dealUtils";
import { RiskCard } from "./DealWorkspacePage";
import { mapTemporalRisks } from "../lib/api";

const categories = ["All", "Legal", "Financial", "Tax", "HR", "IP", "Regulatory", "Cyber", "Customer"];

const TIER_CLASS = {
  "At Signing": "at-signing",
  "At Close": "at-close",
  "Post-Close (Year 1)": "post-close",
  "Post-Close (Year 2+)": "post-close",
  Indeterminate: "indeterminate",
};

export default function DiligencePage() {
  const risks = riskItems(getActiveReport());
  const [category, setCategory] = useState("All");
  const [temporal, setTemporal] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const filtered = category === "All" ? risks : risks.filter((risk) => risk.category === category);

  const counts = useMemo(() => ({
    High: risks.filter((risk) => risk.severity === "High").length,
    Medium: risks.filter((risk) => risk.severity === "Medium").length,
    Low: risks.filter((risk) => risk.severity === "Low").length,
  }), [risks]);

  const runTemporal = async () => {
    setStatus("loading");
    setError("");
    try {
      const payload = risks.map((r) => ({
        risk_category: r.risk_category || r.category || "General Risk",
        severity: r.severity || "Medium",
        quoted_text: (r.quoted_text || r.ai_explanation || "No clause text available for this finding.").slice(0, 4000),
        ai_explanation: (r.ai_explanation || r.recommended_action || "No explanation available.").slice(0, 1180),
      }));
      const res = await mapTemporalRisks(payload);
      setTemporal(res.temporal_risk_map);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "Temporal risk mapping failed.");
    }
  };

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Diligence Status</p>
          <h2>Due Diligence</h2>
          <p className="muted">Sample local risk findings with evidence, owner, status, and Recommended Mitigation guidance.</p>
        </div>
        <span className="source-chip">Sample diligence data</span>
        <button onClick={runTemporal} disabled={status === "loading"}>
          {status === "loading" ? "Mapping..." : "Run Temporal Risk Map"}
        </button>
      </section>

      <section className="metric-grid">
        <div className="metric-card severity-high"><span>High Risk</span><strong>{counts.High}</strong></div>
        <div className="metric-card severity-medium"><span>Medium Risk</span><strong>{counts.Medium}</strong></div>
        <div className="metric-card severity-low"><span>Low Risk</span><strong>{counts.Low}</strong></div>
      </section>

      {status === "error" && (
        <section className="panel-flat warning"><strong>Temporal mapping error</strong><p className="muted">{error}</p></section>
      )}

      {status === "ready" && temporal && (
        <section className="table-panel">
          <div className="section-title">
            <p className="eyebrow">E4 · Temporal Risk Mapper</p>
            <h3>Findings ranked by time-adjusted severity</h3>
          </div>
          <p className="muted">Urgency multiplier weights each finding by when it crystallises (At Signing 0.5 → Indeterminate 0.0), reordering the negotiation priority.</p>
          <table className="data-table">
            <thead>
              <tr><th>#</th><th>Risk</th><th>Severity</th><th>Temporal Tier</th><th>Base</th><th>Adjusted</th></tr>
            </thead>
            <tbody>
              {temporal.findings.map((f) => (
                <tr key={f.priority_rank}>
                  <td>{f.priority_rank}</td>
                  <td>{f.risk_category}</td>
                  <td>{f.severity}</td>
                  <td><span className={`temporal-tier ${TIER_CLASS[f.temporal_tier] || "indeterminate"}`}>{f.temporal_tier}</span></td>
                  <td>{f.base_severity_score.toFixed(1)}</td>
                  <td><strong>{f.adjusted_score.toFixed(2)}</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="segmented-control">
        {categories.map((item) => (
          <button key={item} className={category === item ? "active" : ""} onClick={() => setCategory(item)}>
            {item}
          </button>
        ))}
      </section>

      <section className="risk-grid">
        {filtered.map((risk) => <RiskCard key={`${risk.risk_category}-${risk.sourceDocument}`} risk={risk} />)}
      </section>
    </div>
  );
}
