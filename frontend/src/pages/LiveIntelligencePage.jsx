import React, { useEffect, useState } from "react";
import {
  getFinnhubFinancials,
  getFinnhubQuote,
  getFinnhubStatus,
  getNewsSentiment,
  getPatentsStatus,
  getPatentVelocity,
} from "../lib/api";
import { formatPercent } from "../lib/dealUtils";

export default function LiveIntelligencePage() {
  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Free Data · Live Intelligence</p>
          <h2>Live Intelligence</h2>
          <p className="muted">Real market data (Finnhub), news sentiment (GDELT + FinBERT), and patent-velocity signals (USPTO) — free sources.</p>
        </div>
      </section>
      <FinnhubPanel />
      <NewsSentimentPanel />
      <PatentsPanel />
    </div>
  );
}

function StatusChip({ configured, name, howto }) {
  return (
    <span className={`source-chip source-mode-${configured ? "live" : "sample"}`}>
      {name}: {configured ? "connected" : `no key — ${howto}`}
    </span>
  );
}

function FinnhubPanel() {
  const [symbol, setSymbol] = useState("AAPL");
  const [quote, setQuote] = useState(null);
  const [fin, setFin] = useState(null);
  const [configured, setConfigured] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  useEffect(() => { getFinnhubStatus().then((d) => setConfigured(d.configured)).catch(() => setConfigured(false)); }, []);

  const run = async () => {
    setStatus("loading"); setError("");
    try {
      const [q, f] = await Promise.all([getFinnhubQuote(symbol), getFinnhubFinancials(symbol)]);
      setQuote(q.quote); setFin(f.financials); setStatus("ready");
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Finnhub request failed.");
      setStatus("error");
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title chart-title-row">
        <div><p className="eyebrow">Finnhub · Free key (60/min)</p><h3>Market Quote &amp; Multiples</h3></div>
        {configured !== null && <StatusChip configured={configured} name="Finnhub" howto="set FINNHUB_API_KEY" />}
      </div>
      <div className="form-grid compact">
        <label>Ticker<input type="text" value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} /></label>
      </div>
      <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Fetching…" : "Get Quote"}</button>
      {status === "error" && <p className="muted" style={{ color: "#f2a3a3" }}>{error}</p>}
      {status === "ready" && quote && (
        <section className="metric-grid" style={{ marginTop: 14 }}>
          <div className="metric-card"><span>Price</span><strong>${quote.current_price}</strong></div>
          <div className={`metric-card ${quote.percent_change >= 0 ? "severity-low" : "severity-high"}`}><span>Change</span><strong>{quote.percent_change}%</strong></div>
          <div className="metric-card"><span>Day Range</span><strong>${quote.low}–${quote.high}</strong></div>
          <div className="metric-card"><span>P/E (TTM)</span><strong>{fin?.highlights?.pe_ttm ?? "—"}</strong></div>
          <div className="metric-card"><span>EV/Revenue</span><strong>{fin?.highlights?.ev_revenue ?? "—"}</strong></div>
          <div className="metric-card"><span>Market Cap</span><strong>{fin?.highlights?.market_cap ? `$${Number(fin.highlights.market_cap).toLocaleString()}M` : "—"}</strong></div>
        </section>
      )}
    </section>
  );
}

function NewsSentimentPanel() {
  const [company, setCompany] = useState("Microsoft");
  const [result, setResult] = useState(null);
  const [source, setSource] = useState("gdelt");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const run = async () => {
    setStatus("loading"); setError("");
    try {
      const payload = source === "gdelt" ? { source: "gdelt", company } : { source: "finnhub", symbol: company };
      const res = await getNewsSentiment(payload);
      setResult(res.sentiment); setStatus("ready");
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "News sentiment failed.");
      setStatus("error");
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title"><p className="eyebrow">GDELT + FinBERT · Free, no key</p><h3>News Sentiment (Sentiment Radar)</h3></div>
      <p className="muted">Pulls recent news (GDELT), scores each headline with FinBERT, and rolls it up into distress / momentum signals.</p>
      <div className="form-grid compact">
        <label>{source === "gdelt" ? "Company" : "Ticker"}<input type="text" value={company} onChange={(e) => setCompany(e.target.value)} /></label>
        <label>Source
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="gdelt">GDELT (free, no key)</option>
            <option value="finnhub">Finnhub (needs key)</option>
          </select>
        </label>
      </div>
      <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Analyzing…" : "Analyze Sentiment"}</button>
      {status === "error" && <p className="muted" style={{ color: "#f2a3a3" }}>{error}</p>}
      {status === "ready" && result && (
        <section className="metric-grid" style={{ marginTop: 14 }}>
          <div className="metric-card severity-low"><span>Momentum</span><strong>{result.momentum_score}/10</strong></div>
          <div className="metric-card severity-high"><span>Distress</span><strong>{result.distress_score}/10</strong></div>
          <div className="metric-card"><span>Headlines Analyzed</span><strong>{result.analyzed}</strong></div>
          <div className="metric-card"><span>Pos / Neg / Neu</span><strong>{result.label_counts?.positive || 0} / {result.label_counts?.negative || 0} / {result.label_counts?.neutral || 0}</strong></div>
        </section>
      )}
    </section>
  );
}

function PatentsPanel() {
  const [company, setCompany] = useState("Microsoft");
  const [result, setResult] = useState(null);
  const [configured, setConfigured] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  useEffect(() => { getPatentsStatus().then((d) => setConfigured(d.configured)).catch(() => setConfigured(false)); }, []);

  const run = async () => {
    setStatus("loading"); setError("");
    try {
      const res = await getPatentVelocity(company);
      setResult(res.patents); setStatus("ready");
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Patent lookup failed.");
      setStatus("error");
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title chart-title-row">
        <div><p className="eyebrow">USPTO PatentsView · Free key</p><h3>Patent Velocity (R&amp;D Momentum)</h3></div>
        {configured !== null && <StatusChip configured={configured} name="USPTO" howto="set PATENTSVIEW_API_KEY" />}
      </div>
      <div className="form-grid compact">
        <label>Company<input type="text" value={company} onChange={(e) => setCompany(e.target.value)} /></label>
      </div>
      <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Looking up…" : "Get Patent Velocity"}</button>
      {status === "error" && <p className="muted" style={{ color: "#f2a3a3" }}>{error}</p>}
      {status === "ready" && result && (
        <>
          <section className="metric-grid" style={{ marginTop: 14 }}>
            <div className="metric-card"><span>Total Patents</span><strong>{result.total_patents}</strong></div>
            <div className="metric-card" style={{ gridColumn: "span 2" }}><span>Signal</span><strong style={{ fontSize: 14 }}>{result.signal}</strong></div>
          </section>
          <div className="source-list">
            {Object.entries(result.filings_by_year || {}).map(([y, c]) => <span className="source-chip" key={y}>{y}: {c}</span>)}
          </div>
        </>
      )}
    </section>
  );
}
