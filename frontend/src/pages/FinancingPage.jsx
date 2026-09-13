import React, { useState } from "react";
import { runLboAnalysis, saveModuleOutput } from "../lib/api";
import { formatCurrency, formatPercent, getActiveDealMeta, getActiveReport, saveActiveReport } from "../lib/dealUtils";

const DEFAULTS = {
  enterprise_value: 500,
  ebitda: 100,
  senior_leverage_x: 3.0,
  mezzanine_leverage_x: 1.0,
  senior_rate: 0.08,
  mezzanine_rate: 0.12,
  ebitda_growth_rate: 0.05,
  projection_years: 5,
  exit_multiple: 6.0,
  tax_rate: 0.21,
  board_hurdle_irr: 0.15,
  min_dscr_covenant: 1.2,
};

const FIELDS = [
  { key: "enterprise_value", label: "Enterprise Value ($M)", step: 1 },
  { key: "ebitda", label: "LTM EBITDA ($M)", step: 1 },
  { key: "senior_leverage_x", label: "Senior Leverage (x)", step: 0.1 },
  { key: "mezzanine_leverage_x", label: "Mezzanine Leverage (x)", step: 0.1 },
  { key: "senior_rate", label: "Senior Rate", step: 0.005 },
  { key: "mezzanine_rate", label: "Mezzanine Rate", step: 0.005 },
  { key: "ebitda_growth_rate", label: "EBITDA Growth", step: 0.01 },
  { key: "projection_years", label: "Hold Period (yrs)", step: 1 },
  { key: "exit_multiple", label: "Exit Multiple (x)", step: 0.25 },
  { key: "tax_rate", label: "Tax Rate", step: 0.01 },
  { key: "board_hurdle_irr", label: "Hurdle IRR", step: 0.01 },
  { key: "min_dscr_covenant", label: "Min DSCR Covenant", step: 0.05 },
];

