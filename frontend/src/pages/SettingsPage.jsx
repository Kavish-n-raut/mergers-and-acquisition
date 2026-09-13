import React, { useEffect, useState } from "react";
import { getActiveDealMeta, getActiveReport, loadDemoWorkspace } from "../lib/dealUtils";
import { getLlmHealth } from "../lib/api";

const PROVIDER_LABELS = {
  groq: "Groq (free)",
  anthropic: "Anthropic (premium)",
  local: "Local / Free",
};

export default function SettingsPage() {
  const meta = getActiveDealMeta();
  const report = getActiveReport();
  const [aiProvider, setAiProvider] = useState("…");

  useEffect(() => {
    let cancelled = false;
    getLlmHealth()
      .then((h) => {
        if (cancelled) return;
        const p = h?.provider;
        setAiProvider(p ? PROVIDER_LABELS[p] || p.charAt(0).toUpperCase() + p.slice(1) : "Local / Free");
      })
      .catch(() => { if (!cancelled) setAiProvider("Local / Free"); });
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="page">
      <section className="page-header">
        <div><p className="eyebrow">Administration</p><h2>Settings / Admin</h2></div>
      </section>

      <section className="two-column">
        <div className="panel-flat">
          <div className="section-title"><p className="eyebrow">Environment</p><h3>Workspace Mode</h3></div>
          <div className="detail-grid">
            <div><span>AI Provider</span><strong>{aiProvider}</strong></div>
            <div><span>Premium Provider</span><strong>Anthropic Optional</strong></div>
            <div><span>Maps Provider</span><strong>{(import.meta.env.VITE_GOOGLE_MAPS_API_KEY || "").trim() ? "OpenStreetMap default / Google optional" : "OpenStreetMap default"}</strong></div>
            <div><span>Active Deal</span><strong>{meta.dealName}</strong></div>
            <div><span>Transaction Code</span><strong>{meta.transactionCode}</strong></div>
          </div>
        </div>
        <div className="panel-flat">
          <div className="section-title"><p className="eyebrow">Demo Data</p><h3>Sample Deal</h3></div>
          <p className="muted">Reload Aster Capital Technologies acquiring Northstar Process Automation.</p>
          <button onClick={loadDemoWorkspace}>Reload Sample Deal</button>
        </div>
        <div className="panel-flat span-2">
          <div className="section-title"><p className="eyebrow">Location Intelligence</p><h3>Google Maps Setup</h3></div>
          <p className="muted">The MVP works without paid keys by using MapLibre GL JS with OpenStreetMap-compatible tiles. To enable optional Google Maps rendering later:</p>
          <ol className="clean-list">
            <li>Create or open <code>frontend/.env</code>.</li>
            <li>Add your key as <code>VITE_GOOGLE_MAPS_API_KEY=your_key_here</code>.</li>
            <li>Enable <strong>Maps JavaScript API</strong> and <strong>Geocoding API</strong> in Google Cloud.</li>
            <li>Restrict the key to local development origins such as <code>http://127.0.0.1:5173/*</code> and <code>http://localhost:5173/*</code>.</li>
            <li>Restart the Vite dev server after changing environment variables.</li>
          </ol>
          <p className="callout-text">Do not hardcode API keys in source code. Keep this blank for free/local mode.</p>
        </div>
      </section>

      <details className="advanced-json">
        <summary>Developer diagnostics</summary>
        <pre className="document-preview">{JSON.stringify({ activeDeal: meta, report }, null, 2)}</pre>
      </details>
    </div>
  );
}
