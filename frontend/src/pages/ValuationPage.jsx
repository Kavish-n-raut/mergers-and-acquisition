import React, { useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  LabelList,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { DEMO_ASSUMPTIONS, DEMO_VALUATION, formatCurrency, formatPercent, getActiveReport, getMetrics } from "../lib/dealUtils";
import { getMarketAssumptions, runDriverDcf } from "../lib/api";
import OrchestratorPage from "./OrchestratorPage";
import MLInsightsPanel from "./MLInsightsPanel";

const chartColors = {
  gold: "#d6a13a",
  teal: "#31c6a0",
  blue: "#6aa7ff",
  grid: "#26313a",
  text: "#eef2f4",
  muted: "#a7b2b8",
};

export default function ValuationPage() {
  const [mode, setMode] = useState("dashboard");
  const [assumptions, setAssumptions] = useState(DEMO_ASSUMPTIONS);
  const [marketAssumptions, setMarketAssumptions] = useState(null);
  const [marketAssumptionsStatus, setMarketAssumptionsStatus] = useState("loading");
  const [marketAssumptionsError, setMarketAssumptionsError] = useState("");
  const report = getActiveReport();
  const metrics = getMetrics(report);

  useEffect(() => {
    let isActive = true;
    setMarketAssumptionsStatus("loading");
    getMarketAssumptions()
      .then((data) => {
        if (!isActive) return;
        setMarketAssumptions(data);
        setMarketAssumptionsStatus("ready");
        setAssumptions((current) => ({
          ...current,
          dcf_assumptions: {
            ...current.dcf_assumptions,
            wacc: data.wacc,
            terminal_growth_rate: data.terminal_growth_rate,
          },
        }));
      })
      .catch((error) => {
        if (!isActive) return;
        setMarketAssumptionsStatus("error");
        setMarketAssumptionsError(error?.response?.data?.detail || error.message || "Market assumptions unavailable.");
      });
    return () => {
      isActive = false;
    };
  }, []);

  const footballData = useMemo(() => DEMO_VALUATION.footballField.map((row) => ({
    ...row,
    range: [row.low, row.high],
    midpoint: (row.low + row.high) / 2,
  })), []);

  const enterpriseValueMarker = Number.isFinite(metrics.enterpriseValue) ? metrics.enterpriseValue / 1000000 : null;

  if (mode === "analysis") {
    return (
      <div className="page">
        <section className="page-header">
          <div><p className="eyebrow">Guided Analysis</p><h2>Run Valuation Workflow</h2></div>
          <button className="secondary-button" onClick={() => setMode("dashboard")}>Back to Valuation</button>
        </section>
        <OrchestratorPage />
      </div>
    );
  }

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Valuation Dashboard</p>
          <h2>Valuation</h2>
          <p className="muted">Board-ready range analysis, operating trends, and synergy value creation.</p>
        </div>
        <button onClick={() => setMode("analysis")}>Run New Analysis</button>
      </section>

      <section className="metric-grid">
        <MetricCard label="Enterprise Value" value={formatCurrency(metrics.enterpriseValue)} />
        <MetricCard label="EBITDA" value={formatCurrency(metrics.ebitda)} />
        <MetricCard label="Revenue Growth" value={formatPercent(metrics.revenueGrowth)} />
        <MetricCard label="DCF Value" value={formatCurrency(metrics.dcfValue)} />
        <MetricCard label="Synergy Value" value={formatCurrency(metrics.synergyValue)} />
        <MetricCard label="Opening Bid" value={formatCurrency(metrics.openingBid)} />
        <MetricCard label="Walk-Away Price" value={formatCurrency(metrics.walkAway)} />
      </section>

      <MLInsightsPanel
        companyAFinancials={[
          { Year: 2020, Revenue: 10000000, COGS: 6000000, Operating_Expenses: 1800000 },
          { Year: 2021, Revenue: 11200000, COGS: 6600000, Operating_Expenses: 1900000 },
          { Year: 2022, Revenue: 12500000, COGS: 7200000, Operating_Expenses: 2000000 },
        ]}
        companyBFinancials={[
          { Year: 2020, Revenue: 8000000, COGS: 4800000, Operating_Expenses: 1500000 },
          { Year: 2021, Revenue: 9000000, COGS: 5200000, Operating_Expenses: 1600000 },
          { Year: 2022, Revenue: 10200000, COGS: 5600000, Operating_Expenses: 1700000 },
        ]}
        marketContext={{ filings_signal: [{ name: 'sample' }], acquisition_signal: [{ name: 'sample' }] }}
      />

      <section className="chart-grid">
        <div className="panel-flat chart-card valuation-range-card">
          <div className="section-title chart-title-row">
            <div><p className="eyebrow">Football Field</p><h3>Football Field Valuation Range</h3></div>
            <span className="source-chip">USD millions</span>
          </div>
          <div className="chart-shell tall">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={footballData} layout="vertical" margin={{ top: 14, right: 126, bottom: 34, left: 18 }}>
                <defs>
                  <linearGradient id="valuationRangeGradient" x1="0" x2="1" y1="0" y2="0">
                    <stop offset="0%" stopColor={chartColors.gold} />
                    <stop offset="100%" stopColor={chartColors.teal} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  domain={[60, 112]}
                  tick={{ fill: chartColors.muted, fontSize: 12 }}
                  tickFormatter={(value) => `$${value}M`}
                  allowDataOverflow
                  label={{ value: "Implied enterprise value", position: "insideBottom", offset: -10, fill: chartColors.muted }}
                />
                <YAxis
                  dataKey="method"
                  type="category"
                  width={142}
                  tick={{ fill: chartColors.text, fontSize: 13 }}
                />
                <Tooltip content={<ValuationTooltip />} cursor={{ fill: "rgba(255,255,255,0.04)" }} />
                {enterpriseValueMarker && (
                  <ReferenceLine
                    x={enterpriseValueMarker}
                    stroke={chartColors.blue}
                    strokeDasharray="5 5"
                    label={{ value: "Current EV", fill: chartColors.blue, fontSize: 12, position: "top" }}
                  />
                )}
                <Bar dataKey="range" fill="url(#valuationRangeGradient)" radius={[8, 8, 8, 8]} barSize={16}>
                  <LabelList content={(props) => <RangeValueLabel {...props} data={footballData} />} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel-flat chart-card">
          <div className="section-title chart-title-row">
            <div><p className="eyebrow">Operating Trend</p><h3>Revenue vs EBITDA</h3></div>
            <span className="source-chip">Management case</span>
          </div>
          <div className="chart-shell">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={DEMO_VALUATION.trends} margin={{ top: 16, right: 20, bottom: 28, left: 12 }}>
                <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="year" tick={{ fill: chartColors.muted, fontSize: 12 }} />
                <YAxis
                  tick={{ fill: chartColors.muted, fontSize: 12 }}
                  tickFormatter={(value) => `$${value}M`}
                  label={{ value: "USD millions", angle: -90, position: "insideLeft", fill: chartColors.muted }}
                />
                <Tooltip content={<StandardTooltip suffix="M" />} />
                <Legend wrapperStyle={{ color: chartColors.muted, fontSize: 12 }} />
                <Bar dataKey="revenue" name="Revenue" fill={chartColors.blue} radius={[6, 6, 0, 0]} barSize={34} />
                <Line dataKey="ebitda" name="EBITDA" type="monotone" stroke={chartColors.teal} strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel-flat chart-card">
          <div className="section-title chart-title-row">
            <div><p className="eyebrow">Synergies</p><h3>Value Creation Breakdown</h3></div>
            <span className="source-chip">Annual run-rate</span>
          </div>
          <div className="chart-shell">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={DEMO_VALUATION.synergyBreakdown} layout="vertical" margin={{ top: 18, right: 58, bottom: 28, left: 18 }}>
                <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: chartColors.muted, fontSize: 12 }}
                  tickFormatter={(value) => `$${value}M`}
                  label={{ value: "Annual synergy value", position: "insideBottom", offset: -10, fill: chartColors.muted }}
                />
                <YAxis dataKey="label" type="category" width={150} tick={{ fill: chartColors.text, fontSize: 12 }} />
                <Tooltip content={<StandardTooltip suffix="M" />} />
                <Bar dataKey="value" name="Run-rate synergy" fill={chartColors.teal} radius={[0, 8, 8, 0]} barSize={18}>
                  <LabelList dataKey="value" position="right" formatter={(value) => `$${Number(value).toFixed(1)}M`} fill={chartColors.text} fontSize={12} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel-flat assumptions-card">
          <div className="section-title"><p className="eyebrow">Assumptions</p><h3>Model Inputs</h3></div>
          <p className="muted">Keep this form-based for business users. Advanced JSON remains hidden in the analysis workflow.</p>
          <MarketAssumptionsPanel
            data={marketAssumptions}
            status={marketAssumptionsStatus}
            error={marketAssumptionsError}
            onApply={() => {
              if (!marketAssumptions) return;
              setAssumptions({
                ...assumptions,
                dcf_assumptions: {
                  ...assumptions.dcf_assumptions,
                  wacc: marketAssumptions.wacc,
                  terminal_growth_rate: marketAssumptions.terminal_growth_rate,
                },
              });
            }}
          />
          <div className="form-grid compact">
            <NumberField label="WACC" value={assumptions.dcf_assumptions.wacc} onChange={(value) => setAssumptions({ ...assumptions, dcf_assumptions: { ...assumptions.dcf_assumptions, wacc: value } })} />
            <NumberField label="Terminal Growth" value={assumptions.dcf_assumptions.terminal_growth_rate} onChange={(value) => setAssumptions({ ...assumptions, dcf_assumptions: { ...assumptions.dcf_assumptions, terminal_growth_rate: value } })} />
            <NumberField label="Cost Synergy %" value={assumptions.synergy_assumptions.cost_reduction_pct} onChange={(value) => setAssumptions({ ...assumptions, synergy_assumptions: { ...assumptions.synergy_assumptions, cost_reduction_pct: value } })} />
            <NumberField label="Cross-Sell %" value={assumptions.synergy_assumptions.cross_sell_pct} onChange={(value) => setAssumptions({ ...assumptions, synergy_assumptions: { ...assumptions.synergy_assumptions, cross_sell_pct: value } })} />
          </div>
          <button>Save Assumptions</button>
        </div>
      </section>

      <DriverDcfPanel />
    </div>
  );
}

