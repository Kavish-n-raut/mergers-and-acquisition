import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createDeal, listDeals } from "../lib/api";
import {
  DEAL_TYPES,
  DEMO_DEAL,
  STAGE_OPTIONS,
  displayDealName,
  formatCurrency,
  getDealMetadataMap,
  loadDemoWorkspace,
  saveActiveDealMeta,
  saveDealMetadata,
  stageLabel,
  statusLabel,
} from "../lib/dealUtils";

const statusFilters = ["All", "In Progress", "Completed", "Blocked"];

const emptyForm = {
  dealName: "",
  buyerName: "",
  targetName: "",
  dealType: "Acquisition",
  dealValue: 0,
  sector: "",
  geography: "",
  stage: "m1_hunt",
  teamMembers: "",
  owner: "",
};

export default function DealsPage() {
  const navigate = useNavigate();
  const [deals, setDeals] = useState([]);
  const [metadata, setMetadata] = useState(getDealMetadataMap());
  const [form, setForm] = useState(emptyForm);
  const [stageFilter, setStageFilter] = useState("All");
  const [statusFilter, setStatusFilter] = useState("All");
  const [archived, setArchived] = useState(() => JSON.parse(localStorage.getItem("archivedDealIds") || "[]"));
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const refresh = async () => {
    setLoading(true);
    setError("");
    try {
      const rows = await listDeals(100);
      setDeals(rows);
      setMetadata(getDealMetadataMap());
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Unable to load deal pipeline.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const enrichedDeals = useMemo(() => {
    const backendDeals = deals.map((deal) => ({
      ...deal,
      meta: metadata[deal.id] || {},
    }));
    const showDemo = localStorage.getItem("activeDealMeta");
    const demoRow = showDemo
      ? [{
          id: "sample",
          deal_name: DEMO_DEAL.dealName,
          stage: DEMO_DEAL.stage,
          status: DEMO_DEAL.status,
          updated_at: new Date().toISOString(),
          meta: DEMO_DEAL,
          sample: true,
        }]
      : [];
    return [...demoRow, ...backendDeals];
  }, [deals, metadata]);

  const visibleDeals = enrichedDeals
    .filter((deal) => !archived.includes(deal.id))
    .filter((deal) => stageFilter === "All" || stageLabel(deal.stage) === stageFilter)
    .filter((deal) => statusFilter === "All" || statusLabel(deal.status) === statusFilter);

  const createNewDeal = async () => {
    if (!form.dealName.trim() || !form.buyerName.trim() || !form.targetName.trim()) {
      setError("Deal name, buyer, and target are required.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const created = await createDeal(form.dealName.trim());
      const meta = {
        ...DEMO_DEAL,
        ...form,
        dealValue: Number(form.dealValue || 0),
        teamMembers: form.teamMembers.split(",").map((member) => member.trim()).filter(Boolean),
        transactionCode: `TX-${created.id.slice(0, 8).toUpperCase()}`,
        status: created.status,
        id: created.id,
      };
      saveDealMetadata(created.id, meta);
      saveActiveDealMeta(meta);
      localStorage.setItem("activeDealId", created.id);
      setForm(emptyForm);
      await refresh();
      navigate("/workspace");
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Unable to create deal.");
    } finally {
      setLoading(false);
    }
  };

  const openDeal = (deal) => {
    const meta = deal.sample ? DEMO_DEAL : { ...DEMO_DEAL, ...deal.meta, dealName: displayDealName(deal.deal_name), stage: deal.stage, status: deal.status, transactionCode: deal.meta?.transactionCode || `TX-${deal.id.slice(0, 8).toUpperCase()}` };
    saveActiveDealMeta(meta);
    if (!deal.sample) localStorage.setItem("activeDealId", deal.id);
    navigate("/workspace");
  };

  const archiveDeal = (dealId) => {
    const updated = Array.from(new Set([...archived, dealId]));
    setArchived(updated);
    localStorage.setItem("archivedDealIds", JSON.stringify(updated));
    setNotice("Deal archived from this workspace.");
  };

  const copyId = async (dealId) => {
    if (dealId === "sample") return;
    await navigator.clipboard.writeText(dealId);
    setNotice("Deal ID copied.");
  };

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Origination & Execution</p>
          <h2>Deal Pipeline</h2>
        </div>
        <button onClick={() => { loadDemoWorkspace(); navigate("/workspace"); }}>
          Load Sample Deal
        </button>
      </section>

      <section className="panel-flat">
        <div className="section-title">
          <p className="eyebrow">New Deal</p>
          <h3>Guided Setup</h3>
        </div>
        <div className="form-grid">
          <Field label="Deal name" value={form.dealName} onChange={(dealName) => setForm({ ...form, dealName })} />
          <Field label="Buyer name" value={form.buyerName} onChange={(buyerName) => setForm({ ...form, buyerName })} />
          <Field label="Target name" value={form.targetName} onChange={(targetName) => setForm({ ...form, targetName })} />
          <label>Deal type<select value={form.dealType} onChange={(e) => setForm({ ...form, dealType: e.target.value })}>{DEAL_TYPES.map((type) => <option key={type}>{type}</option>)}</select></label>
          <Field type="number" label="Estimated deal value" value={form.dealValue} onChange={(dealValue) => setForm({ ...form, dealValue })} />
          <Field label="Sector" value={form.sector} onChange={(sector) => setForm({ ...form, sector })} />
          <Field label="Geography" value={form.geography} onChange={(geography) => setForm({ ...form, geography })} />
          <label>Current stage<select value={form.stage} onChange={(e) => setForm({ ...form, stage: e.target.value })}>{STAGE_OPTIONS.map((stage) => <option key={stage.value} value={stage.value}>{stage.label}</option>)}</select></label>
          <Field label="Deal owner" value={form.owner} onChange={(owner) => setForm({ ...form, owner })} />
          <Field label="Team members" value={form.teamMembers} onChange={(teamMembers) => setForm({ ...form, teamMembers })} placeholder="Names separated by commas" />
        </div>
        <button onClick={createNewDeal} disabled={loading}>Create Deal</button>
      </section>

      <section className="toolbar-row">
        <label>Stage<select value={stageFilter} onChange={(e) => setStageFilter(e.target.value)}><option>All</option>{Object.values(STAGE_OPTIONS).map((stage) => <option key={stage.label}>{stage.label}</option>)}</select></label>
        <label>Status<select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>{statusFilters.map((status) => <option key={status}>{status}</option>)}</select></label>
        <button className="secondary-button" onClick={refresh}>Refresh</button>
      </section>

      <section className="table-panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Deal</th>
              <th>Buyer</th>
              <th>Target</th>
              <th>Value</th>
              <th>Stage</th>
              <th>Status</th>
              <th>Owner</th>
              <th>Last Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleDeals.map((deal) => (
              <tr key={deal.id}>
                <td><strong>{displayDealName(deal.deal_name)}</strong><span className="subtext">{deal.meta?.dealType || "Acquisition"}</span></td>
                <td>{deal.meta?.buyerName || "Not assigned"}</td>
                <td>{deal.meta?.targetName || "Not assigned"}</td>
                <td>{formatCurrency(deal.meta?.dealValue)}</td>
                <td>{stageLabel(deal.stage)}</td>
                <td><span className={`status-badge status-${deal.status}`}>{statusLabel(deal.status)}</span></td>
                <td>{deal.meta?.owner || "Deal Team"}</td>
                <td>{new Date(deal.updated_at).toLocaleDateString()}</td>
                <td>
                  <div className="action-row">
                    <button className="small-button" onClick={() => openDeal(deal)}>Open Deal</button>
                    <details className="more-menu">
                      <summary>More</summary>
                      <button className="small-button secondary-button" onClick={() => copyId(deal.id)}>Copy ID</button>
                      <button className="small-button text-button" onClick={() => archiveDeal(deal.id)}>Archive</button>
                    </details>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {visibleDeals.length === 0 && <p className="empty-state">No deals match this view.</p>}
      </section>

      {notice && <p className="success-text">{notice}</p>}
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}

function Field({ label, value, onChange, type = "text", placeholder = "" }) {
  return (
    <label>
      {label}
      <input type={type} value={value} placeholder={placeholder} onChange={(e) => onChange(type === "number" ? Number(e.target.value) : e.target.value)} />
    </label>
  );
}

