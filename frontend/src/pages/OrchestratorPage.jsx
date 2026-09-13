import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { runFullAnalysis } from "../lib/api";
import {
  DEMO_ASSUMPTIONS,
  DEMO_DEAL,
  DEMO_RISKS,
  loadDemoWorkspace,
  saveActiveDealMeta,
  saveActiveReport,
} from "../lib/dealUtils";

const acquirerCsv = `Year,Revenue,COGS,Operating_Expenses
2023,96000000,43000000,34600000
2024,108000000,47500000,38200000
2025,118000000,51800000,43800000`;

const targetCsv = `Year,Revenue,COGS,Operating_Expenses
2023,34000000,15500000,12700000
2024,38000000,17100000,14000000
2025,42000000,18600000,15300000`;

export default function OrchestratorPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [companyA, setCompanyA] = useState(null);
  const [companyB, setCompanyB] = useState(null);
  const [legalPdf, setLegalPdf] = useState(null);
  const [assumptions, setAssumptions] = useState(DEMO_ASSUMPTIONS);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const steps = useMemo(() => [
    ["Acquirer Financials", Boolean(companyA)],
    ["Target Financials", Boolean(companyB)],
    ["Legal Documents", Boolean(legalPdf)],
    ["Review Assumptions", true],
    ["Run Analysis", false],
  ], [companyA, companyB, legalPdf]);

  const loadDemo = () => {
    loadDemoWorkspace();
    setCompanyA(new File([acquirerCsv], "aster_capital_technologies_financials.csv", { type: "text/csv" }));
    setCompanyB(new File([targetCsv], "northstar_process_automation_financials.csv", { type: "text/csv" }));
    setLegalPdf(new File(["Sample legal diligence pack stored in sample_data/merger_pdf_pack."], "northstar_process_automation_diligence_pack.pdf", { type: "application/pdf" }));
    setAssumptions(DEMO_ASSUMPTIONS);
    setStep(4);
  };

  const runAnalysis = async () => {
    const acquirerFile = companyA || new File([acquirerCsv], "aster_capital_technologies_financials.csv", { type: "text/csv" });
    const targetFile = companyB || new File([targetCsv], "northstar_process_automation_financials.csv", { type: "text/csv" });
    setLoading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("company_a_file", acquirerFile);
      formData.append("company_b_file", targetFile);
      formData.append("orchestration_payload", JSON.stringify(assumptions));
      if (legalPdf && !legalPdf.name.includes("northstar_diligence_pack")) {
        formData.append("legal_pdf", legalPdf);
      }

      const result = await runFullAnalysis(formData);
      const enriched = result.legal_risks ? result : { ...result, legal_risks: { risks: DEMO_RISKS } };
      saveActiveDealMeta({ ...DEMO_DEAL, dealValue: enriched?.valuation?.enterprise_value || DEMO_DEAL.dealValue });
      saveActiveReport(enriched);
      navigate("/workspace");
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Analysis could not be completed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Guided Analysis</p>
          <h2>Valuation Workflow</h2>
        </div>
        <button onClick={loadDemo}>Load Aster Northstar Sample Deal</button>
      </section>

      <section className="stepper">
        {steps.map(([label, complete], index) => (
          <button key={label} className={step === index + 1 ? "active" : ""} onClick={() => setStep(index + 1)}>
            <span>{index + 1}</span>
            {label}
            {complete && <i>Complete</i>}
          </button>
        ))}
      </section>

      <section className="panel-flat">
        {step === 1 && <UploadStep title="Upload acquirer financials" file={companyA} onFile={setCompanyA} accept=".csv" />}
        {step === 2 && <UploadStep title="Upload target financials" file={companyB} onFile={setCompanyB} accept=".csv" />}
        {step === 3 && <UploadStep title="Upload legal documents" file={legalPdf} onFile={setLegalPdf} accept=".pdf" optional />}
        {step === 4 && (
          <div className="assumption-grid">
            <NumberField label="Discount Rate (WACC)" value={assumptions.dcf_assumptions.wacc} onChange={(value) => setAssumptions(updateAssumption(assumptions, "wacc", value))} />
            <NumberField label="Terminal Growth Rate" value={assumptions.dcf_assumptions.terminal_growth_rate} onChange={(value) => setAssumptions(updateAssumption(assumptions, "terminal_growth_rate", value))} />
            <NumberField label="Acquirer Market Cap" value={assumptions.acquirer_market_cap} onChange={(value) => setAssumptions({ ...assumptions, acquirer_market_cap: value })} />
            <NumberField label="Cost Reduction %" value={assumptions.synergy_assumptions.cost_reduction_pct} onChange={(value) => setAssumptions(updateSynergy(assumptions, "cost_reduction_pct", value))} />
            <NumberField label="Cross-Sell %" value={assumptions.synergy_assumptions.cross_sell_pct} onChange={(value) => setAssumptions(updateSynergy(assumptions, "cross_sell_pct", value))} />
          </div>
        )}
        {step === 5 && (
          <div className="run-card">
            <h3>Ready to run integrated analysis</h3>
            <p>Financials, assumptions, synergy logic, structuring, and negotiation guidance will be consolidated into the Deal Workspace.</p>
            <button onClick={runAnalysis} disabled={loading}>{loading ? "Running Analysis..." : "Run Analysis"}</button>
          </div>
        )}

        <div className="wizard-actions">
          <button className="secondary-button" disabled={step === 1} onClick={() => setStep(step - 1)}>Back</button>
          <button disabled={step === 5} onClick={() => setStep(step + 1)}>Continue</button>
        </div>
      </section>

      <details className="advanced-json" open={advancedOpen} onToggle={(e) => setAdvancedOpen(e.currentTarget.open)}>
        <summary>Advanced JSON</summary>
        <textarea
          rows={12}
          value={JSON.stringify(assumptions, null, 2)}
          onChange={(e) => {
            try {
              setAssumptions(JSON.parse(e.target.value));
            } catch {
              setError("Advanced JSON is not valid yet.");
            }
          }}
        />
      </details>

      {error && <p className="error-text">{typeof error === "string" ? error : JSON.stringify(error)}</p>}
    </div>
  );
}

function UploadStep({ title, file, onFile, accept, optional = false }) {
  return (
    <div className="upload-step">
      <h3>{title}</h3>
      <p>{optional ? "Optional, but recommended for risk extraction." : "Use the standard CSV format with year, revenue, cost of goods sold, and operating expenses."}</p>
      <input type="file" accept={accept} onChange={(e) => onFile(e.target.files?.[0] || null)} />
      {file && <span className="file-pill">{file.name}</span>}
    </div>
  );
}

function NumberField({ label, value, onChange }) {
  return (
    <label>
      {label}
      <input type="number" step="0.001" value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}

function updateAssumption(current, key, value) {
  return {
    ...current,
    dcf_assumptions: {
      ...current.dcf_assumptions,
      [key]: value,
    },
  };
}

function updateSynergy(current, key, value) {
  return {
    ...current,
    synergy_assumptions: {
      ...current.synergy_assumptions,
      [key]: value,
    },
  };
}