export default function FinancingPage() {
  const [form, setForm] = useState(DEFAULTS);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const setField = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const run = async () => {
    setStatus("loading");
    setError("");
    try {
      const payload = { ...form };
      const res = await runLboAnalysis(payload);
      setResult(res.lbo_analysis);
      // Persist into the active deal report so the pitchbook (Reports tab) includes it.
      saveActiveReport({ ...getActiveReport(), financing: res.lbo_analysis });
      // Also persist to the backend deal record (per-deal, flows between modules) when a real deal is active.
      const dealId = getActiveDealMeta()?.id;
      if (dealId) {
        saveModuleOutput(dealId, "m6_lbo", res.lbo_analysis).catch(() => {});
      }
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "LBO analysis failed.");
    }
  };

  const returns = result?.returns;
  const covenants = result?.covenants;
  const su = result?.sources_and_uses;

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Module 6 · The Check</p>
          <h2>Financing &amp; LBO</h2>
          <p className="muted">Deterministic leveraged-acquisition model: capital stack, debt paydown, DSCR covenant, equity IRR / MOIC, and an entry/exit sensitivity grid.</p>
        </div>
        <button onClick={run} disabled={status === "loading"}>
          {status === "loading" ? "Running..." : "Run LBO Analysis"}
        </button>
      </section>

      <section className="panel-flat">
        <div className="section-title"><p className="eyebrow">Assumptions</p><h3>Model Inputs</h3></div>
        <div className="form-grid compact">
          {FIELDS.map((field) => (
            <label key={field.key}>
              {field.label}
              <input
                type="number"
                step={field.step}
                value={form[field.key]}
                onChange={(e) => setField(field.key, Number(e.target.value))}
              />
            </label>
          ))}
        </div>
      </section>

      {status === "error" && (
        <section className="panel-flat warning"><strong>LBO error</strong><p className="muted">{error}</p></section>
      )}

      {status === "ready" && result && (
        <>
          <section className="metric-grid">
            <div className={`metric-card ${returns.meets_hurdle ? "severity-low" : "severity-high"}`}>
              <span>Equity IRR</span><strong>{formatPercent(returns.equity_irr)}</strong>
            </div>
            <div className="metric-card"><span>MOIC</span><strong>{returns.moic ? `${returns.moic.toFixed(2)}x` : "n/a"}</strong></div>
            <div className="metric-card"><span>Sponsor Equity</span><strong>{formatCurrency(su.sources_sponsor_equity * 1e6)}</strong></div>
            <div className="metric-card"><span>Entry / Exit</span><strong>{result.entry_multiple.toFixed(1)}x / {result.exit_multiple.toFixed(1)}x</strong></div>
            <div className="metric-card"><span>Entry Leverage</span><strong>{su.entry_leverage_x?.toFixed(2)}x</strong></div>
            <div className={`metric-card ${covenants.covenant_breach ? "severity-high" : "severity-low"}`}>
              <span>Min DSCR</span><strong>{covenants.min_dscr?.toFixed(2)}x</strong>
            </div>
          </section>

          <p className="muted">✓ Saved to the active deal — this financing summary now flows into the board pitchbook (Reports tab).</p>

          <div className="chart-grid">
            <section className="panel-flat">
              <div className="section-title"><p className="eyebrow">Sources &amp; Uses</p><h3>Capital Stack</h3></div>
              <div className="capital-stack">
                {result.capital_stack.filter((t) => t.amount > 0).map((tranche) => (
                  <div key={tranche.tranche} className="capital-stack-row">
                    <span className="capital-stack-label">{tranche.tranche}</span>
                    <div className="capital-stack-bar-wrap">
                      <div className="capital-stack-bar" style={{ width: `${Math.max(2, tranche.pct_of_capital * 100)}%` }} />
                    </div>
                    <span className="capital-stack-value">{formatCurrency(tranche.amount * 1e6)} · {(tranche.pct_of_capital * 100).toFixed(0)}%</span>
                  </div>
                ))}
              </div>
              <p className="muted">Exit equity {formatCurrency(result.exit.exit_equity_value * 1e6)} at {result.exit.exit_year}-yr exit ({formatCurrency(result.exit.exit_enterprise_value * 1e6)} EV − {formatCurrency(result.exit.exit_net_debt * 1e6)} net debt).</p>
              {result.warnings?.length > 0 && (
                <ul className="warning-list">{result.warnings.map((w) => <li key={w}>{w}</li>)}</ul>
              )}
            </section>

            <section className="panel-flat">
              <div className="section-title"><p className="eyebrow">Returns Sensitivity</p><h3>Equity IRR — Entry × Exit Multiple</h3></div>
              <div className="sensitivity-scroll">
                <table className="data-table sensitivity-table">
                  <thead>
                    <tr>
                      <th>Exit ↓ / Entry →</th>
                      {result.sensitivity.entry_multiples.map((m) => <th key={m}>{m}x</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {result.sensitivity.equity_irr_matrix.map((row, i) => (
                      <tr key={result.sensitivity.exit_multiples[i]}>
                        <th>{result.sensitivity.exit_multiples[i]}x</th>
                        {row.map((cell, j) => (
                          <td
                            key={j}
                            className={cell == null ? "" : cell >= result.sensitivity.hurdle_irr ? "irr-pass" : "irr-fail"}
                          >
                            {cell == null ? "—" : `${(cell * 100).toFixed(0)}%`}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="muted">Green ≥ {formatPercent(result.sensitivity.hurdle_irr)} hurdle; red below.</p>
            </section>
          </div>

          <section className="table-panel">
            <div className="section-title"><p className="eyebrow">Debt Schedule</p><h3>Year-by-Year Deleveraging</h3></div>
            <table className="data-table">
              <thead>
                <tr><th>Year</th><th>EBITDA</th><th>Cash Interest</th><th>CFADS</th><th>Principal Repaid</th><th>Ending Debt</th><th>Net Leverage</th><th>DSCR</th></tr>
              </thead>
              <tbody>
                {result.debt_schedule.map((row) => (
                  <tr key={row.year}>
                    <td>{row.year}</td>
                    <td>{formatCurrency(row.ebitda * 1e6)}</td>
                    <td>{formatCurrency(row.cash_interest * 1e6)}</td>
                    <td>{formatCurrency(row.cfads * 1e6)}</td>
                    <td>{formatCurrency(row.principal_repaid * 1e6)}</td>
                    <td>{formatCurrency(row.ending_total_debt * 1e6)}</td>
                    <td>{row.net_leverage_x?.toFixed(2)}x</td>
                    <td className={row.dscr != null && row.dscr < result.covenants.min_dscr_covenant ? "irr-fail" : ""}>{row.dscr != null ? `${row.dscr.toFixed(2)}x` : "—"}</td>
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
