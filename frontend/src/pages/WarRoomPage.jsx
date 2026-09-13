import React, { useEffect, useState } from "react";
import { listWarRoomMessages, postWarRoomMessage } from "../lib/api";
import { DEMO_NEGOTIATION_TERMS, formatCurrency, getActiveDealMeta, getActiveReport, getMetrics } from "../lib/dealUtils";

export default function NegotiationPage() {
  const meta = getActiveDealMeta();
  const report = getActiveReport();
  const metrics = getMetrics(report);
  const activeDealId = localStorage.getItem("activeDealId");
  const [senderName, setSenderName] = useState("Deal Team");
  const [content, setContent] = useState("");
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!activeDealId) return;
    listWarRoomMessages(activeDealId).then((data) => setMessages(data.messages || [])).catch(() => setMessages([]));
  }, [activeDealId]);

  const sendMessage = async () => {
    if (!content.trim()) return;
    if (!activeDealId) {
      setMessages((prev) => [...prev, { sender_name: senderName, sender_role: "deal team", content }]);
      setContent("");
      return;
    }
    try {
      await postWarRoomMessage(activeDealId, senderName, content.trim());
      const data = await listWarRoomMessages(activeDealId);
      setMessages(data.messages || []);
      setContent("");
    } catch (e) {
      setError(e?.response?.data?.detail || "Unable to post negotiation update.");
    }
  };

  return (
    <div className="page">
      <section className="page-header">
        <div><p className="eyebrow">Negotiation</p><h2>{meta.dealName}</h2><p className="muted">Sample negotiation terms and Term Sheet tracker for local/free demo mode.</p></div>
        <span className="workspace-code compact">{meta.transactionCode}</span>
      </section>

      <section className="metric-grid">
        <div className="metric-card"><span>Initial Offer</span><strong>{formatCurrency(metrics.openingBid)}</strong></div>
        <div className="metric-card"><span>Current Offer</span><strong>{formatCurrency(92500000)}</strong></div>
        <div className="metric-card"><span>Walk-Away Price</span><strong>{formatCurrency(metrics.walkAway)}</strong></div>
        <div className="metric-card"><span>Seller Leverage</span><strong>{report.negotiation_strategy?.seller_leverage || "Medium"}</strong></div>
        <div className="metric-card"><span>Structure Recommendation</span><strong>{report.deal_structure?.recommended_structure || "Cash + Earn-out"}</strong></div>
      </section>

      <section className="two-column">
        <div className="panel-flat">
          <div className="section-title"><p className="eyebrow">Suggested Tactics</p><h3>Negotiation Playbook</h3></div>
          <ul className="clean-list">{(report.negotiation_strategy?.tactical_moves || []).map((move) => <li key={move}>{move}</li>)}</ul>
        </div>
        <div className="panel-flat">
          <div className="section-title"><p className="eyebrow">Notes Feed</p><h3>Negotiation Updates</h3></div>
          <div className="feed-window">
            {messages.map((msg, index) => <article key={`${msg.created_at || index}-${index}`} className="feed-item"><div className="feed-meta"><strong>{msg.sender_name}</strong><span>{msg.sender_role || "deal team"}</span></div><p>{msg.content}</p></article>)}
            {messages.length === 0 && <p className="empty-state">No negotiation notes have been recorded yet.</p>}
          </div>
          <div className="form-stack">
            <input value={senderName} onChange={(e) => setSenderName(e.target.value)} />
            <textarea rows={3} value={content} onChange={(e) => setContent(e.target.value)} placeholder="Add negotiation note" />
            <button onClick={sendMessage}>Post Update</button>
          </div>
        </div>
      </section>

      <section className="table-panel">
        <div className="section-title"><p className="eyebrow">Term Sheet Tracker</p><h3>Term Sheet - Key Deal Terms</h3></div>
        <table className="data-table">
          <thead><tr><th>Term</th><th>Current Position</th><th>Status</th></tr></thead>
          <tbody>{DEMO_NEGOTIATION_TERMS.map((term) => <tr key={term.term}><td>{term.term}</td><td>{term.value}</td><td><span className={`term-status status-${term.status}`}>{term.status}</span></td></tr>)}</tbody>
        </table>
      </section>
      {error && <p className="error-text">{error}</p>}
    </div>
  );
}
