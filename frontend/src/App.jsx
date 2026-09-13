import React, { lazy, Suspense, useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { getMarketDataSummary, getSession, logout } from "./lib/api";
import LoginPage from "./pages/LoginPage";

// Route pages are lazy-loaded so each page (and its heavy deps like recharts /
// maplibre / leaflet) ships as its own chunk, loaded only when the route is visited.
const HomePage = lazy(() => import("./pages/HomePage"));
const DealsPage = lazy(() => import("./pages/DealsPage"));
const ScreeningPage = lazy(() => import("./pages/ScreeningPage"));
const ApproachPage = lazy(() => import("./pages/ApproachPage"));
const DealWorkspacePage = lazy(() => import("./pages/DealWorkspacePage"));
const DocumentsPage = lazy(() => import("./pages/DocumentsPage"));
const ValuationPage = lazy(() => import("./pages/ValuationPage"));
const MarketIntelligencePage = lazy(() => import("./pages/MarketIntelligencePage"));
const DiligencePage = lazy(() => import("./pages/DiligencePage"));
const NegotiationPage = lazy(() => import("./pages/WarRoomPage"));
const FinancingPage = lazy(() => import("./pages/FinancingPage"));
const ClosingPage = lazy(() => import("./pages/ClosingPage"));
const IntegrationPage = lazy(() => import("./pages/IntegrationPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));
const DataSourcesPage = lazy(() => import("./pages/DataSourcesPage"));
const LiveIntelligencePage = lazy(() => import("./pages/LiveIntelligencePage"));

const navItems = [
  { to: "/", label: "Dashboard" },
  { to: "/pipeline", label: "Deal Pipeline" },
  { to: "/screening", label: "Target Screening" },
  { to: "/approach", label: "Approach" },
  { to: "/workspace", label: "Deal Workspace" },
  { to: "/documents", label: "Document Vault" },
  { to: "/valuation", label: "Valuation" },
  { to: "/market-intelligence", label: "Market Intelligence" },
  { to: "/live-intelligence", label: "Live Intelligence" },
  { to: "/diligence", label: "Due Diligence" },
  { to: "/negotiation", label: "Negotiation" },
  { to: "/financing", label: "Financing" },
  { to: "/closing", label: "Closing" },
  { to: "/integration", label: "Integration" },
  { to: "/reports", label: "Reports" },
  { to: "/settings", label: "Settings / Admin" },
  { to: "/datasources", label: "External Data" },
];

const fallbackMarketCards = [
  { label: "S&P 500", value: "5,310.74", change: "+0.61%", status: "positive", last_updated: "Sample", data_source: "Sample fallback", detail: "Broad US equity risk appetite proxy." },
  { label: "NASDAQ", value: "16,920.8", change: "+0.83%", status: "positive", last_updated: "Sample", data_source: "Sample fallback", detail: "Technology and growth equity sentiment proxy." },
  { label: "US10Y", value: "4.21%", change: "-2 bp", status: "positive", last_updated: "Sample", data_source: "Sample fallback", detail: "Risk-free discount-rate benchmark for valuation." },
  { label: "DXY", value: "103.88", change: "+0.12%", status: "neutral", last_updated: "Sample", data_source: "Sample fallback", detail: "US dollar strength proxy." },
  { label: "WTI", value: "$78.40", change: "-0.45%", status: "negative", last_updated: "Sample", data_source: "Sample fallback", detail: "Energy price marker." },
  { label: "Global M&A Activity", value: "+12% QoQ", change: "Improving", status: "positive", last_updated: "Sample", data_source: "Sample fallback", detail: "Indicative activity pulse only." },
  { label: "Private Credit Spread", value: "Stable", change: "Flat", status: "neutral", last_updated: "Sample", data_source: "Sample fallback", detail: "Financing climate indicator." },
];

export default function App() {
  const [marketCards, setMarketCards] = useState(fallbackMarketCards);
  const [user, setUser] = useState(() => {
    const session = getSession();
    return session?.token ? { username: session.username, role: session.role } : null;
  });

  useEffect(() => {
    getMarketDataSummary()
      .then((data) => setMarketCards(data.cards || fallbackMarketCards))
      .catch(() => setMarketCards(fallbackMarketCards));
  }, []);

  const handleLogout = () => {
    logout();
    setUser(null);
  };

  if (!user) {
    return <LoginPage onLogin={setUser} />;
  }

  return (
    <div className="app-shell">
      <header className="app-topbar">
        <div>
          <div className="eyebrow">QuantumBlack Advisory Systems</div>
          <h1>Enterprise M&A Deal Workspace</h1>
        </div>
        <div className="topbar-actions">
          <span>Signed in as {user.username}{user.role ? ` (${user.role})` : ""}</span>
          <button className="text-button" onClick={handleLogout}>
            Sign out
          </button>
        </div>
      </header>

      <div className="market-strip market-card-strip">
        {marketCards.map((item) => (
          <article key={item.label} className={`market-card status-${item.status}`}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <em>{item.change}</em>
            <div className="market-card-popover">
              <b>{item.label}</b>
              <p>{item.detail}</p>
              <small>Updated: {item.last_updated}</small>
              <small>Source: {item.data_source}</small>
            </div>
          </article>
        ))}
      </div>

      <div className="app-layout">
        <aside className="sidebar">
          <div className="sidebar-label">Workspace</div>
          <nav className="sidebar-nav">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </aside>

        <main className="content">
          <Suspense fallback={<div className="page"><div className="mini-loader" /><p className="muted">Loading…</p></div>}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/deals" element={<DealsPage />} />
            <Route path="/pipeline" element={<DealsPage />} />
            <Route path="/screening" element={<ScreeningPage />} />
            <Route path="/approach" element={<ApproachPage />} />
            <Route path="/workspace" element={<DealWorkspacePage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/valuation" element={<ValuationPage />} />
            <Route path="/market-intelligence" element={<MarketIntelligencePage />} />
            <Route path="/live-intelligence" element={<LiveIntelligencePage />} />
            <Route path="/diligence" element={<DiligencePage />} />
            <Route path="/negotiation" element={<NegotiationPage />} />
            <Route path="/financing" element={<FinancingPage />} />
            <Route path="/closing" element={<ClosingPage />} />
            <Route path="/integration" element={<IntegrationPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/settings" element={<SettingsPage />} />
            <Route path="/datasources" element={<DataSourcesPage />} />
          </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  );
}
