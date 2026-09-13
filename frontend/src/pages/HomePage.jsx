import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getHealth, getLlmHealth, listDeals } from "../lib/api";
import {
  DEMO_DEAL,
  displayDealName,
  formatCurrency,
  getActiveDealMeta,
  getActiveReport,
  getMetrics,
  loadDemoWorkspace,
  nextRecommendedAction,
  stageLabel,
  statusLabel,
} from "../lib/dealUtils";

export default function HomePage() {
  const [health, setHealth] = useState(null);
  const [engine, setEngine] = useState(null);
  const [deals, setDeals] = useState([]);
  const [meta, setMeta] = useState(getActiveDealMeta());
  const [report, setReport] = useState(getActiveReport());
  const [error, setError] = useState("");

  const refresh = async () => {
    setError("");
    // Independent calls: a single failure (e.g. a free-tier cold-start timeout)
    // must not blank the whole dashboard. Each tile updates on its own success.
    const [core, llm, rows] = await Promise.allSettled([
      getHealth(),
      getLlmHealth(),
      listDeals(100),
    ]);
    if (core.status === "fulfilled") setHealth(core.value);
    if (llm.status === "fulfilled") setEngine(llm.value);
    if (rows.status === "fulfilled") setDeals(Array.isArray(rows.value) ? rows.value : []);
    setMeta(getActiveDealMeta());
    setReport(getActiveReport());

    const failed = [core, llm, rows].find((r) => r.status === "rejected");
    if (failed) {
      const e = failed.reason;
      setError(e?.response?.data?.detail || e?.message || "Some dashboard data is unavailable.");
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const activeMandates = useMemo(
    () => deals.filter((deal) => deal.status === "in_progress").length,
    [deals]
  );
  const metrics = getMetrics(report);

  // Friendly name for the AI provider tile. Null engine = not loaded yet ("…"),
  // never the misleading "Local" default while a request is still in flight.
  const engineLabel = useMemo(() => {
    if (!engine?.provider) return "…";
    const names = { groq: "Groq", anthropic: "Anthropic", local: "Local" };
    const p = engine.provider;
    return names[p] || p.charAt(0).toUpperCase() + p.slice(1);
  }, [engine]);

  const onLoadDemo = () => {
    loadDemoWorkspace();
    setMeta(DEMO_DEAL);
    setReport(getActiveReport());
  };

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Portfolio Overview</p>
          <h2>Dashboard</h2>
        </div>
        <button onClick={onLoadDemo}>Load Aster Northstar Sample Deal</button>
      </section>

      <section className="metric-grid">
        <div className="metric-card">
          <span>Total Transactions</span>
          <strong>{deals.length}</strong>
        </div>
        <div className="metric-card">
          <span>Active Mandates</span>
          <strong>{activeMandates}</strong>
        </div>
        <div className="metric-card">
          <span>Platform Status</span>
          <strong>{health?.status || "Checking"}</strong>
        </div>
        <div className="metric-card">
          <span>Decision Engine</span>
          <strong>{engineLabel}</strong>
        </div>
      </section>

      <section className="workspace-summary">
        <div className="summary-main">
          <div className="section-title">
            <p className="eyebrow">Active Transaction</p>
            <h3>{displayDealName(meta.dealName)}</h3>
          </div>
          <div className="detail-grid">
            <div>
              <span>Buyer</span>
              <strong>{meta.buyerName}</strong>
            </div>
            <div>
              <span>Target</span>
              <strong>{meta.targetName}</strong>
            </div>
            <div>
              <span>Indicative Value</span>
              <strong>{formatCurrency(meta.dealValue || metrics.enterpriseValue)}</strong>
            </div>
            <div>
              <span>Current Stage</span>
              <strong>{stageLabel(meta.stage)}</strong>
            </div>
          </div>
          <div className="recommendation">
            <span>Next recommended action</span>
            <strong>{nextRecommendedAction(report)}</strong>
          </div>
        </div>
        <aside className="summary-side">
          <span className={`status-badge status-${meta.status}`}>{statusLabel(meta.status)}</span>
          <Link to="/workspace" className="link-button">
            Open Deal Workspace
          </Link>
        </aside>
      </section>

      <section className="two-column">
        <div className="panel-flat">
          <div className="section-title">
            <p className="eyebrow">Valuation Snapshot</p>
            <h3>Key Economics</h3>
          </div>
          <div className="mini-metrics">
            <div>
              <span>Enterprise Value</span>
              <strong>{formatCurrency(metrics.enterpriseValue)}</strong>
            </div>
            <div>
              <span>Synergy Value</span>
              <strong>{formatCurrency(metrics.synergyValue)}</strong>
            </div>
            <div>
              <span>Opening Bid</span>
              <strong>{formatCurrency(metrics.openingBid)}</strong>
            </div>
          </div>
        </div>
        <div className="panel-flat">
          <div className="section-title">
            <p className="eyebrow">Workflow Health</p>
            <h3>Mandate Readiness</h3>
          </div>
          <div className="progress-list">
            <div><span>Financials</span><progress value="85" max="100" /></div>
            <div><span>Diligence</span><progress value="65" max="100" /></div>
            <div><span>Negotiation</span><progress value="55" max="100" /></div>
          </div>
        </div>
      </section>

      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

