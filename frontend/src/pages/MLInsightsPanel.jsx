import { useEffect, useState } from 'react';
import { getDealIntelligence } from '../lib/api';

export default function MLInsightsPanel({ companyAFinancials, companyBFinancials, marketContext }) {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!companyAFinancials?.length || !companyBFinancials?.length) {
      return;
    }

    let cancelled = false;
    getDealIntelligence({
      company_a_financials: companyAFinancials,
      company_b_financials: companyBFinancials,
      market_context: marketContext,
    })
      .then((data) => { if (!cancelled) setResult(data.result); })
      .catch((err) => {
        if (!cancelled) setError(err?.response?.data?.detail || err.message || 'Unable to load ML insights.');
      });
    return () => { cancelled = true; };
  }, [companyAFinancials, companyBFinancials, marketContext]);

  return (
    <div className="panel-flat" style={{ marginTop: '1rem' }}>
      <div className="section-title"><p className="eyebrow">ML Intelligence</p><h3>Deal Success & Risk</h3></div>
      {error && <p className="muted">{error}</p>}
      {!result && !error && <p className="muted">Waiting for financial inputs…</p>}
      {result && (
        <div className="metric-grid">
          <div className="metric-card"><span>Success Probability</span><strong>{result.deal_success_probability}</strong></div>
          <div className="metric-card"><span>Prediction</span><strong>{result.deal_success_label}</strong></div>
          <div className="metric-card"><span>Risk Class</span><strong>{result.risk_classification}</strong></div>
          <div className="metric-card"><span>Synergy Forecast</span><strong>${Number(result.synergy_forecast).toLocaleString()}</strong></div>
        </div>
      )}
    </div>
  );
}
