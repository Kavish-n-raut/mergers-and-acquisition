import React, { useState } from "react";
import { Link } from "react-router-dom";
import {
  DEMO_ACTIVITY,
  DEMO_CLOSING_CHECKLIST,
  DEMO_INTEGRATION_TASKS,
  DEMO_NEGOTIATION_TERMS,
  DEMO_REPORT_HISTORY,
  DEMO_TIMELINE,
  formatCurrency,
  formatPercent,
  getActiveDealMeta,
  getActiveDocuments,
  getActiveReport,
  getMetrics,
  nextRecommendedAction,
  riskItems,
  stageLabel,
  statusLabel,
} from "../lib/dealUtils";

const tabs = ["Overview", "Financials", "Documents", "Risks", "Valuation", "Negotiation", "Closing", "Integration", "Reports"];

export default function DealWorkspacePage() {
  const [activeTab, setActiveTab] = useState("Overview");
  const meta = getActiveDealMeta();
  const report = getActiveReport();
  const metrics = getMetrics(report);
  const risks = riskItems(report);
  const documents = getActiveDocuments();

  return (
    <div className="page">
      <section className="workspace-hero">
        <div>
          <p className="eyebrow">Deal Workspace</p>
          <h2>{meta.dealName}</h2>
          <p>{meta.buyerName} acquiring {meta.targetName}</p>
        </div>
        <div className="workspace-code">
          <span>{meta.transactionCode}</span>
          <strong>{stageLabel(meta.stage)}</strong>
        </div>
      </section>

      <section className="tab-bar">
        {tabs.map((tab) => (
          <button key={tab} className={activeTab === tab ? "active" : ""} onClick={() => setActiveTab(tab)}>
            {tab}
          </button>
        ))}
      </section>

      {activeTab === "Overview" && (
        <section className="workspace-grid">
          <div className="panel-flat span-2">
            <div className="section-title"><p className="eyebrow">Decision Summary</p><h3>Executive Overview</h3></div>
            <div className="detail-grid">
              <div><span>Deal Value</span><strong>{formatCurrency(meta.dealValue || metrics.enterpriseValue)}</strong></div>
              <div><span>Current Stage</span><strong>{stageLabel(meta.stage)}</strong></div>
              <div><span>Status</span><strong>{statusLabel(meta.status)}</strong></div>
              <div><span>Close Probability</span><strong>{meta.closeProbability || 62}%</strong></div>
              <div><span>Sector</span><strong>{meta.sector}</strong></div>
              <div><span>Geography</span><strong>{meta.geography}</strong></div>
            </div>
            <div className="recommendation"><span>Next action</span><strong>{nextRecommendedAction(report)}</strong></div>
          </div>

          <div className="panel-flat">
            <div className="section-title"><p className="eyebrow">Top Risks</p><h3>Diligence Status</h3></div>
            <ul className="clean-list">
              {risks.slice(0, 3).map((risk) => <li key={risk.risk_category}><strong>{risk.severity}</strong> {risk.risk_category}</li>)}
            </ul>
          </div>

          <div className="panel-flat">
            <div className="section-title"><p className="eyebrow">Deal Team</p><h3>Coverage</h3></div>
            <ul className="people-list">{(meta.teamMembers || []).map((member) => <li key={member}>{member}</li>)}</ul>
          </div>

          <div className="panel-flat">
            <div className="section-title"><p className="eyebrow">Recent Activity</p><h3>Latest Updates</h3></div>
            <ul className="clean-list">{DEMO_ACTIVITY.map((item) => <li key={item}>{item}</li>)}</ul>
          </div>

          <div className="panel-flat span-2">
            <div className="section-title"><p className="eyebrow">Milestones</p><h3>Transaction Timeline</h3></div>
            <div className="timeline-row">
              {DEMO_TIMELINE.map((item) => (
                <div key={item.label}><strong>{item.label}</strong><span>{item.date}</span><em>{item.status}</em></div>
              ))}
            </div>
          </div>
        </section>
      )}

      {activeTab === "Financials" && <Financials metrics={metrics} />}
      {activeTab === "Documents" && <Documents documents={documents} />}
      {activeTab === "Risks" && <RiskCards risks={risks} />}
      {activeTab === "Valuation" && <ValueBars metrics={metrics} />}
      {activeTab === "Negotiation" && <Terms report={report} metrics={metrics} />}
      {activeTab === "Closing" && <Checklist />}
      {activeTab === "Integration" && <IntegrationPlan />}
      {activeTab === "Reports" && <Reports />}
    </div>
  );
}

function Financials({ metrics }) {
  return (
    <section className="metric-grid">
      <div className="metric-card"><span>Buyer Revenue</span><strong>{formatCurrency(metrics.acquirerRevenue)}</strong></div>
      <div className="metric-card"><span>Target Revenue</span><strong>{formatCurrency(metrics.targetRevenue)}</strong></div>
      <div className="metric-card"><span>EBITDA</span><strong>{formatCurrency(metrics.ebitda)}</strong></div>
      <div className="metric-card"><span>Revenue Growth</span><strong>{formatPercent(metrics.revenueGrowth)}</strong></div>
      <div className="metric-card"><span>EBITDA Margin</span><strong>{formatPercent(metrics.ebitdaMargin)}</strong></div>
    </section>
  );
}

