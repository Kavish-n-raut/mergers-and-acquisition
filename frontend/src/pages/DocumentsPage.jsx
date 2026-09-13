import React, { useState } from "react";
import { DEMO_DOCUMENT_FOLDERS, getActiveDocuments } from "../lib/dealUtils";

export default function DocumentsPage() {
  const documents = getActiveDocuments();
  const [folder, setFolder] = useState("All");
  const [selectedDoc, setSelectedDoc] = useState(null);
  const visibleDocs = folder === "All" ? documents : documents.filter((doc) => doc.folder === folder);

  return (
    <div className="page">
      <section className="page-header">
        <div>
          <p className="eyebrow">Virtual Data Room</p>
          <h2>Document Vault</h2>
          <p className="muted">Sample VDR data linked to the Aster Northstar local demo package.</p>
        </div>
        <div className="action-row">
          <span className="source-chip">Sample documents</span>
          <button>Upload Documents</button>
          <button className="secondary-button">Scan Documents</button>
          <button className="secondary-button">Ask Question</button>
        </div>
      </section>

      <section className="folder-grid">
        {["All", ...DEMO_DOCUMENT_FOLDERS].map((item) => (
          <button key={item} className={folder === item ? "active" : ""} onClick={() => setFolder(item)}>
            {item}
          </button>
        ))}
      </section>

      <section className="table-panel">
        <table className="data-table">
          <thead>
            <tr>
              <th>Document Name</th>
              <th>Folder</th>
              <th>Owner</th>
              <th>Upload Date</th>
              <th>Scan Status</th>
              <th>Risk Count</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {visibleDocs.map((doc) => (
              <tr key={doc.name}>
                <td><strong>{doc.name}</strong><span className="subtext">{doc.type}</span></td>
                <td>{doc.folder}</td>
                <td>{doc.owner}</td>
                <td>{doc.uploadDate}</td>
                <td>{doc.scanStatus}</td>
                <td>{doc.riskCount}</td>
                <td>
                  <div className="action-row">
                    <button className="small-button">Scan</button>
                    <button className="small-button secondary-button">Ask Question</button>
                    <button className="small-button text-button" onClick={() => setSelectedDoc(doc)}>View Summary</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {selectedDoc && (
        <aside className="drawer">
          <button className="drawer-close" onClick={() => setSelectedDoc(null)}>Close</button>
          <p className="eyebrow">Document Summary</p>
          <h3>{selectedDoc.name}</h3>
          <div className="detail-grid">
            <div><span>Folder</span><strong>{selectedDoc.folder}</strong></div>
            <div><span>Owner</span><strong>{selectedDoc.owner}</strong></div>
            <div><span>Scan status</span><strong>{selectedDoc.scanStatus}</strong></div>
            <div><span>Risks</span><strong>{selectedDoc.riskCount}</strong></div>
          </div>
          <p>{selectedDoc.summary}</p>
        </aside>
      )}
    </div>
  );
}