function DriverDcfPanel() {
  const [form, setForm] = useState({
    base_revenue: 1000,
    revenue_growth_rate: 0.1,
    projection_years: 5,
    ebitda_margin: 0.25,
    wacc: 0.1,
    terminal_growth_rate: 0.025,
    net_debt: 200,
    scenario_delta: 0.15,
  });
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  const fields = [
    ["base_revenue", "Base Revenue ($M)", 1],
    ["revenue_growth_rate", "Revenue Growth", 0.01],
    ["ebitda_margin", "EBITDA Margin", 0.01],
    ["projection_years", "Years", 1],
    ["wacc", "WACC", 0.005],
    ["terminal_growth_rate", "Terminal Growth", 0.005],
    ["net_debt", "Net Debt ($M)", 1],
    ["scenario_delta", "Bull/Bear Delta", 0.05],
  ];

  const run = async () => {
    setStatus("loading");
    setError("");
    try {
      const res = await runDriverDcf(form);
      setResult(res.valuation);
      setStatus("ready");
    } catch (err) {
      setStatus("error");
      setError(err?.response?.data?.detail || err.message || "Driver DCF failed.");
    }
  };

  const evRange = result?.enterprise_value_range;
  const chartData = evRange
    ? [
        { case: "Bear", ev: evRange.bear },
        { case: "Base", ev: evRange.base },
        { case: "Bull", ev: evRange.bull },
      ]
    : [];

  return (
    <section className="panel-flat">
      <div className="section-title"><p className="eyebrow">M3 · Driver-Based DCF</p><h3>Base / Bull / Bear from operating drivers</h3></div>
      <div className="form-grid compact">
        {fields.map(([key, label, step]) => (
          <label key={key}>{label}
            <input type="number" step={step} value={form[key]} onChange={(e) => setForm((f) => ({ ...f, [key]: Number(e.target.value) }))} />
          </label>
        ))}
      </div>
      <button onClick={run} disabled={status === "loading"}>{status === "loading" ? "Running..." : "Run Driver DCF"}</button>
      {status === "error" && <p className="muted" style={{ color: "#f2a3a3" }}>{error}</p>}
      {status === "ready" && result && (
        <>
          <section className="metric-grid" style={{ marginTop: 16 }}>
            <div className="metric-card"><span>Bear EV</span><strong>{formatCurrency(evRange.bear * 1e6)}</strong></div>
            <div className="metric-card"><span>Base EV</span><strong>{formatCurrency(evRange.base * 1e6)}</strong></div>
            <div className="metric-card"><span>Bull EV</span><strong>{formatCurrency(evRange.bull * 1e6)}</strong></div>
            <div className="metric-card"><span>Base Equity</span><strong>{formatCurrency(result.equity_value_range.base * 1e6)}</strong></div>
          </section>
          <div className="chart-shell">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 16, right: 20, bottom: 20, left: 12 }}>
                <CartesianGrid stroke={chartColors.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="case" tick={{ fill: chartColors.muted, fontSize: 12 }} />
                <YAxis tick={{ fill: chartColors.muted, fontSize: 12 }} tickFormatter={(v) => `$${v}M`} />
                <Tooltip content={<StandardTooltip suffix="M" />} />
                <Bar dataKey="ev" name="Enterprise Value" fill={chartColors.gold} radius={[6, 6, 0, 0]} barSize={48} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </section>
  );
}

function MetricCard({ label, value }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong></div>;
}

function MarketAssumptionsPanel({ data, status, error, onApply }) {
  if (status === "loading") {
    return (
      <div className="market-assumptions-panel">
        <div className="mini-loader" />
        <span>Loading public WACC assumptions...</span>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="market-assumptions-panel warning">
        <strong>Market assumptions unavailable</strong>
        <span>{error}</span>
      </div>
    );
  }

  if (!data) return null;

  const rows = [
    ["Risk-free rate", data.risk_free_rate],
    ["Equity risk premium", data.equity_risk_premium],
    ["Beta", data.beta],
    ["Cost of equity", data.cost_of_equity],
    ["After-tax debt cost", data.after_tax_cost_of_debt],
    ["Calculated WACC", data.wacc],
  ];

  return (
    <div className="market-assumptions-panel">
      <div className="market-assumptions-header">
        <div>
          <span className="source-chip">Market-calibrated WACC</span>
          <strong>{formatPercent(data.wacc)}</strong>
        </div>
        <button className="secondary-button compact-button" onClick={onApply}>Apply</button>
      </div>
      <div className="assumption-breakdown">
        {rows.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{label === "Beta" ? Number(value).toFixed(2) : formatPercent(value)}</strong>
          </div>
        ))}
      </div>
      <p className="muted">{data.note}</p>
      <div className="source-list">
        <span className={`source-chip source-mode-${data.source_mode}`}>{data.source_mode}</span>
        {data.sources.slice(0, 2).map((source) => (
          <small key={`${source.name}-${source.date}`}>{source.name}: {source.value}</small>
        ))}
      </div>
    </div>
  );
}

function RangeValueLabel({ x, y, width, height, index, data }) {
  const row = data[index];
  if (!row) return null;
  return (
    <text x={x + width + 10} y={y + height / 2 + 5} fill={chartColors.text} fontSize={12} fontWeight={700}>
      {`$${row.low}M - $${row.high}M`}
    </text>
  );
}

function ValuationTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="chart-tooltip">
      <strong>{row.method}</strong>
      <span>Low: ${row.low}M</span>
      <span>High: ${row.high}M</span>
      <span>Midpoint: ${row.midpoint.toFixed(1)}M</span>
    </div>
  );
}

function StandardTooltip({ active, payload, label, suffix = "" }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <strong>{label}</strong>
      {payload.map((item) => (
        <span key={item.name} style={{ color: item.color }}>
          {item.name}: ${Number(item.value).toFixed(1)}{suffix}
        </span>
      ))}
    </div>
  );
}

function NumberField({ label, value, onChange }) {
  return (
    <label>{label}<input type="number" step="0.001" value={value} onChange={(e) => onChange(Number(e.target.value))} /></label>
  );
}
