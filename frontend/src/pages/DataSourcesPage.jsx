import { useEffect, useState } from 'react';
import {
  getDealGenomeSummary,
  importEdgarDeals,
  listDealGenomeTransactions,
  searchEdgarDeals,
  seedDealGenomeSample,
} from '../lib/api';

function DataSourcesPage() {
  const [summary, setSummary] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');

  const refresh = () => {
    setStatus('loading');
    Promise.all([
      getDealGenomeSummary(),
      listDealGenomeTransactions({ limit: 8 }),
    ])
      .then(([summaryPayload, transactionPayload]) => {
        setSummary(summaryPayload);
        setTransactions(transactionPayload.transactions || []);
        setStatus('ready');
        setError('');
      })
      .catch((err) => {
        setError(err?.response?.data?.detail || err.message || 'Unable to load Deal Genome data.');
        setStatus('error');
      });
  };

  useEffect(() => {
    refresh();
  }, []);

  const seedSamples = async () => {
    setStatus('loading');
    try {
      await seedDealGenomeSample();
      refresh();
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Unable to seed sample transactions.');
      setStatus('error');
    }
  };

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Data Foundation</p>
          <h2>External Data & Deal Genome</h2>
          <p className="muted">Track what is real, what is sample, and how many historical transactions are actually loaded.</p>
        </div>
        <button onClick={seedSamples} disabled={status === 'loading'}>Seed Sample Deals</button>
      </section>

      {error && <p className="empty-state">{error}</p>}

      <EdgarImportPanel onImported={refresh} />

      <section className="metric-grid">
        <MetricCard label="Transactions Loaded" value={summary ? summary.total_transactions.toLocaleString() : '...'} />
        <MetricCard label="Database Claim" value={summary?.database_claim || 'Loading'} />
        <MetricCard label="Source Types" value={summary ? Object.keys(summary.by_source_type).length : '...'} />
        <MetricCard label="Sectors Covered" value={summary ? Object.keys(summary.by_sector).length : '...'} />
      </section>

      {summary && (
        <section className="panel-flat">
          <div className="section-title">
            <p className="eyebrow">Integrity Guardrail</p>
            <h3>Current Database Status</h3>
          </div>
          <p className="muted">{summary.note}</p>
          <div className="source-list">
            {Object.entries(summary.by_source_type).map(([source, count]) => (
              <span className="source-chip" key={source}>{source}: {count}</span>
            ))}
          </div>
        </section>
      )}

      <section className="table-panel">
        <div className="section-title">
          <p className="eyebrow">Recent Records</p>
          <h3>Deal Genome Transactions</h3>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Buyer</th>
              <th>Target</th>
              <th>Sector</th>
              <th>Status</th>
              <th>Deal Value</th>
              <th>Source</th>
            </tr>
          </thead>
          <tbody>
            {transactions.map((deal) => (
              <tr key={deal.id}>
                <td>{deal.buyer_name}</td>
                <td>{deal.target_name}</td>
                <td>{deal.sector}</td>
                <td><span className="source-chip">{deal.deal_status}</span></td>
                <td>{deal.deal_value ? `$${Number(deal.deal_value).toLocaleString()}` : 'Unknown'}</td>
                <td>{deal.source_type}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {transactions.length === 0 && <p className="empty-state">No Deal Genome records loaded yet. Seed sample deals or import a CSV through the API.</p>}
      </section>
    </div>
  );
}

function MetricCard({ label, value }) {
  return <div className="metric-card"><span>{label}</span><strong>{value}</strong></div>;
}

function EdgarImportPanel({ onImported }) {
  const [query, setQuery] = useState('"merger agreement"');
  const [forms, setForms] = useState('8-K');
  const [limit, setLimit] = useState(10);
  const [enrich, setEnrich] = useState(false);
  const [filings, setFilings] = useState([]);
  const [status, setStatus] = useState('idle');
  const [msg, setMsg] = useState('');

  const preview = async () => {
    setStatus('loading'); setMsg('');
    try {
      const res = await searchEdgarDeals({ q: query, forms, limit });
      setFilings(res.filings || []);
      setStatus('ready');
    } catch (err) {
      setMsg(err?.response?.data?.detail || err.message || 'EDGAR search failed.');
      setStatus('error');
    }
  };

  const doImport = async () => {
    setStatus('loading'); setMsg('');
    try {
      const res = await importEdgarDeals({ q: query, forms, limit, enrich });
      const v = res.result.deal_values_extracted;
      setMsg(`Imported ${res.result.imported} real deals from SEC EDGAR into the Deal Genome${enrich ? ` (${v} with parsed deal values)` : ''}.`);
      setStatus('ready');
      onImported?.();
    } catch (err) {
      setMsg(err?.response?.data?.detail || err.message || 'EDGAR import failed.');
      setStatus('error');
    }
  };

  return (
    <section className="panel-flat">
      <div className="section-title">
        <p className="eyebrow">SEC EDGAR · Free, no key</p>
        <h3>Import Real M&amp;A Deals</h3>
      </div>
      <p className="muted">Pull real merger filings from SEC EDGAR full-text search into the Deal Genome — real history instead of synthetic samples.</p>
      <div className="form-grid compact">
        <label>Search query<input type="text" value={query} onChange={(e) => setQuery(e.target.value)} /></label>
        <label>Forms<input type="text" value={forms} onChange={(e) => setForms(e.target.value)} /></label>
        <label>Limit<input type="number" min="1" max="100" value={limit} onChange={(e) => setLimit(Number(e.target.value))} /></label>
        <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><input type="checkbox" checked={enrich} onChange={(e) => setEnrich(e.target.checked)} />Parse deal values (slower)</label>
      </div>
      <div className="topbar-actions">
        <button className="secondary-button" onClick={preview} disabled={status === 'loading'}>Preview</button>
        <button onClick={doImport} disabled={status === 'loading'}>{status === 'loading' ? 'Working…' : 'Import Real Deals'}</button>
      </div>
      {msg && <p className="muted" style={{ color: status === 'error' ? '#f2a3a3' : '#7ee6c6' }}>{msg}</p>}
      {filings.length > 0 && (
        <table className="data-table" style={{ marginTop: 12 }}>
          <thead><tr><th>Company</th><th>Form</th><th>Filed</th><th>Sector</th><th>Filing</th></tr></thead>
          <tbody>
            {filings.map((f, i) => (
              <tr key={i}>
                <td>{f.company}</td><td>{f.form}</td><td>{f.filed_date}</td><td>{f.sector}</td>
                <td>{f.url ? <a href={f.url} target="_blank" rel="noreferrer">view</a> : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export default DataSourcesPage;