function Documents({ documents }) {
  return (
    <section className="table-panel">
      <table className="data-table">
        <thead><tr><th>Document</th><th>Type</th><th>Owner</th><th>Status</th><th>Risks</th></tr></thead>
        <tbody>{documents.slice(0, 6).map((doc) => <tr key={doc.name}><td><strong>{doc.name}</strong></td><td>{doc.type}</td><td>{doc.owner}</td><td>{doc.scanStatus}</td><td>{doc.riskCount}</td></tr>)}</tbody>
      </table>
    </section>
  );
}

function RiskCards({ risks }) {
  return <section className="risk-grid">{risks.map((risk) => <RiskCard key={`${risk.risk_category}-${risk.sourceDocument}`} risk={risk} />)}</section>;
}

export function RiskCard({ risk }) {
  return (
    <article className={`risk-card severity-${risk.severity?.toLowerCase()}`}>
      <span className="severity-badge">{risk.severity}</span>
      <h3>{risk.risk_category}</h3>
      <p>{risk.ai_explanation}</p>
      <blockquote>{risk.quoted_text}</blockquote>
      <div className="detail-grid compact">
        <div><span>Source</span><strong>{risk.sourceDocument || "Diligence file"}</strong></div>
        <div><span>Owner</span><strong>{risk.owner || "Deal Team"}</strong></div>
        <div><span>Status</span><strong>{risk.status || "Open"}</strong></div>
        <div><span>Recommended Mitigation</span><strong>{risk.mitigation || "Indemnity"}</strong></div>
      </div>
      <strong>{risk.recommended_action || "Escalate to diligence lead and incorporate into transaction protections."}</strong>
    </article>
  );
}

function ValueBars({ metrics }) {
  const rows = [["Enterprise Value", metrics.enterpriseValue], ["DCF Value", metrics.dcfValue], ["Synergy Value", metrics.synergyValue], ["Opening Bid", metrics.openingBid], ["Walk-Away Price", metrics.walkAway]];
  const max = Math.max(...rows.map(([, value]) => Number(value) || 0), 1);
  return <section className="panel-flat"><div className="bar-list">{rows.map(([label, value]) => <div key={label} className="bar-row"><span>{label}</span><div><i style={{ width: `${((Number(value) || 0) / max) * 100}%` }} /></div><strong>{formatCurrency(value)}</strong></div>)}</div></section>;
}

function Terms({ report, metrics }) {
  return (
    <section className="two-column">
      <div className="panel-flat"><div className="mini-metrics"><div><span>Opening Bid</span><strong>{formatCurrency(metrics.openingBid)}</strong></div><div><span>Walk-Away Price</span><strong>{formatCurrency(metrics.walkAway)}</strong></div><div><span>Seller Leverage</span><strong>{report.negotiation_strategy?.seller_leverage || "Medium"}</strong></div></div></div>
      <div className="panel-flat"><ul className="clean-list">{(report.negotiation_strategy?.tactical_moves || []).map((move) => <li key={move}>{move}</li>)}</ul></div>
      <div className="table-panel span-2"><table className="data-table"><thead><tr><th>Term</th><th>Position</th><th>Status</th></tr></thead><tbody>{DEMO_NEGOTIATION_TERMS.map((term) => <tr key={term.term}><td>{term.term}</td><td>{term.value}</td><td><span className={`term-status status-${term.status}`}>{term.status}</span></td></tr>)}</tbody></table></div>
    </section>
  );
}

function Checklist() {
  return <section className="table-panel"><table className="data-table"><thead><tr><th>Item</th><th>Owner</th><th>Due Date</th><th>Status</th><th>Blocker</th></tr></thead><tbody>{DEMO_CLOSING_CHECKLIST.map((item) => <tr key={item.item}><td>{item.item}</td><td>{item.owner}</td><td>{item.dueDate}</td><td>{item.status}</td><td>{item.blocker}</td></tr>)}</tbody></table></section>;
}

function IntegrationPlan() {
  return <section className="table-panel"><table className="data-table"><thead><tr><th>Milestone</th><th>Workstream</th><th>Task</th><th>Owner</th><th>Status</th></tr></thead><tbody>{DEMO_INTEGRATION_TASKS.map((task) => <tr key={`${task.milestone}-${task.task}`}><td>{task.milestone}</td><td>{task.workstream}</td><td>{task.task}</td><td>{task.owner}</td><td>{task.status}</td></tr>)}</tbody></table></section>;
}

function Reports() {
  return <section className="table-panel"><table className="data-table"><thead><tr><th>Report</th><th>Generated By</th><th>Date</th><th>Status</th></tr></thead><tbody>{DEMO_REPORT_HISTORY.map((report) => <tr key={report.name}><td>{report.name}</td><td>{report.generatedBy}</td><td>{report.date}</td><td>{report.status}</td></tr>)}</tbody></table><Link className="link-button" to="/reports">Open Reports Center</Link></section>;
}
